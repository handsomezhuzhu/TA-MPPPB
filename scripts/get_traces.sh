#!/usr/bin/env bash
# 下载 DPC-3 (SPEC CPU2017) ChampSim 压缩 trace 的一个代表性子集
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/traces"
BASE="https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu"
mkdir -p "$OUT"

TRACES=(
  410.bwaves-945B
  400.perlbench-41B
  437.leslie3d-134B
  403.gcc-16B
  429.mcf-22B
  450.soplex-92B
  483.xalancbmk-127B
  470.lbm-1274B
)

get() {
  local t="$1" f="$OUT/$1.champsimtrace.xz"
  if [[ -s "$f" ]]; then echo "skip $t"; return; fi
  echo "get  $t"
  if curl -sL --retry 3 --retry-delay 3 --max-time 1800 -o "$f.part" "$BASE/$t.champsimtrace.xz"; then
    mv "$f.part" "$f"
    echo "ok   $t $(du -h "$f" | cut -f1)"
  else
    echo "FAIL $t"; rm -f "$f.part"
  fi
}

n=0
for t in "${TRACES[@]}"; do
  get "$t" &
  n=$((n+1))
  if (( n % 3 == 0 )); then wait; fi
done
wait
echo "--- total ---"
du -sh "$OUT"