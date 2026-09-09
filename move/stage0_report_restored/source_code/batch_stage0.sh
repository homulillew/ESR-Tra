#!/usr/bin/env bash
run=/data1/ESR-Tra/traces/experiments/refactor_v21_forward
cd /data1/ESR-Tra/ESR-Tra-refactor-esr-state-2.1
for q in 324 120 594 234 364 854 1000 170; do
  for arm in esr/off esr/hard esr/soft; do
    f="$run/$arm/$q.exit"
    if [ -f "$f" ]; then echo "skip existing $arm/$q"; continue; fi
    echo "[start] $arm $q $(date -u +%H:%M:%S)"
    timeout --signal=TERM --kill-after=30s 900s \
      python $run/run_stage0_lanz.py "$q" "$arm" > $run/$arm/$q.stdout.log 2>&1
    echo "exit=$?" > "$f"
    echo "[end]   $arm $q $(date -u +%H:%M:%S) exit=$(cat "$f")"
  done
done
echo "STAGE0_BATCH_DONE"
