# TA-MPPPB: Translation- & Access-Aware MPPPB (v3)

**TA-MPPPB** (*Translation- & Access-Aware Multiperspective Reuse Prediction*) 是针对 **MPPPB (MICRO 2017)** Single-Core Static MDPP 在现代乱序核 + 虚存页表游走 + 硬件预取器环境中退化问题的零总线修改、近似零额外存储（维持 **60.41 KiB** 感知机与采样表不变，仅增 20-bit set-dueling 计数器）原创改进方案。

---

## 核心实验结论（8 条 SPEC Trace，50M Warmup + 150M Sim，现代 ChampSim）

| 场景配置 | 策略 | Geomean IPC 增益 (vs LRU) | vs 原版 MPPPB | Demand (LOAD+RFO+TRANS) MPKI 变化 | `LOAD+RFO` MPKI 变化 |
| --- | --- | ---: | ---: | ---: | ---: |
| **开启硬件预取器** (`L1D next_line + L2C ip_stride`) | `MPPPB (author2)` | +1.66% (`+1.6646%`) | 0.00% | -6.85% | -6.71% |
| **开启硬件预取器** | `SHiP_pref` | +2.56% (`+2.5582%`) | +0.88% | -7.18% | -7.15% |
| **开启硬件预取器** | `TA-MPPPB v2 (ta_pref)` | +2.60% (`+2.6038%`) | +0.92% | -8.24% | -7.22% |
| **开启硬件预取器** | **`TA-MPPPB v3 (ta_mpppb)`** | **+3.33% (`+3.3282%`)** | **+1.64%** | **-9.60%** | **-8.95%** |
| **无硬件预取器** | `SHiP-PC` | +4.30% (`+4.3003%`) | -0.13% | -8.07% | -7.79% |
| **无硬件预取器** | `MPPPB (author1)` | +4.44% (`+4.4352%`) | 0.00% | -9.02% | -8.86% |
| **无硬件预取器** | **`TA-MPPPB v3 (ta_mpppb_np)`** | **+4.72% (`+4.7247%`)** | **+0.28%** | **-9.88%** | **-9.35%** |

### 逐 Trace IPC 对比（开启硬件预取器）

| Trace | `LRU_pref` | `SHiP_pref` | `MPPPB (author2)` | **`TA-MPPPB v3 (ta_mpppb)`** | `v3` vs `author2` | `v3` vs `LRU_pref` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `400.perlbench-41B` | 1.3735 | 1.3929 | **1.4005** | 1.3963 | -0.29% | +1.67% |
| `403.gcc-16B` | **2.2054** | 2.2052 | 2.2044 | 2.2046 | +0.01% | -0.04% |
| `410.bwaves-945B` | 2.9747 | 2.9747 | 2.9747 | 2.9747 | +0.00% | +0.00% |
| `429.mcf-22B` | 0.4503 | 0.4546 | 0.4521 | **0.4695** | **+3.85%** | **+4.28%** |
| `437.leslie3d-134B` | **1.3478** | 1.3476 | 1.3146 | 1.3448 | **+2.29%** | -0.22% |
| `450.soplex-92B` | 0.4848 | **0.5080** | 0.5014 | 0.5025 | +0.21% | +3.64% |
| `470.lbm-1274B` | 0.6518 | 0.6513 | 0.6423 | **0.6689** | **+4.14%** | **+2.62%** |
| `483.xalancbmk-127B` | 0.3258 | 0.3720 | 0.3654 | **0.3764** | **+3.00%** | **+15.54%** |

---

## 核心设计（TA-MPPPB v3）

1. **Zero-PC `pc_ring` 屏蔽**：禁止 `pc == 0` 的 `WRITE`/`TRANSLATION`/`PREFETCH` 写入指令历史环形队列 `pc_ring`（`ab_mask_zero_pc_`, `ab_*_nopc_`），避免零 IP 破坏 14 张 PC 相关性感知机表的历史模式。
2. **`TRANSLATION` 防旁路、采样隔离与高保护插入（`idx = 8`）**：MMU 页表游走永不旁路、不占用地址采样器，插入 Static MDPP `idx = 8` 并在命中时使用 `kVecMdpp` 提升（将 `429.mcf` 页表命中由 `0.23%` 拉升至 `10.8%`，`483.xalancbmk` 提升至 `85.6%`）。
3. **Demand-Loss 驱动的对称 Set-Dueling（`wsel_`, `pfsel_`：`idx 8 vs 15`）**：针对 `WRITE`（slot 17/49）和开启预取时的 `PREFETCH`（slot 18/50），仅依据需求 `LOAD`/`RFO` 缺失代价更新 10-bit 对决计数器（`ab_duel_dem_w_=1, ab_duel_own_w_=0`），自动将冗余预取（如 `483` `pfsel=-505`）和冲刷性写回（如 `470` `wsel=-511`）压入冷插入位 `15`。
4. **双模 `WRITE` 采样一致性策略**：
   - 开启预取（`MPPPB_PROFILE=ta_mpppb`）：`ab_write_nosamp_ = true` + `ab_pref_nosamp_ = true`，消除 `429.mcf` 写采样负分漂移与 `483.xalancbmk` 预取采样高分桶膨胀；
   - 无预取（`MPPPB_PROFILE=ta_mpppb_np`）：保留创建者复用回传（`ab_write_nosamp_ = false, ab_write_preserve_ = true`），彻底避免 `450.soplex` 上的 *Write-Sampler Starvation*。

详细原理、因果归因表与 v1→v2→v3 消融演进请参见 [`docs/results_ta_mpppb.md`](docs/results_ta_mpppb.md)。

---

## 快速构建与复现

在基于 ChampSim（`develop @ 410cee62d9c429c043ea611325ce00e6c303be2a`）的工作目录下：

```bash
# 1. 将 mpppb 模块复制到 ChampSim/replacement/ 并应用最小 cache 对齐偏移补丁
cp -r champsim_modules/mpppb ChampSim/replacement/mpppb
git -C ChampSim apply ../patches/cache_offset.patch

# 2. 编译无预取版与开启硬件预取版二进制（注意不要重复传入 --replacement-dir 导致符号重复）
cd ChampSim
./config.sh ../configs/champsim_mpppb_mdpp.json && make -j"$(nproc)"
./config.sh ../configs/champsim_mpppb_mdpp_pref.json && make -j"$(nproc)"

# 3. 运行（200M 指令：50M warmup + 150M simulation）
MPPPB_PROFILE=ta_mpppb_np MPPPB_STATS=1 ./bin/champsim_mpppb_mdpp \
  -w 50000000 -i 150000000 --hide-heartbeat --json out_np.json trace.champsimtrace.xz

MPPPB_PROFILE=ta_mpppb MPPPB_STATS=1 ./bin/champsim_mpppb_mdpp_pref \
  -w 50000000 -i 150000000 --hide-heartbeat --json out_pref.json trace.champsimtrace.xz
```

*(注：`patches/champsim_410cee6_ta_mpppb.patch` 额外包含仅供对照研究的可选 `CHAMPSIM_PROPAGATE_PREF_IP` 开关；TA-MPPPB v3 主结果完全在**不启用**该硬件 PC 总线修改的条件下取得。)*

---

## 仓库目录结构

- `champsim_modules/mpppb/`：`TA-MPPPB v3` 与原版 Static MDPP/SHiP/MPPPB 统一替换策略源码（`mpppb.h`, `mpppb.cc`）
- `patches/`：`cache_offset.patch`（`src/cache.cc` unaligned 访问行内偏移修复）与对照用 `champsim_410cee6_ta_mpppb.patch`
- `configs/`：`champsim_mpppb_mdpp.json`、`champsim_mpppb_mdpp_pref.json` 及 `LRU`/`SHiP` 基线配置
- `scripts/`：trace 下载（`get_traces.sh`）、结果汇总与校验（`verify_results.py`, `summarize_champsim.py`, `analyze_attribution.py`）
- `results/`：全量 v3 对比 CSV（`ta_mpppb_v3_pref_comparison.csv`, `ta_mpppb_v3_nopref_comparison.csv`）、因果归因矩阵（`point1_attribution.csv`）及 v2 演进对照表
- `docs/`：完整技术分析文档（[`docs/results_ta_mpppb.md`](docs/results_ta_mpppb.md)、[`docs/final_report.md`](docs/final_report.md)）
