# TA-MPPPB: Translation- & Access-Aware MPPPB

**TA-MPPPB** (*Translation- & Access-Aware Multiperspective Reuse Prediction*) 是针对 **MPPPB（MICRO 2017）** Single-Core Static MDPP 在现代乱序核 + 五级虚存页表游走 + 多级硬件预取器环境中退化的原创改进方案：不修改任何缓存互连 / MSHR 总线接口，感知机 16 张特征表与 64×18 影子采样器规模与原版完全一致、不新增任何 SRAM 阵列，仅在全局控制器新增两个 10-bit 饱和集合决斗计数器（合计 **20 bits**）。

论文全文与 LaTeX 源码见 [`handsomezhuzhu/SHiP`](https://github.com/handsomezhuzhu/SHiP) 仓库 `paper/` 目录。

---

## 核心实验结论（全 28 负载 × 3 预取体系，336 场主对比）

评测集覆盖 5 个公开基准源共 28 条负载：SPEC CPU2006（8）、SPEC CPU2017 Speed（10）、GAP/XSBench（4）、CVP-1（3）、Qualcomm 服务器（3）；全部超参数冻结后一次性评测，几何平均 IPC 增益相对同组 LRU：

| 预取体系 | `SHiP-PC` | `MPPPB` | **`TA-MPPPB`** | TA vs `SHiP-PC` | TA vs `MPPPB` | 平均 `LR-MPKI`（LRU → TA） | `TRANSLATION` 命中率（MPPPB → TA） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 无预取（`L1D=no`, `L2C=no`） | +5.54% | +4.49% | **+4.82%** | −0.69% | +0.32% | 16.45 → 13.24 | 48.04% → **65.75%** |
| `next_line` + `ip_stride` | +4.10% | +1.34% | **+5.91%** | **+1.75%** | **+4.51%** | 10.84 → **7.38** | 46.98% → **69.38%** |
| `next_line` + `spp_dev` | +0.99% | −1.40% | **+2.55%** | **+1.54%** | **+4.00%** | 9.20 → **7.48** | 23.07% → **55.14%** |

核阻塞需求活跃子集（`LR-MPKI ≥ 2`）上，TA-MPPPB 在 `ip_stride` 与 `spp_dev` 下分别达到 **+10.76%** 与 **+4.99%**，并在 `spp_dev` 高压力子集对原版 MPPPB 实现 **15/0/0（全胜）**。

> 关键现象（**能力反转**）：原版 MPPPB 在无预取时以 +4.49% 领先 SHiP-PC 的 +4.30%（SPEC06 子集 +4.44% vs +4.30%），一旦开启预取器即跌至 +1.34%（`ip_stride`）乃至跌破 LRU 的 −1.40%（`spp_dev`）；TA-MPPPB 在三种体制下均为第一。

### SPEC CPU2006 子集（8 条，50M Warmup + 150M Sim）

| 场景配置 | 策略 | Geomean IPC 增益 (vs LRU) | vs 原版 MPPPB | Demand (LOAD+RFO+TRANS) MPKI 变化 | `LOAD+RFO` MPKI 变化 |
| --- | --- | ---: | ---: | ---: | ---: |
| **开启硬件预取器** (`L1D next_line + L2C ip_stride`) | `MPPPB (author2)` | +1.66% (`+1.6646%`) | 0.00% | -6.85% | -6.71% |
| **开启硬件预取器** | `SHiP_pref` | +2.56% (`+2.5582%`) | +0.88% | -7.18% | -7.15% |
| **开启硬件预取器** | **`TA-MPPPB (ta_mpppb)`** | **+3.33% (`+3.3282%`)** | **+1.64%** | **-9.60%** | **-8.95%** |
| **无硬件预取器** | `SHiP-PC` | +4.30% (`+4.3003%`) | -0.13% | -8.07% | -7.79% |
| **无硬件预取器** | `MPPPB (author1)` | +4.44% (`+4.4352%`) | 0.00% | -9.02% | -8.86% |
| **无硬件预取器** | **`TA-MPPPB (ta_mpppb_np)`** | **+4.72% (`+4.7247%`)** | **+0.28%** | **-9.88%** | **-9.35%** |

### 逐 Trace IPC 对比（开启硬件预取器）

| Trace | `LRU_pref` | `SHiP_pref` | `MPPPB (author2)` | **`TA-MPPPB (ta_mpppb)`** | `TA` vs `author2` | `TA` vs `LRU_pref` |
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

## 核心设计

1. **Zero-PC `pc_ring` 屏蔽**：禁止 `pc == 0` 的 `WRITE`/`TRANSLATION`/`PREFETCH` 写入指令历史环形队列 `pc_ring`（`ab_mask_zero_pc_`, `ab_*_nopc_`），避免零 IP 破坏 14 张 PC 相关性感知机表的历史模式。
2. **`TRANSLATION` 防旁路、采样隔离与中游插入（`idx = 8`）**：MMU 页表游走永不旁路、不占用地址采样器，插入 Static MDPP 中游保护位 `idx = 8` 并在命中时使用 `kVecMdpp` 晋升（将 `429.mcf` 页表命中由 `0.23%` 拉升，`483.xalancbmk` 提升至 `85.6%`）。
3. **Demand-Loss 驱动的正交双路 Set-Dueling（`wsel_`, `pfsel_`：`idx 8 vs 15`）**：针对 `WRITE`（slot 17/49）和开启预取时的 `PREFETCH`（slot 18/50），仅依据需求 `LOAD`/`RFO` 缺失代价更新 10-bit 对决计数器（`ab_duel_dem_w_=1, ab_duel_own_w_=0`），自动将冗余预取（如 `483` `pfsel=-505`）和冲刷性写回（如 `470` `wsel=-511`）压入冷插入位 `15`。
4. **双模 `WRITE` 采样一致性策略**：
   - 开启预取（`MPPPB_PROFILE=ta_mpppb`）：`ab_write_nosamp_ = true` + `ab_pref_nosamp_ = true`，消除 `429.mcf` 写采样负分漂移与 `483.xalancbmk` 预取采样高分桶膨胀；
   - 无预取（`MPPPB_PROFILE=ta_mpppb_np`）：保留创建者复用回传（`ab_write_nosamp_ = false, ab_write_preserve_ = true`），彻底避免 `450.soplex` 上的 *Write-Sampler Starvation*。

详细原理、因果归因表与早期迭代到定型方案的消融演进请参见 [`docs/results_ta_mpppb.md`](docs/results_ta_mpppb.md)。

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

### 正交留一法（LOO）消融开关

上述两个二进制均支持通过环境变量 `MPPPB_LOO` 精确剔除单个模块（论文 280 场双预取器 LOO 消融即由该开关生成，可多个 token 以逗号分隔）：

```bash
# 撤去 Zero-PC 屏蔽；撤去 PTW 固定中游保护；撤去写回仲裁；撤去预取仲裁
MPPPB_LOO=no_zero_pc,no_ptw_prot,no_write_arb,no_pref_arb ...
```

其余单变量开关见 `MPPPB_ABLATE`（如 `write_nopc`、`write_preserve`、`trans_duel` 等）。

---

## 仓库目录结构

- `champsim_modules/mpppb/`：TA-MPPPB 与原版 Static MDPP / SHiP / MPPPB 统一替换策略源码（`mpppb.h`, `mpppb.cc`）
- `patches/`：`cache_offset.patch`（`src/cache.cc` unaligned 访问行内偏移最小补丁）
- `configs/`：`champsim_mpppb_mdpp.json`、`champsim_mpppb_mdpp_pref.json` 及 `LRU`/`SHiP` 基线配置
- `scripts/`：trace 下载（`get_traces.sh`）、结果汇总与校验（`verify_results.py`, `summarize_champsim.py`, `analyze_attribution.py`）
- `results/`：全量对比 CSV（`ta_mpppb_pref_comparison.csv`, `ta_mpppb_nopref_comparison.csv`）、因果归因矩阵（`point1_attribution.csv`）及早期迭代演进对照表
- `docs/`：完整技术分析文档（[`docs/results_ta_mpppb.md`](docs/results_ta_mpppb.md)、[`docs/final_report.md`](docs/final_report.md)）