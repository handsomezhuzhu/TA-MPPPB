#!/usr/bin/env bash
# 构建 ChampSim (develop 分支, vcpkg 依赖), 日志在 env/build.log
set -euo pipefail
unset ALL_PROXY all_proxy
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$ROOT/env/venv/bin:$PATH"
cd "$ROOT/env/ChampSim"

echo "[1/5] git submodule (vcpkg)"
git submodule update --init --depth 1 vcpkg

echo "[2/5] bootstrap vcpkg"
if [[ ! -x vcpkg/vcpkg ]]; then
  vcpkg/bootstrap-vcpkg.sh -disableMetrics
fi

echo "[3/5] vcpkg install"
vcpkg/vcpkg install --triplet x64-linux --clean-after-build

echo "[4/5] configure champsim"
./config.sh champsim_config.json

echo "[5/5] make -j$(nproc)"
make -j"$(nproc)"
echo "BUILD OK: $(ls -l bin/champsim)"