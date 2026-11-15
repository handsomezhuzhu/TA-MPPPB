#!/usr/bin/env bash
# 批量运行 ChampSim：策略 × trace，输出 JSON，最后汇总为 CSV
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIM="$ROOT/env/ChampSim"
OUT="$ROOT/results/raw/champsim"
mkdir -p "$OUT"

WARMUP=${WARMUP:-50000000}
SIMINSTR=${SIMINSTR:-150000000}
POLICIES=${POLICIES:-"lru ship mpppb"}
PARALLEL=${PARALLEL:-6}

jobs=()
run_one() {
  local pol=$1 trace=$2 name
  name="$(basename "$trace" .champsimtrace.xz)"
  local dst="$OUT/$pol"
  mkdir -p "$dst"
  [[ -s "$dst/$name.json" ]] && { echo "skip $pol/$name"; return; }
  echo "run  $pol/$name"
  "$SIM/bin/champsim_$pol" -w "$WARMUP" -i "$SIMINSTR" --hide-heartbeat \
    --json "$dst/$name.json" "$trace" > "/dev/null" 2> "$dst/$name.err"
}

for t in "$ROOT"/traces/*.champsimtrace.xz; do
  for p in $POLICIES; do
    run_one "$p" "$t" &
    jobs+=($!)
    if (( ${#jobs[@]} >= PARALLEL )); then
      wait "${jobs[0]}"; jobs=("${jobs[@]:1}")
    fi
  done
done
wait

python3 "$ROOT/scripts/summarize_champsim.py" "$OUT" "$ROOT/results/champsim_results.csv"
echo "done -> $ROOT/results/champsim_results.csv"