from __future__ import annotations

import sqlite3

import pytest

from esr_grpo.environment import ESREnvironment, IllegalActionError
from esr_grpo.models import RetrievedDocument, TokenSpan
from esr_grpo.retrieval import InMemoryRetriever
from esr_grpo.verification import KeywordVerifier


def make_environment() -> ESREnvironment:
    retriever = InMemoryRetriever.from_documents(
        [
            RetrievedDocument("d1", "Vector Labs developed Orion Analytics."),
            RetrievedDocument("d2", "Northstar later redesigned Orion Analytics."),
        ]
    )
    return ESREnvironment("Who developed Orion?", retriever, KeywordVerifier(("Vector Labs",)))


def acquire(environment: ESREnvironment, docid: str = "d1") -> dict:
    search = environment.search("Vector Labs Orion Northstar", token_spans=[TokenSpan(0, 0, 2)])
    return environment.open_page(
        docid, search_action_id=search["action_id"], token_spans=[TokenSpan(0, 2, 4)]
    )


def test_evidence_is_immutable_at_database_layer() -> None:
    environment = make_environment()
    page = acquire(environment)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        environment.store._conn.execute(  # noqa: SLF001 - invariant test
            "UPDATE evidence SET payload_json = '{}' WHERE evidence_id = ?", (page["evidence_id"],)
        )


def test_update_requires_directory_coverage() -> None:
    environment = make_environment()
    acquire(environment)
    with pytest.raises(IllegalActionError, match="coverage"):
        environment.update_state("Vector Labs", [], ["e1"])
    assert environment.store.list_actions()[-1].legal is False


def test_coverage_reject_is_actionable_mentions_missing_id() -> None:
    """Fix7：coverage 拒绝要可操作——点名缺失 ID 并提醒它来自 open_page。

    复现 120 卡点：open 了 d1+d2 两个文档，update 只登记 d1，应被拒且
    文案指明 missing 里包含 d2（模型需把全部已打开而未登记的证据写进
    evidence_findings），而非只报一个干巴巴的 missing=[...]。
    """
    environment = make_environment()
    page1 = acquire(environment, "d1")
    s2 = environment.search("Northstar redesigned", token_spans=[TokenSpan(0, 0, 2)])
    page2 = environment.open_page("d2", search_action_id=s2["action_id"], token_spans=[TokenSpan(0, 2, 4)])
    # 只登记 d1 对应 evidence，必然 coverage missing=page2.evidence_id
    with pytest.raises(IllegalActionError, match="missing.*open_page"):
        environment.update_state(
            "Vector Labs",
            [{"evidence_id": page1["evidence_id"], "finding": "Vector Labs developed it."}],
            [page1["evidence_id"]],
        )
    # 缺口指向 page2 刚打开的 evidence_id
    exc = None
    try:
        environment.update_state(
            "Vector Labs",
            [{"evidence_id": page1["evidence_id"], "finding": "Vector Labs developed it."}],
            [page1["evidence_id"]],
        )
    except IllegalActionError as e:
        exc = str(e)
    assert exc is not None
    assert page2["evidence_id"] in exc  # 点名缺失 ID
    assert "open_page" in exc  # 提醒来自 open_page


def test_changed_finding_requires_original_evidence_to_be_visible() -> None:
    environment = make_environment()
    page = acquire(environment)
    environment.update_state(
        "Vector Labs",
        [{"evidence_id": page["evidence_id"], "finding": "Vector Labs developed it."}],
        [page["evidence_id"]],
    )
    with pytest.raises(IllegalActionError, match="visible original"):
        environment.update_state(
            "Vector Labs",
            [{"evidence_id": page["evidence_id"], "finding": "Changed finding."}],
            [page["evidence_id"]],
        )
    environment.read_evidence(page["evidence_id"])
    state = environment.update_state(
        "Vector Labs",
        [{"evidence_id": page["evidence_id"], "finding": "Changed finding."}],
        [page["evidence_id"]],
    )
    assert state["task_state"]["evidence_directory"][0]["finding"] == "Changed finding."


def test_gaps_are_only_changed_by_verification() -> None:
    environment = make_environment()
    page = acquire(environment, "d2")
    environment.update_state(
        "Northstar", [{"evidence_id": page["evidence_id"], "finding": "Northstar redesigned it."}], ["e1"]
    )
    verified = environment.verify_answer()
    assert verified["verification_status"] == "needs_revision"
    gap_ids = [item["gap_id"] for item in verified["gaps"]]
    environment.read_evidence("e1")
    updated = environment.update_state(
        "Northstar", [{"evidence_id": "e1", "finding": "Still only a redesign claim."}], ["e1"]
    )
    assert [item["gap_id"] for item in updated["task_state"]["gaps"]] == gap_ids


def test_submit_is_gated_by_supported_latest_state() -> None:
    environment = make_environment()
    page = acquire(environment)
    environment.update_state(
        "Vector Labs", [{"evidence_id": "e1", "finding": "Names Vector Labs."}], ["e1"]
    )
    with pytest.raises(IllegalActionError, match="verify_answer"):
        environment.submit_answer()
    environment.verify_answer()
    assert environment.submit_answer()["answer"] == "Vector Labs"


def test_new_evidence_invalidates_previous_verification() -> None:
    environment = make_environment()
    acquire(environment)
    environment.update_state(
        "Vector Labs", [{"evidence_id": "e1", "finding": "Names Vector Labs."}], ["e1"]
    )
    environment.verify_answer()
    acquire(environment, "d2")
    with pytest.raises(IllegalActionError, match="latest Evidence"):
        environment.submit_answer()


def test_parallel_calls_have_independent_action_ids_and_spans() -> None:
    environment = make_environment()
    search = environment.search("Vector Labs Northstar Orion")
    results = environment.execute_parallel(
        [
            {
                "name": "open_page",
                "arguments": {"docid": "d1", "search_action_id": search["action_id"]},
                "token_spans": [{"segment_index": 0, "start": 0, "end": 2}],
            },
            {
                "name": "open_page",
                "arguments": {"docid": "d2", "search_action_id": search["action_id"]},
                "token_spans": [{"segment_index": 0, "start": 2, "end": 4}],
            },
        ],
        turn_id="t1",
    )
    assert results[0]["action_id"] != results[1]["action_id"]
    actions = environment.store.list_actions()[-2:]
    assert {item.turn_id for item in actions} == {"t1"}
    assert actions[0].token_spans != actions[1].token_spans


# ---------------------------------------------------------------------------
# 超长文档的关键 chunk 观察视图（第二段检索 /get_doc_chunks 接入）
# ---------------------------------------------------------------------------

def _long_doc_environment() -> tuple[ESREnvironment, dict]:
    """构造一篇 >16k 字符的超长文档，真正的关键信息在 head 之后。

    返回 (env, page)。问题指向文中后部的一段明确文字。
    """
    filler = "这是无关的填充内容，介绍天气与研究背景。" * 700   # ≈700×18≈12600 字符的填充
    assert len(filler) < 16_000, "填充不能先超 16k"
    trailing = ("\n\nThe third focused research question is: "
                "Why would any graduate want to start a business in Nigeria?\n")
    content = filler + trailing
    # 若填充不足 16k，加长到确实越过观察窗
    while len(content) < 16_500:
        filler += "这是无关的填充内容，介绍天气与研究背景。"
        content = filler + trailing
    assert len(content) > 16_000, "测试前提：内容必须超过 observation_char_limit=16000"
    # 确保 search 能命中该 doc：query 里带正文 token
    retriever = InMemoryRetriever.from_documents(
        [RetrievedDocument("d_long", content, "Long Dissertation")]
    )
    env = ESREnvironment(
        "What is the third focused research question in the study?",
        retriever,
        KeywordVerifier(("Why would any graduate want to start a business in Nigeria?",)),
    )
    search = env.search(
        "third focused research question graduate business Nigeria",
        token_spans=[TokenSpan(0, 0, 2)],
    )
    page = env.open_page(
        "d_long", search_action_id=search["action_id"], token_spans=[TokenSpan(0, 2, 4)]
    )
    return env, page


def test_open_page_returns_relevant_chunk_when_past_head():
    """open_page 的关键信息在 16k 头之外时，chunk 视图应把它暴露给模型。

    这是 query 120 型的核心断言：旧/头截断会看不到，chunk 视图能看到。
    """
    _, page = _long_doc_environment()
    assert page["view"] == "chunks", f"期望 chunk 视图, 实际 {page['view']}"
    assert "Why would any graduate want to start a business in Nigeria?" in page["content"], (
        "chunk 视图必须包含 key 信息，即使它在原文 16k 之后"
    )
    assert any(c for c in page.get("chunks", [])), "应当返回 chunk 元数据"


def test_open_page_root_head_is_not_shown_by_default():
    """head 截断时无关填充不应直接作为首屏主体（chunk 视图按相关度排序）。"""
    _, page = _long_doc_environment()
    # 首屏 chunk 应包含 key 信息，而不是只看到填充头的 windowns。
    assert page["content"].find("focused research question") != -1


def test_read_evidence_returns_chunk_view_by_default():
    """read_evidence 无 offset 时默认也走 chunk 视图，按问题排序。

    read_evidence 只能读 evidence_directory 里已登记的 ID，故先用 open_page 返回的
    evidence_id 做一次 update_state 登记，再重读。
    """
    env, page = _long_doc_environment()
    eid = page["evidence_id"]
    env.update_state(
        "Why would any graduate want to start a business in Nigeria?",
        [{"evidence_id": eid, "finding": "Reads the third research question."}],
        [eid],
    )
    read = env.read_evidence(eid, token_spans=[TokenSpan(0, 5, 8)])
    assert read["view"] == "chunks", f"期望 chunk 视图, 实际 {read['view']}"
    assert "Why would any graduate want to start a business in Nigeria?" in read["content"]


def test_read_evidence_offset_removed_unify_on_chunk_view():
    """方案 B/E'：offset 已移除，read_evidence 默认且唯一地返回 chunk 视图。

    read_evidence 不再接受 offset（避免从原文任意偏移续读）；重读返回与 open_page
    一致、按该证据被 open 时的 search query 排序的 chunk 视图。也即 search 与 verify
    阅读同一份视图，杜绝 verify 读到 search 从未展示的内容。
    """
    import inspect

    from esr_grpo.environment import ESREnvironment

    sig = inspect.signature(ESREnvironment.read_evidence)
    assert "offset" not in sig.parameters, "offset 应已从 read_evidence 移除"

    env, page = _long_doc_environment()
    eid = page["evidence_id"]
    env.update_state(
        "Why would any graduate want to start a business in Nigeria?",
        [{"evidence_id": eid, "finding": "Reads the third research question."}],
        [eid],
    )
    read = env.read_evidence(eid, token_spans=[TokenSpan(0, 6, 9)])
    assert read["view"] == "chunks", f"期望 chunk 视图, 实际 {read['view']}"
    assert "Why would any graduate want to start a business in Nigeria?" in read["content"]


def test_open_page_falls_back_to_head_when_retriever_has_no_chunks():
    """retriever 无 get_doc_chunks / 报错时，open_page 应回退到头截断，行为不倒退。"""
    class _NoChunkRetriever(InMemoryRetriever):
        def get_doc_chunks(self, docid, query, topk=3):
            raise RuntimeError("no chunk support")

    # 超长填充（越过 16k 头截断），关键答案在尾部，chunk 服务不可用时必须回退头截断
    filler = "无关填充。" * 3400  # ≈17000 字符，> observation_char_limit=16000
    trailing = "\n尾部关键答案 X"
    content = filler + trailing
    assert len(content) > 16_000
    retriever = _NoChunkRetriever.from_documents([RetrievedDocument("d_fb", content, "Doc")])
    env = ESREnvironment("What is the answer?", retriever, KeywordVerifier(("尾部关键答案",)))
    search = env.search("无关填充", token_spans=[TokenSpan(0, 0, 2)])
    page = env.open_page("d_fb", search_action_id=search["action_id"],
                         token_spans=[TokenSpan(0, 2, 4)])
    assert page["view"] == "head", f"应回退 head 截断, 实际 {page['view']}"
    assert page["content"] == content[:16_000]  # 精确回到头截断（16k 之后不可见）
    assert "尾部关键答案" not in page["content"]  # key 信息在 16k 之后，头截断看不到


def test_verify_receives_same_chunk_view_not_full_doc():
    """方案 E'（设计文档 §2.3/§4.2 落实）：verify 送入验证器的必须是模型 open 时真正
    看到的同一份 chunk 视图，而非全文原文——否则验证器读到 search 从未展示的头/尾内容，
    形成观察面不对称与越权实体。

    用一个记录收到的 evidence content 的探针 verifier 断言：
      - 收到的是 chunk 视图（view=="chunks" 对应的关键片段），而不是 >16k 的全文；
      - chunk 视图含 key 信息（应被验证器读到），因为它在 open 时已暴露给模型。
    """
    class _RecordingVerifier:
        def __init__(self, keyword):
            self._keyword = keyword
            self.saw_content = None

        def verify(self, question, answer, evidence):
            from esr_grpo.verification import VerificationResult, VerificationStatus
            self.saw_content = "".join(e.content for e in evidence)
            supported = self._keyword in self.saw_content
            return VerificationResult(
                status=VerificationStatus.SUPPORTED if supported else VerificationStatus.NEEDS_REVISION,
                rationale="probe",
                gaps=[] if supported else ["need the key info"],
            )

    env, page = _long_doc_environment()
    eid = page["evidence_id"]
    verifier = _RecordingVerifier("Why would any graduate")
    env.verifier = verifier  # 替换探针（环境在构造后属性可变）
    env.update_state(
        "What is the third focused research question in the study?",
        [{"evidence_id": eid, "finding": "Reads the third research question."}],
        [eid],
    )
    result = env.verify_answer()
    full_len = len(env.store.get_evidence(eid).content)
    assert full_len > 16_000, "测试前提：证据是全文长文（原文被存证为完整 doc）"
    # 验证器收到的是 chunk 视图，不是 >16k 全文
    assert verifier.saw_content is not None
    assert len(verifier.saw_content) < full_len, "验证器不应收到全文原文（应收到 chunk 视图）"
    assert len(env.store.get_evidence(eid).content) == full_len  # 原文存证不受影响
    # chunk 视图含 key 信息 → 验证器能读到模型实际看到的内容
    assert "Why would any graduate" in verifier.saw_content
    assert result["verification_status"] == "supported"
