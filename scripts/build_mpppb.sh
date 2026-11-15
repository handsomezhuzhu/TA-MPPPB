#!/usr/bin/env bash
# 编译 MPPPB 模块（源码在 champsim_modules/mpppb）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$ROOT/env/venv/bin:$PATH"
cd "$ROOT/env/ChampSim"
./config.sh --replacement-dir "$ROOT/champsim_modules" "$ROOT/configs/champsim_mpppb.json"
make -j"$(nproc)"
ls -l bin/champsim_mpppb
