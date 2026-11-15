#!/usr/bin/env bash
# 为每种 LLC 替换策略编译一个 ChampSim 可执行文件（bin/champsim_<policy>）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$ROOT/env/venv/bin:$PATH"
cd "$ROOT/env/ChampSim"

for pol in lru srrip drrip ship; do
  echo "=== configure/build $pol ==="
  ./config.sh "$ROOT/configs/champsim_$pol.json"
  make -j"$(nproc)" >/dev/null
  ls -l "bin/champsim_$pol"
done