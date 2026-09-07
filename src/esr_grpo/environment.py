"""ESR-GRPO Harness：执行工具、校验协议并记录动作关系。"""

from __future__ import annotations

import dataclasses
import hashlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import (
    ActionKind,
    ActionRecord,
    Evidence,
    EvidenceFinding,
    EvidenceSource,
    Gap,
    TaskState,
    TokenSpan,
    VerificationStatus,
    normalize_spans,
    to_primitive,
)
from .retrieval import Retriever
from .store import EpisodeStore
from .verification import Verifier


class IllegalActionError(RuntimeError):
    def __init__(self, message: str, action_id: str | None = None) -> None:
        super().__init__(message)
        self.action_id = action_id


class ESREnvironment:
    """一个问题对应一个环境实例和一个追加式事件账本。"""

    def __init__(
        self,
        question: str,
        retriever: Retriever,
        verifier: Verifier,
        *,
        store: EpisodeStore | None = None,
        store_path: str | Path = ":memory:",
        episode_id: str | None = None,
        search_top_k: int = 5,
        observation_char_limit: int = 16_000,
        finding_char_limit: int = 600,
        max_gaps: int = 8,
        action_budget: int = 30,
    ) -> None:
        if not question.strip():
            raise ValueError("question must not be empty")
        self.question = question.strip()
        self.retriever = retriever
        self.verifier = verifier
        self.store = store or EpisodeStore(store_path)
        self.search_top_k = search_top_k
        self.observation_char_limit = observation_char_limit
        self.finding_char_limit = finding_char_limit
        self.max_gaps = max_gaps
        # 动作预算（=AgentRunner.max_turns）：guidance 据此在预算尾部注入收敛提醒，
        # 避免模型在触顶时仍"再找一篇"而从未收敛提交（19/81 条触顶实证）。
        self.action_budget = action_budget
        self._lock = threading.RLock()
        self._visible_evidence_inputs: dict[str, str] = {}

        stored_question = self.store.get_metadata("question")
        if stored_question is None:
            self.store.set_metadata_once("episode_id", episode_id or uuid.uuid4().hex)
            self.store.set_metadata_once("question", self.question)
        elif stored_question != self.question:
            raise ValueError("store belongs to a different question")

    @property
    def current_state(self) -> TaskState | None:
        return self.store.latest_state()

    @property
    def is_submitted(self) -> bool:
        return self.store.get_metadata("submit_action_id") is not None

    @property
    def submitted_answer(self) -> str | None:
        return self.store.get_metadata("submitted_answer")

    def search(
        self,
        query: str,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if not query.strip():
                return self._reject(ActionKind.SEARCH, "search query must not be empty", token_spans, turn_id)
            hits = self.retriever.search(query.strip(), top_k or self.search_top_k)
            action = self._make_action(
                ActionKind.SEARCH,
                token_spans,
                turn_id=turn_id,
                active_gap_ids=self._active_gap_ids(),
                metadata={"query": query.strip(), "hits": [to_primitive(item) for item in hits]},
            )
            self.store.add_action(action)
            return {"action_id": action.action_id, "results": [to_primitive(item) for item in hits]}

    def open_page(
        self,
        docid: str,
        *,
        search_action_id: str,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """读取整篇文档，并在截断模型观察前持久化完整正文。"""

        with self._lock:
            try:
                search_action = self.store.get_action(search_action_id)
            except KeyError:
                return self._reject(
                    ActionKind.OPEN_PAGE, "search_action_id does not exist", token_spans, turn_id
                )
            if search_action.kind is not ActionKind.SEARCH or not search_action.legal:
                return self._reject(
                    ActionKind.OPEN_PAGE, "open_page parent must be a legal search action", token_spans, turn_id
                )
            hit_ids = {str(item.get("docid")) for item in search_action.metadata.get("hits", [])}
            if docid not in hit_ids:
                return self._reject(
                    ActionKind.OPEN_PAGE,
                    "document was not returned by the referenced search action",
                    token_spans,
                    turn_id,
                )

            document = self.retriever.get_document(docid)
            if not document.content:
                return self._reject(ActionKind.OPEN_PAGE, "retrieved document is empty", token_spans, turn_id)
            content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
            source = EvidenceSource(document.docid, document.url, document.title)
            existing = self.store.find_evidence(source.key, content_hash)
            action_id, sequence_index = self._next_action_identity()
            evidence: Evidence | None = None
            if existing is None:
                evidence_id = f"e{len(self.store.list_evidence()) + 1}"
                evidence = Evidence(
                    evidence_id=evidence_id,
                    source=source,
                    content=document.content,
                    content_sha256=content_hash,
                    created_by_action_id=action_id,
                    search_action_id=search_action_id,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            else:
                evidence_id = existing.evidence_id
            action = ActionRecord(
                action_id=action_id,
                sequence_index=sequence_index,
                turn_id=turn_id,
                kind=ActionKind.OPEN_PAGE,
                token_spans=normalize_spans(token_spans),
                legal=True,
                state_version_before=self._state_version(),
                parent_action_ids=(search_action_id,),
                referenced_evidence_ids=() if evidence is not None else (evidence_id,),
                created_evidence_ids=(evidence_id,) if evidence is not None else (),
                active_gap_ids=self._active_gap_ids(),
                metadata={"docid": docid, "duplicate": evidence is None},
            )
            self.store.commit_transition(action, evidence=evidence)
            self._visible_evidence_inputs[evidence_id] = action.action_id
            # 观察视图：优先返回 BM25 关键 chunk（按引发本次 open 的 search query 排序），
            # 服务不可用或无可用 chunk 时回退到原 16k 头截断，行为不倒退。
            sort_query = str(search_action.metadata.get("query") or self.question)
            visible, view, chunk_meta = self._chunk_view(
                docid, sort_query, document.content, fallback_head=True
            )
            return {
                "action_id": action.action_id,
                "evidence_id": evidence_id,
                "source": to_primitive(source),
                "content": visible,
                "truncated": len(visible) < len(document.content),
                "stored_content_chars": len(document.content),
                "duplicate": evidence is None,
                "view": view,
                "chunks": chunk_meta,
            }

    def read_evidence(
        self,
        evidence_id: str,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """重读已登记证据。

        与 open_page / verify 统一：返回按【该证据被 open 时的 search query】排序的关键
        chunk 视图（方案 B），保证重读看到的正是模型当初真正读过的同一份视图，而非从
        原文任意偏移续读（offset 已移除，避免 verify 看到 search 从未展示的内容形成泄露）。
        服务不可用时回退头截断。
        """
        with self._lock:
            state = self.current_state
            if state is None or evidence_id not in state.directory_map():
                return self._reject(
                    ActionKind.READ_EVIDENCE,
                    "read_evidence requires an Evidence ID in the current evidence_directory",
                    token_spans,
                    turn_id,
                )
            evidence = self.store.get_evidence(evidence_id)
            action = self._make_action(
                ActionKind.READ_EVIDENCE,
                token_spans,
                turn_id=turn_id,
                referenced_evidence_ids=(evidence_id,),
                active_gap_ids=self._active_gap_ids(),
                metadata={"evidence_id": evidence_id},
            )
            self.store.add_action(action)
            self._visible_evidence_inputs[evidence_id] = action.action_id
            full = evidence.content
            # 同一份 sort basis：证据被 open 时的 search query，与 open_page 观察一致。
            query = self._evidence_sort_query(evidence)
            visible, view, chunk_meta = self._chunk_view(
                evidence.source.docid, query, full, fallback_head=True
            )
            return {
                "action_id": action.action_id,
                "evidence_id": evidence_id,
                "source": to_primitive(evidence.source),
                "content": visible,
                "truncated": len(visible) < len(full),
                "stored_content_chars": len(full),
                "view": view,
                "chunks": chunk_meta,
            }

    def _evidence_sort_query(self, evidence: Evidence) -> str:
        """回退链得到该证据的 chunk 排序 query（方案 B）。

        优先用【证据被 open 时的 search query】（open_page 记录在
        action.metadata），保证重读/verify 与模型当初实际看到的视图一致；
        无记录或 query 缺失时回退到 self.question。
        """
        if evidence.search_action_id:
            try:
                act = self.store.get_action(evidence.search_action_id)
                q = act.metadata.get("query") if act.metadata else None
                if q:
                    return str(q)
            except Exception:
                pass
        return self.question

    def _chunk_view(
        self,
        docid: str,
        query: str,
        full: str,
        *,
        fallback_head: bool = True,
        topk: int = 3,
    ) -> tuple[str, str, dict]:
        """构造"精确观察视图"：优先返回 BM25 关键 chunk，失败/无 chunk 时回退头截断。

        返回 (visible_content, view, chunk_meta)：
          - view==="chunks": visible 是 top-K chunk 按 chunk_index 升序拼接、相邻去重消重叠，
            用分隔标注块边界；chunk_meta 含每个 chunk 的 index/score。
          - view==="head": 回退到原 content[:observation_char_limit] 头截断。
          - chunk_meta 用于让模型/日志定位涉及的关键片段。
        不改变证据库内容（原文仍全量存证）。纯观察接口层，Layer-1 合法。
        """
        try:
            chunks_call = getattr(self.retriever, "get_doc_chunks", None)
            if chunks_call is None:
                raise RuntimeError("retriever has no get_doc_chunks")
            resp = chunks_call(docid, query, topk=topk)
            raw_chunks = resp.get("chunks") or []
            if not raw_chunks:
                raise RuntimeError("no chunks returned")
            # 按 chunk_index 升序，保证局部连续；相邻重叠自然合并为一段，避免重复 token。
            items = sorted(
                (c for c in raw_chunks if (c.get("text") or "").strip()),
                key=lambda c: int(c.get("chunk_index", 0)),
            )
            # 相邻 chunk（chunk_index 连续）时，服务端 overlap 会造成重复尾/头。
            # 采用"连续块合并、接缝去重叠"：若 i+1 的起始与 i 的尾部重合，则从 i+1 中
            # 去掉那段重复前缀。用简单的"重复长度"启发式（前后 n 字符相同即视为重复 s 字符）。
            parts: list[str] = []
            chunk_meta = []
            for c in items:
                text = c["text"].strip()
                if not text:
                    continue
                idx = int(c.get("chunk_index", 0))
                score = c.get("score", 0.0)
                if parts:
                    prev = parts[-1]
                    # 计算重叠字符数：从 prev 尾部和 text 头部找最长公共前缀。
                    max_ol = min(len(prev), len(text))
                    ol = 0
                    for k in range(max_ol, 0, -1):
                        if text[:k] == prev[-k:]:
                            ol = k
                            break
                    if ol > 0:
                        text = text[ol:].strip()
                        if not text:
                            continue
                parts.append(text)
                chunk_meta.append({"chunk_index": idx, "score": score})
            if not parts:
                raise RuntimeError("all chunks empty after dedup")
            visible = "\n".join(
                f"[关键片段 #{m['chunk_index']}]\n{txt}" for m, txt in zip(chunk_meta, parts)
            )
            return visible, "chunks", chunk_meta
        except Exception:
            if not fallback_head:
                raise
            return full[: self.observation_char_limit], "head", {}

    def update_state(
        self,
        answer: str,
        evidence_findings: Sequence[EvidenceFinding | Mapping[str, str]],
        supporting_evidence: Sequence[str],
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """追加 TaskState；保留 gaps，并将验证状态重置为 unverified。"""

        with self._lock:
            before = self.current_state
            old_directory = before.directory_map() if before else {}
            patch: dict[str, str] = {}
            finding_inputs: dict[str, str] = {}
            for raw in evidence_findings:
                item = raw if isinstance(raw, EvidenceFinding) else EvidenceFinding(**dict(raw))
                finding = item.finding.strip()
                if not finding:
                    return self._reject(
                        ActionKind.UPDATE_STATE, f"finding for {item.evidence_id} is empty", token_spans, turn_id
                    )
                if len(finding) > self.finding_char_limit:
                    return self._reject(
                        ActionKind.UPDATE_STATE,
                        f"finding for {item.evidence_id} exceeds character limit",
                        token_spans,
                        turn_id,
                    )
                if item.evidence_id in patch:
                    return self._reject(
                        ActionKind.UPDATE_STATE, f"duplicate finding: {item.evidence_id}", token_spans, turn_id
                    )
                try:
                    self.store.get_evidence(item.evidence_id)
                except KeyError:
                    return self._reject(
                        ActionKind.UPDATE_STATE, f"unknown Evidence ID: {item.evidence_id}", token_spans, turn_id
                    )
                changed = old_directory.get(item.evidence_id) != finding
                if changed and item.evidence_id not in self._visible_evidence_inputs:
                    return self._reject(
                        ActionKind.UPDATE_STATE,
                        f"changed finding requires visible original Evidence: {item.evidence_id}。"
                        "你引用的这个证据 ID 你还没读过原文（或它是旧的归档 ID）。"
                        "请用最近一次 open_page/read_evidence 返回的新 evidence_id 写 finding，"
                        "不要硬塞没亲见原文的旧 ID。",
                        token_spans,
                        turn_id,
                    )
                if changed:
                    finding_inputs[item.evidence_id] = self._visible_evidence_inputs[item.evidence_id]
                patch[item.evidence_id] = finding

            new_directory = {**old_directory, **patch}
            archive_ids = [item.evidence_id for item in self.store.list_evidence()]
            missing = [item for item in archive_ids if item not in new_directory]
            extra = [item for item in new_directory if item not in set(archive_ids)]
            if missing or extra:
                # Fix7：coverage 拒绝要"可操作"——点名缺失/多余的证据 ID，并提醒
                # 缺失证据来自 open_page 返回、需一并纳入 evidence_findings。
                # 这是 observation 增强（Layer-1 协议合法），不替模型判断答案语义。
                parts = [f"evidence_directory coverage failed; missing={missing}, extra={extra}"]
                if missing:
                    parts.append(
                        f"缺失的证据 ID {missing} 是你已 open_page 打开、但还没写进本次 "
                        "evidence_findings 的证据。请把它们的 evidence_id 一并填进 "
                        "evidence_findings 的每一条（写成 {evidence_id: <该ID>, finding: <描述>}），"
                        "即使这次只新增一条也要覆盖全部已打开而未登记的证据。"
                    )
                if not missing and extra:
                    parts.append(
                        f"多出的证据 ID {extra} 不存在于本条轨迹；请只引用真实 open_page/read_evidence 返回的 ID，"
                        "不要用记忆里不存在的编号。"
                    )
                return self._reject(
                    ActionKind.UPDATE_STATE,
                    " ".join(parts),
                    token_spans,
                    turn_id,
                )
            support = tuple(dict.fromkeys(str(item) for item in supporting_evidence))
            if len(support) != len(supporting_evidence):
                return self._reject(ActionKind.UPDATE_STATE, "supporting_evidence contains duplicates", token_spans, turn_id)
            unknown_support = [item for item in support if item not in new_directory]
            if unknown_support:
                return self._reject(
                    ActionKind.UPDATE_STATE,
                    f"supporting_evidence is not in directory: {unknown_support}",
                    token_spans,
                    turn_id,
                )
            normalized_answer = answer.strip()
            if normalized_answer and not support:
                return self._reject(
                    ActionKind.UPDATE_STATE, "a non-empty answer requires supporting_evidence", token_spans, turn_id
                )

            action_id, sequence_index = self._next_action_identity()
            state = TaskState(
                version=(before.version + 1) if before else 1,
                parent_version=before.version if before else None,
                evidence_directory=tuple(
                    EvidenceFinding(evidence_id, new_directory[evidence_id]) for evidence_id in archive_ids
                ),
                answer=normalized_answer,
                supporting_evidence=support,
                gaps=before.gaps if before else (),
                verification_status=VerificationStatus.UNVERIFIED,
                created_by_action_id=action_id,
            )
            action = ActionRecord(
                action_id=action_id,
                sequence_index=sequence_index,
                turn_id=turn_id,
                kind=ActionKind.UPDATE_STATE,
                token_spans=normalize_spans(token_spans),
                legal=True,
                state_version_before=before.version if before else None,
                state_version_after=state.version,
                parent_action_ids=tuple(dict.fromkeys(finding_inputs.values())),
                referenced_evidence_ids=tuple(new_directory),
                active_gap_ids=self._active_gap_ids(),
                metadata={
                    "finding_inputs": finding_inputs,
                    "changed_finding_ids": [
                        key for key, value in new_directory.items() if old_directory.get(key) != value
                    ],
                    "answer_changed": before is None or before.answer != normalized_answer,
                    "support_changed": before is None or before.supporting_evidence != support,
                },
            )
            self.store.commit_transition(action, state=state)
            self._visible_evidence_inputs.clear()
            return {"action_id": action.action_id, "task_state": to_primitive(state)}

    def verify_answer(
        self,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            before = self.current_state
            error = self._verification_error(before)
            if error:
                return self._reject(ActionKind.VERIFY_ANSWER, error, token_spans, turn_id)
            assert before is not None
            # 方案 B（文档 §2.3/§4.2 的落实）：把送入验证器的每条 supporting Evidence 从
            # "全文原文" 收敛为 "模型当初 open 时真正看到的同一份 chunk 视图"，避免 verify
            # 读到 search 从未展示的头/尾内容（观察面不对称 + 越权实体）。用 dataclasses.replace
            # 保持证据不可变性（仅替换视图内容，source/search_action_id 等元数据不变）。
            evidence: list[Evidence] = []
            for item in (self.store.get_evidence(i) for i in before.supporting_evidence):
                visible = self._chunk_view(
                    item.source.docid, self._evidence_sort_query(item), item.content, fallback_head=True
                )[0]
                evidence.append(dataclasses.replace(item, content=visible))
            try:
                result = self.verifier.verify(self.question, before.answer, evidence)
            except Exception as exc:
                # verifier 服务瞬时故障（HTTP 4xx/5xx/超时/连接）不应终结整条轨迹：
                # 记为一次被拒绝的 verify。文案必须让模型明白这不是 needs_revision——
                # 答案和证据都不用动，原地重试即可（否则模型会误跑去搜新证据，23 号实证）。
                return self._reject(
                    ActionKind.VERIFY_ANSWER,
                    f"【系统服务瞬时故障，非答案问题】verify 服务暂时不可用（{type(exc).__name__}）。"
                    "你的答案与证据无需任何改动：【直接再次调用 verify_answer 重试】即可。",
                    token_spans,
                    turn_id,
                )
            if result.status is VerificationStatus.SUPPORTED and result.gaps:
                return self._reject(
                    ActionKind.VERIFY_ANSWER, "supported verifier result contains gaps", token_spans, turn_id
                )
            if result.status is VerificationStatus.NEEDS_REVISION and not result.gaps:
                return self._reject(
                    ActionKind.VERIFY_ANSWER, "needs_revision verifier result has no gap", token_spans, turn_id
                )
            if len(result.gaps) > self.max_gaps:
                return self._reject(
                    ActionKind.VERIFY_ANSWER, "verifier returned too many gaps", token_spans, turn_id
                )

            action_id, sequence_index = self._next_action_identity()
            old_by_text = {item.description.strip().lower(): item for item in before.gaps}
            gap_count = len({gap.gap_id for state in self.store.list_states() for gap in state.gaps})
            gaps: list[Gap] = []
            for description in result.gaps:
                text = description.strip()
                existing = old_by_text.get(text.lower())
                if existing is not None:
                    gaps.append(existing)
                else:
                    gap_count += 1
                    gaps.append(Gap(f"g{gap_count}", text, action_id))
            old_ids = {item.gap_id for item in before.gaps}
            new_ids = {item.gap_id for item in gaps}
            state = TaskState(
                version=before.version + 1,
                parent_version=before.version,
                evidence_directory=before.evidence_directory,
                answer=before.answer,
                supporting_evidence=before.supporting_evidence,
                gaps=tuple(gaps),
                verification_status=result.status,
                created_by_action_id=action_id,
            )
            action = ActionRecord(
                action_id=action_id,
                sequence_index=sequence_index,
                turn_id=turn_id,
                kind=ActionKind.VERIFY_ANSWER,
                token_spans=normalize_spans(token_spans),
                legal=True,
                state_version_before=before.version,
                state_version_after=state.version,
                referenced_evidence_ids=before.supporting_evidence,
                active_gap_ids=tuple(old_ids),
                metadata={
                    "verification_status": result.status.value,
                    "created_gap_ids": sorted(new_ids - old_ids),
                    "resolved_gap_ids": sorted(old_ids - new_ids),
                    "rationale": result.rationale,
                },
            )
            self.store.commit_transition(action, state=state)
            self._visible_evidence_inputs.clear()
            return {
                "action_id": action.action_id,
                "verification_status": result.status.value,
                "gaps": [to_primitive(item) for item in gaps],
                "rationale": result.rationale,
            }

    def submit_answer(
        self,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            state = self.current_state
            error = self._submission_error(state)
            if error:
                return self._reject(ActionKind.SUBMIT_ANSWER, error, token_spans, turn_id)
            assert state is not None
            action = self._make_action(
                ActionKind.SUBMIT_ANSWER,
                token_spans,
                turn_id=turn_id,
                referenced_evidence_ids=state.supporting_evidence,
                metadata={"answer": state.answer},
            )
            self.store.commit_transition(
                action,
                metadata_once={"submitted_answer": state.answer, "submit_action_id": action.action_id},
            )
            return {"action_id": action.action_id, "answer": state.answer}

    def finish(
        self,
        answer: str,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """Baseline 模式：不带 TaskState/验证 gate 直接提交最终答案。

        与 ESR 的 submit_answer 不同，finish 不要求 TaskState、不要求验证通过、
        不要求 gaps 为空。供"普通 Agent"对比条件使用，保证检索层（search/open_page）
        与 ESR 完全一致，唯一差距在于没有结构化 State 与验证 gate。
        """
        with self._lock:
            answer = answer.strip()
            if not answer:
                return self._reject(ActionKind.FINISH, "answer must not be empty", token_spans, turn_id)
            if self.is_submitted:
                return self._reject(ActionKind.FINISH, "episode has already been submitted", token_spans, turn_id)
            action = self._make_action(
                ActionKind.FINISH,
                token_spans,
                turn_id=turn_id,
                metadata={"answer": answer},
            )
            self.store.commit_transition(
                action,
                metadata_once={"submitted_answer": answer, "submit_action_id": action.action_id},
            )
            return {"action_id": action.action_id, "answer": answer}

    def execute_parallel(self, calls: Sequence[Mapping[str, Any]], *, turn_id: str) -> list[dict[str, Any]]:
        """并行调用只允许 search/open_page/read_evidence，并为每项分配独立 action_id。"""

        allowed = {"search", "open_page", "read_evidence"}
        if any(str(call.get("name")) not in allowed for call in calls):
            raise ValueError("parallel execution only supports search/open_page/read_evidence")

        def run(call: Mapping[str, Any]) -> dict[str, Any]:
            name = str(call["name"])
            arguments = dict(call.get("arguments", {}))
            arguments["turn_id"] = turn_id
            arguments["token_spans"] = call.get("token_spans")
            try:
                return getattr(self, name)(**arguments)
            except IllegalActionError as exc:
                return {"error": str(exc), "action_id": exc.action_id, "legal": False}

        with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
            return list(pool.map(run, calls))

    def execute_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        token_spans: Sequence[TokenSpan | Mapping[str, int]] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = dict(arguments or {})
        arguments["token_spans"] = token_spans
        arguments["turn_id"] = turn_id
        try:
            method = getattr(self, name)
        except AttributeError as exc:
            raise ValueError(f"unknown ESR tool: {name}") from exc
        try:
            return method(**arguments)
        except IllegalActionError:
            raise
        except TypeError as exc:
            # 模型传了签名外的参数（如 update_state(gaps=...)）：降级为一次非法动作拒绝，
            # 引导模型按 schema 重试，而不是让 TypeError 逃逸炸掉整条轨迹。
            raise IllegalActionError(
                f"工具 {name} 的参数不符合定义：{exc}。请严格按照工具 schema 的参数名重试"
                "（update_state 只接受 answer/evidence_findings/supporting_evidence，gaps 由 verify 生成、不可手工传入）。",
            ) from exc

    def render_context(self, *, mode: str = "esr") -> dict[str, Any]:
        state = self.current_state
        evidence = self.store.list_evidence()
        if mode == "baseline":
            return {
                "question": self.question,
                "evidence_archive_count": len(evidence),
                "evidence_sources": [
                    {"evidence_id": item.evidence_id, "source": to_primitive(item.source)} for item in evidence
                ],
                "allowed_actions": ["search", "open_page", "read_evidence", "finish"],
            }
        return {
            "question": self.question,
            "task_state": to_primitive(state) if state else None,
            "evidence_archive_count": len(evidence),
            "unindexed_evidence_ids": self._missing_directory_ids(state),
            "evidence_sources": [
                {"evidence_id": item.evidence_id, "source": to_primitive(item.source)} for item in evidence
            ],
            "allowed_actions": [item.value for item in ActionKind],
            "next_step_guidance": self._next_step_guidance(state),
        }

    def _search_open_break(self) -> str | None:
        """检测"连续多轮纯 search、期间没 open/update/verify"的死循环，并强制 open 最近的 top-1。

        4B 多跳查询常见两种 search 死循环：(a) state=None 之前(127/384 等, 30 轮纯 search
        不 open); (b) needs_revision 后的 gap 重搜又回到纯 search 吹循环。两者本质都是
        模型反复换 query 重搜却不读文档。此方法从最新动作向前数连续 search-only 片段,
        若 >=3 且命中 top-1 有效, 则点名 docid+search_action_id 强制 open_page。
        """
        actions = self.store.list_actions()
        if not actions:
            return None
        # 从最新向前数连续 search-only 片段（只认合法的、真实执行的 search）。
        # 非法动作（legal=False）不算进展也不算打断——它们是空转，若计入会形成
        # "search×2 → verify被拒 → search×2 → read被拒 → …" 的夹空转绕过断环器
        # （bad case 23 实证），因此跳过继续向前数。
        tail_search_count = 0
        latest: ActionRecord | None = None
        for act in reversed(actions):
            if not act.legal:
                continue
            if act.kind is ActionKind.SEARCH:
                tail_search_count += 1
                if latest is None:
                    latest = act
                continue
            # 只要最近动作里有任何合法的非 search（open/update/verify/read），就不是搜索死循环
            break
        if tail_search_count < 3 or latest is None:
            return None
        hits = latest.metadata.get("hits", []) if latest.metadata else []
        if not hits:
            return None
        top = hits[0]
        docid = str(top.get("docid", ""))
        if not docid:
            return None
        title = str(top.get("title", ""))[:60]
        return (
            f"你已连续 {tail_search_count} 个动作只 search 而没 open/update/verify，正在死循环。"
            f"【必须立即】open_page(docid=\"{docid}\", search_action_id=\"{latest.action_id}\") 打开最近一次 search 的 top-1 命中"
            f"（标题：{title or docid}），读其原文后再推进。禁止再 search。"
        )

    def _illegal_read_break(self, state: TaskState | None) -> str | None:
        """检测"连续多次非法 read_evidence"死循环并给出可读 ID 清单（bad case 170 实证）。

        模型常在 update_state 之前反复 read_evidence 一个尚未写入 evidence_directory
        的证据 ID（必然 legal=False），却不知道出路是先 update_state。这里点名可用 ID
        与出路，把模型从"猜 ID 撞墙"里捞出来。
        """
        actions = self.store.list_actions()
        consecutive_illegal_reads = 0
        for act in reversed(actions):
            if act.kind is ActionKind.READ_EVIDENCE and not act.legal:
                consecutive_illegal_reads += 1
                continue
            break
        if consecutive_illegal_reads < 3:
            return None
        missing = self._missing_directory_ids(state)
        directory = state.directory_map() if state else {}
        parts = [
            f"你已连续 {consecutive_illegal_reads} 次调用 read_evidence 全部被拒——这不是偶发参数错，"
            "你在反复读取一个不在 evidence_directory 里的证据。read_evidence 只能读当前 TaskState 的 "
            "evidence_directory 中已登记的 ID。"
        ]
        if missing:
            parts.append(
                f"你已打开但尚未登记的证据：{', '.join(missing[:8])}。"
                "【必须立即】先调用 update_state（在 evidence_findings 里为这些证据写入 finding），"
                "登记后即可正常 read_evidence。禁止再次直接 read 未登记的证据。"
            )
        elif directory:
            parts.append(
                f"当前可读的证据 ID：{', '.join(list(directory)[:8])}。"
                "如需读取新文档，先 open_page 打开它并 update_state 登记。"
            )
        else:
            parts.append("如需读取新文档，先 open_page 打开它并 update_state 登记。")
        return " ".join(parts)

    def _stale_evidence_id_break(self) -> str | None:
        """检测「攥着陈旧 evidence_id 撞 update_state / read_evidence 墙」死循环。

        bad case 170/186/324/391 实证：gap-worklist 让模型 open 对了新文档，但模型
        回头却用【旧/未见过原文】的证据 ID（如 e1）去做 update_state/read_evidence，
        全部 legal=False（update_state 报 "changed finding requires visible original
        Evidence: eX"，read_evidence 报 "requires an Evidence ID in the current
        evidence_directory"）。它不认 open_page 刚返回的新 ID（如 e45）。

        这里做三件事：
        1. 检测连续 ≥2 次非法 update_state（stale 串），或非法 update_state + 非法 read 混合串；
        2. 从最近一次【合法】open_page/read_evidence 的动作里找回它返回给模型的
           evidence_id —— 那是本窗口里模型唯一亲见过原文、可合法用于 update_state 的 ID；
        3. guidance 点名那个新 ID 与正确操作，禁止再用未亲见原文的旧 ID。
        """
        actions = self.store.list_actions()
        # 数尾部连续非法 update_state/read_evidence（stale 撞墙串）
        illegal_state_read_tail = 0
        for act in reversed(actions):
            if act.kind is ActionKind.UPDATE_STATE or act.kind is ActionKind.READ_EVIDENCE:
                if not act.legal:
                    illegal_state_read_tail += 1
                    continue
            break
        if illegal_state_read_tail < 2:
            return None
        # 确认 stale 串里确有 update_state 被 "changed finding requires visible original Evidence" 拒
        has_stale_update = any(
            a.kind is ActionKind.UPDATE_STATE and not a.legal
            and "changed finding requires visible original Evidence" in str((a.metadata or {}).get("error", ""))
            for a in actions
        )
        # 找回最近一次合法 open_page/read_evidence 返回的新 evidence_id
        fresh_id: str | None = None
        fresh_kind: str = ""
        for act in reversed(actions):
            if not act.legal:
                continue
            if act.kind is ActionKind.OPEN_PAGE and act.created_evidence_ids:
                fresh_id = str(act.created_evidence_ids[0])
                fresh_kind = "open_page"
                break
            if act.kind is ActionKind.READ_EVIDENCE:
                eid = str((act.metadata or {}).get("evidence_id", ""))
                if eid:
                    fresh_id = eid
                    fresh_kind = "read_evidence"
                    break
        parts = [
            f"你已连续 {illegal_state_read_tail} 次调 update_state/read_evidence 全部被拒——你引用的证据 ID 是"
            "【本窗口从未读过原文】的旧/归档 ID（证据未登记，或未亲见其原文）。"
        ]
        if has_stale_update:
            parts.append(
                "update_state 报 'changed finding requires visible original Evidence'：你不能为一个你没"
                "亲眼读过原文的证据写 finding。"
            )
        if fresh_id:
            parts.append(
                f"你最近一次 {fresh_kind} 返回、且你已亲见原文的证据 ID 是 **{fresh_id}**。"
                f"【必须立即】用 {fresh_id} 写进 update_state 的 evidence_findings（找到的实体/事实 + 来源），"
                f"【禁止】再用 e1 等任何你没读过原文的旧 ID。"
            )
        else:
            parts.append(
                "若你要引用一篇文档里的信息，必须先 open_page 打开它，把返回的 evidence_id 用进 update_state；"
                "不要拿记忆里的旧证据 ID 硬塞。"
            )
        parts.append(
            "正确操作序列：update_state(evidence_findings=[{evidence_id: 新鲜ID, finding: 你从该原文看到的事实}], "
            "supporting_evidence=[新鲜ID], answer=候选答案) → verify_answer。"
        )
        return " ".join(parts)

    def _verify_service_glitch(self) -> bool:
        """最近一次 verify 被拒是否为服务故障（而非答案被打回）。

        服务故障时模型不应去搜新证据（23 号后半程实证：把"稍后重试"当成了
        needs_revision 退回换词重搜），guidance 要明确引导原地重试 verify。
        """
        actions = self.store.list_actions()
        for act in reversed(actions):
            if act.kind is ActionKind.VERIFY_ANSWER:
                if not act.legal:
                    msg = str((act.metadata or {}).get("error", "") or (act.metadata or {}).get("reason", ""))
                    return "服务暂时不可用" in msg or "service" in msg.lower()
                return False  # 最近一次 verify 是合法的（真打回），不是故障
            break
        return False

    def _gap_worklist(self, state: TaskState) -> str:
        """把剩余 gap 编译成结构化作业单：从 gap 提取检索词，给出明确操作序列。

        bad case 分析显示模型被打回后只会同义改写重搜，缺"围绕 gap 定向补证据→
        回填→再 verify"的收敛闭环。这里把闭环写成逐条指令。
        """
        gap_texts = [gap.description for gap in state.gaps][:3]
        if not gap_texts:
            return ""
        lines = ["剩余 Gap（一次只解决一个，按序推进）："]
        for i, text in enumerate(gap_texts, 1):
            lines.append(f"  G{i}: {text}")
        lines.append(
            "操作序列（严格按此执行，禁止跳步）：\n"
            "  1. search(query=从 G1 里提取的关键实体/日期/标题词，不要同义改写原问题)\n"
            "  2. open_page(上一次 search 的 top-1 命中)\n"
            "  3. update_state(answer=修正后的答案, supporting_evidence=[新旧证据ID], "
            "evidence_findings 里为 G1 涉及的证据写明 finding)\n"
            "  4. verify_answer\n"
            "若 G1 的证据确实找不到：update_state 时给出当前最佳候选答案并注明证据不足，再 verify 让校验器裁决。"
        )
        return "\n".join(lines)

    def _soft_deadline_note(self) -> str:
        """动作预算尾部的确定性收敛提醒：别在轮数耗尽前还在扩大检索。"""
        used = len(self.store.list_actions())
        budget = self.action_budget
        if used >= int(budget * 0.9):
            return (
                f"【收敛提醒】已用 {used}/{budget} 轮，仅剩 {budget - used} 轮。"
                "【立即】停止开新检索方向：update_state 给出当前最佳候选答案，然后 verify_answer；"
                "verify 通过即 submit_answer。"
            )
        if used >= int(budget * 0.7):
            return (
                f"【预算提醒】已用 {used}/{budget} 轮。若当前答案已基本成形，优先 update_state+verify_answer 收敛，"
                "而不是继续扩大检索面。"
            )
        return ""

    def _next_step_guidance(self, state: TaskState | None) -> str:
        """基于当前 TaskState 的确定性协议推进建议，打破 search/open 死循环。

        预算尾部（>=70%/>=90%）额外注入收敛提醒，防止轮数耗尽仍未提交。
        """
        note = self._soft_deadline_note()
        core = self._next_step_guidance_core(state)
        if note and "收敛提醒" not in core:
            return f"{note}\n{core}"
        return core

    def _next_step_guidance_core(self, state: TaskState | None) -> str:
        # 最高优先级：陈旧 evidence_id 撞墙（update_state/read 被拒连串）优先于一切分支捞人
        stale_break = self._stale_evidence_id_break()
        if stale_break:
            return stale_break
        evidence = self.store.list_evidence()
        opened_count = len(evidence)
        unindexed = self._missing_directory_ids(state)
        if state is None:
            forced_read = self._illegal_read_break(state)
            if forced_read:
                return forced_read
            if opened_count == 0:
                forced = self._search_open_break()
                if forced:
                    return forced
                return "尚无任何 Evidence。下一步应调用 search 定位与问题相关的候选文档，然后 open_page 打开最相关的一篇。"
            if unindexed:
                return (
                    f"你已打开 {opened_count} 篇文档但尚未整理进 TaskState。"
                    "下一步【必须】调用 update_state，为已读 Evidence 写入 finding，并给出初步 answer。"
                )
            return "已打开文档但尚无 TaskState。调用 update_state 建立答案与主要证据。"
        verdict = state.verification_status
        if unindexed:
            forced_read = self._illegal_read_break(state)
            if forced_read:
                return forced_read
            return "存在已打开但未写入目录的 Evidence。先用 update_state 把最新 finding 与证据关系统一整理。"
        if not state.answer.strip():
            forced_read = self._illegal_read_break(state)
            if forced_read:
                return forced_read
            return (
                "TaskState 尚无候选答案。若你已读到足以定位答案的证据，调用 update_state 填入 answer"
                "（或留空/写'暂无候选'，表示还在搜索）。注意：answer 必须是你认为的候选【答案本身】，"
                "绝不能写搜索计划或过程描述。若还缺关键证据，继续 search 找能直接回答问题的那篇文档。"
            )
        if verdict is VerificationStatus.UNVERIFIED:
            forced_read = self._illegal_read_break(state)
            if forced_read:
                return forced_read
            return "答案已形成但尚未验证。下一步应调用 verify_answer 审计答案是否被证据充分支持（verify 后如需改动必须先 update_state）。"
        if verdict is VerificationStatus.NEEDS_REVISION:
            forced = self._search_open_break()
            if forced:
                # needs_revision 后的 gap 重搜也常陷入纯 search 死循环，同样强制 open
                return forced
            if self._verify_service_glitch():
                return (
                    "上一次 verify_answer 因【系统服务瞬时故障】被拒——这不是你的答案有问题，"
                    "不需要找新证据。【立即】再次调用 verify_answer 重试即可。"
                )
            if state.gaps:
                worklist = self._gap_worklist(state)
                return (
                    f"上次 verify 未通过，同一个 TaskState 不能再 verify。{worklist}"
                )
            return (
                "上次 verify 未通过。同一个 TaskState 不能重复 verify，必须先调用 update_state 修正 answer "
                "（或补充 supporting_evidence），才能再次 verify_answer。"
            )
        if state.gaps:
            return (
                f"仍存在 {len(state.gaps)} 个未解决 Gap。{self._gap_worklist(state)}"
            )
        if verdict is VerificationStatus.SUPPORTED:
            return "验证已通过且无遗留 Gap。下一步应调用 submit_answer 提交最终答案。"
        return "调用 verify_answer 推进验证。"

    def rebuild_context(self) -> dict[str, Any]:
        self._visible_evidence_inputs.clear()
        return self.render_context()

    def snapshot(self) -> dict[str, Any]:
        return self.store.snapshot()

    def _make_action(
        self,
        kind: ActionKind,
        spans: Sequence[TokenSpan | Mapping[str, int]] | None,
        *,
        turn_id: str | None,
        legal: bool = True,
        parent_action_ids: Sequence[str] = (),
        referenced_evidence_ids: Sequence[str] = (),
        created_evidence_ids: Sequence[str] = (),
        active_gap_ids: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> ActionRecord:
        action_id, sequence_index = self._next_action_identity()
        return ActionRecord(
            action_id=action_id,
            sequence_index=sequence_index,
            turn_id=turn_id,
            kind=kind,
            token_spans=normalize_spans(spans),
            legal=legal,
            state_version_before=self._state_version(),
            parent_action_ids=tuple(parent_action_ids),
            referenced_evidence_ids=tuple(referenced_evidence_ids),
            created_evidence_ids=tuple(created_evidence_ids),
            active_gap_ids=tuple(active_gap_ids),
            metadata=dict(metadata or {}),
        )

    def _reject(
        self,
        kind: ActionKind,
        message: str,
        spans: Sequence[TokenSpan | Mapping[str, int]] | None,
        turn_id: str | None,
    ) -> Any:
        action = self._make_action(kind, spans, turn_id=turn_id, legal=False, metadata={"error": message})
        self.store.add_action(action)
        raise IllegalActionError(message, action.action_id)

    def _next_action_identity(self) -> tuple[str, int]:
        index = len(self.store.list_actions())
        return f"a{index + 1}", index

    def _state_version(self) -> int | None:
        state = self.current_state
        return state.version if state else None

    def _active_gap_ids(self) -> tuple[str, ...]:
        state = self.current_state
        return tuple(item.gap_id for item in state.gaps) if state else ()

    def _missing_directory_ids(self, state: TaskState | None) -> list[str]:
        directory = set(state.directory_map()) if state else set()
        return [item.evidence_id for item in self.store.list_evidence() if item.evidence_id not in directory]

    def _verification_error(self, state: TaskState | None) -> str | None:
        if state is None:
            return "TaskState does not exist"
        if self._missing_directory_ids(state):
            return "latest Evidence has not been written to evidence_directory"
        if not state.supporting_evidence:
            return "current answer has no supporting Evidence"
        if state.verification_status is not VerificationStatus.UNVERIFIED:
            return "current TaskState has already been verified; call update_state before verifying again"
        # answer 允许为"暂无候选"或空：由校验模型判 needs_revision，而不是硬拒绝。
        # 否则模型在尚未形成候选时会被迫填搜索计划作为 answer（见偏差1）。
        return None

    def _submission_error(self, state: TaskState | None) -> str | None:
        if self.is_submitted:
            return "episode has already been submitted"
        if state is None:
            return "TaskState does not exist"
        if self._missing_directory_ids(state):
            return "latest Evidence has not been written to evidence_directory"
        if not state.answer:
            return "current answer is empty"
        if not state.supporting_evidence:
            return "current answer has no supporting Evidence"
        if state.gaps:
            return "current answer has unresolved gaps"
        if state.verification_status is not VerificationStatus.SUPPORTED:
            return "current answer has not passed verify_answer"
        return None


ESR_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {"name": "read_evidence", "parameters": {"evidence_id": "string"}},
    {
        "name": "update_state",
        "parameters": {
            "answer": "string",
            "evidence_findings": "array[{evidence_id,finding}]",
            "supporting_evidence": "array[string]",
        },
    },
    {"name": "verify_answer", "parameters": {}},
    {"name": "submit_answer", "parameters": {}},
)
