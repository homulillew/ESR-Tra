#!/usr/bin/env bash
# Stage-1 batch: 32B (Qwen3-32B @ :8002) as policy AND verifier, 4 arms x qids.
# Syntax: run_stage1.sh QID ARM
set -u
PY="python"
RESOLVE=""
cd /data1/ESR-Tra/ESR-Tra-refactor-esr-state-2.1
RUN=/data1/ESR-Tra/traces/experiments/refactor_v21_forward
QID="$1"
ARM="$2"
case "$ARM" in
  baseline/off) ARM_ARGS=(--mode baseline --audit-mode off) ;;
  esr/off)      ARM_ARGS=(--mode esr --audit-mode off) ;;
  esr/hard)     ARM_ARGS=(--mode esr --audit-mode hard) ;;
  esr/soft)     ARM_ARGS=(--mode esr --audit-mode soft) ;;
  *) echo "bad ARM=$ARM"; exit 2 ;;
esac
DIR="$RUN/$ARM"
mkdir -p "$DIR"
# 15-min wall clock = 900s
timeout --signal=TERM --kill-after=30s 900s \
  $PY -m esr_harness run \
  --dataset "$RUN/questions_only.jsonl" --qid "$QID" \
  "${ARM_ARGS[@]}" \
  --policy-url http://127.0.0.1:8002/v1 --model Qwen3-32B \
  --model-revision operator_declared --tokenizer /llm/modelscope/Qwen/Qwen3-32B \
  --thinking --temperature 0.6 --no-audit-thinking \
  --retrieval-url http://127.0.0.1:8000 --retrieval-revision operator_declared \
  --max-actions 64 --max-context-tokens 32768 \
  --max-output-tokens 2048 --audit-max-output-tokens 2048 \
  --max-total-completion-tokens 24000 --search-top-k 5 --view-chars 8000 \
  --max-pending-views 4 --recent-actions 4 \
  --store "$DIR/$QID.sqlite" --output "$DIR/$QID.summary.json" \
  > "$DIR/$QID.stdout.log" 2>&1
echo "exit=$?" > "$DIR/$QID.exit"