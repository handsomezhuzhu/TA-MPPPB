#!/usr/bin/env python3
"""Compare LRU / SHiP-PC / MPPPB from ChampSim JSON summaries.

Usage:
  compare_policies.py results/champsim_results.csv [--markdown out.md]

The CSV is produced by summarize_champsim.py:
  trace,policy,instructions,cycles,ipc,llc_access,llc_miss,llc_mpki,dram_cycles
"""
import argparse
import csv
import math
from collections import defaultdict

POLICIES = ("lru", "ship", "mpppb")
LABEL = {"lru": "LRU", "ship": "SHiP-PC", "mpppb": "MPPPB"}


def geom(values):
    values = [v for v in values if v > 0]
    return math.exp(sum(math.log(v) for v in values) / len(values)) if values else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    data = {}
    for r in rows:
        data[(r["trace"], r["policy"])] = (float(r["ipc"]), float(r["llc_mpki"]))

    traces = sorted({t for t, _ in data})
    lines = []
    lines.append("| trace | LRU IPC | SHiP IPC | MPPPB IPC | MPPPB/LRU | SHiP/LRU | LRU MPKI | SHiP MPKI | MPPPB MPKI |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    speedups = defaultdict(list)
    mpki_ratios = defaultdict(list)
    for t in traces:
        if (t, "lru") not in data:
            continue
        lru_ipc, lru_mpki = data[(t, "lru")]
        cells = [t, f"{lru_ipc:.4f}"]
        for p in ("ship", "mpppb"):
            ipc = data.get((t, p), (float("nan"), float("nan")))[0]
            cells.append(f"{ipc:.4f}" if ipc == ipc else "-")
        for p in ("mpppb", "ship"):
            ipc = data.get((t, p), (float("nan"), 0))[0]
            if ipc == ipc and lru_ipc:
                speedups[p].append(ipc / lru_ipc)
                cells.append(f"{ipc / lru_ipc:.4f}")
            else:
                cells.append("-")
        cells.append(f"{lru_mpki:.2f}")
        for p in ("ship", "mpppb"):
            mpki = data.get((t, p), (0, float("nan")))[1]
            cells.append(f"{mpki:.2f}" if mpki == mpki else "-")
            if mpki == mpki and lru_mpki:
                mpki_ratios[p].append(mpki / lru_mpki)
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("| policy | geomean IPC vs LRU | geomean MPKI vs LRU |")
    lines.append("|---|---|---|")
    for p in ("ship", "mpppb"):
        lines.append(f"| {LABEL[p]} | {geom(speedups[p]):.4f} | {geom(mpki_ratios[p]):.4f} |")

    text = "\n".join(lines)
    print(text)
    if args.markdown:
        open(args.markdown, "w").write(text + "\n")


if __name__ == "__main__":
    main()