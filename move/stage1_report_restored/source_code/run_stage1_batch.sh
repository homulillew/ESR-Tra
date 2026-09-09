#!/usr/bin/env bash
# Stage-1 batch: 32B (Qwen3-32B @ :8002) as policy AND verifier, 4 arms x 8 qids = 32 episodes.
# Serial (concurrency=1), writing to stage1/{arm}/ to avoid clobbering Stage0 data in {arm}/.
set -u
cd /data1/ESR-Tra/ESR-Tra-refactor-esr-state-2.1
RUN=/data1/ESR-Tra/traces/experiments/refactor_v21_forward
QIDS="324 120 594 234 364 854 1000 170"

declare -A ARM_ARGS
ARM_ARGS[baseline/off]="--mode baseline --audit-mode off"
ARM_ARGS[esr/off]="--mode esr --audit-mode off"
ARM_ARGS[esr/hard]="--mode esr --audit-mode hard"
ARM_ARGS[esr/soft]="--mode esr --audit-mode soft"

for arm in baseline/off esr/off esr/hard esr/soft; do
  DIR="$RUN/stage1/$arm"
  mkdir -p "$DIR"
  for q in $QIDS; do
    OUT="$DIR/$q.summary.json"
    if [ -f "$OUT" ]; then
      echo "skip existing stage1/$arm/$q"
      continue
    fi
    echo "[start] $arm $q $(date -u +%H:%M:%S)"
    # 15-min wall clock = 900s
    timeout --signal=TERM --kill-after=30s 900s \
      python -m esr_harness run \
      --dataset "$RUN/questions_only.jsonl" --qid "$q" \
      ${ARM_ARGS[$arm]} \
      --policy-url http://127.0.0.1:8002/v1 --model Qwen3-32B \
      --model-revision operator_declared --tokenizer /llm/modelscope/Qwen/Qwen3-32B \
      --thinking --temperature 0.6 --no-audit-thinking \
      --retrieval-url http://127.0.0.1:8000 --retrieval-revision operator_declared \
      --max-actions 64 --max-context-tokens 32768 \
      --max-output-tokens 2048 --audit-max-output-tokens 2048 \
      --max-total-completion-tokens 24000 --search-top-k 5 --view-chars 8000 \
      --max-pending-views 4 --recent-actions 4 \
      --store "$DIR/$q.sqlite" --output "$OUT" \
      > "$DIR/$q.stdout.log" 2>&1
    ec=$?
    echo "exit=$?" > "$DIR/$q.exit"
    echo "[end]   $arm $q $(date -u +%H:%M:%S) exit=$ec"
  done
done
echo "STAGE1_BATCH_DONE"