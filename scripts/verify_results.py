#!/usr/bin/env python3
"""Verify a ChampSim result matrix before deleting the machines.

Checks:
  * every (policy, trace) JSON exists and parses;
  * instructions are inside the expected window;
  * cycles > 0, a positive .time file exists;
  * .err files contain no panic/deadlock/error/abort/out_of_range;
  * optionally, the summary CSV matches the JSONs (row count, IPC, MPKI).

Usage:
  python scripts/verify_results.py --root results/raw/matrix1 \
      --csv results/matrix1_results.csv
"""
import argparse
import csv
import glob
import json
import math
import os
import sys

DEFAULT_TRACES = [
    "400.perlbench-41B", "403.gcc-16B", "410.bwaves-945B", "429.mcf-22B",
    "437.leslie3d-134B", "450.soplex-92B", "470.lbm-1274B", "483.xalancbmk-127B",
]
DEFAULT_POLICIES = ["lru", "ship", "mpppb"]
BAD_WORDS = ("panic", "deadlock", "error", "abort", "out_of_range")


def _parse_elapsed(text: str) -> float:
    """Parse either plain numeric seconds or key-value elapsed_sec=<float>."""
    for tok in text.split():
        if tok.startswith("elapsed_sec="):
            try:
                return float(tok.split("=", 1)[1].strip())
            except ValueError:
                return 0.0
    try:
        return float(text.strip() or 0)
    except ValueError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--traces", nargs="+", default=DEFAULT_TRACES)
    ap.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    ap.add_argument("--baseline", default="lru")
    ap.add_argument("--min-instr", type=int, default=150_000_000)
    ap.add_argument("--max-instr", type=int, default=150_000_010)
    args = ap.parse_args()

    bad = []
    rows = {}
    for pol in args.policies:
        for tr in args.traces:
            path = os.path.join(args.root, pol, tr + ".json")
            if not os.path.exists(path):
                bad.append(("missing", pol, tr))
                continue
            try:
                sim = json.load(open(path))[0]["sim"]
            except Exception as exc:  # noqa: BLE001
                bad.append(("json", pol, tr, str(exc)))
                continue
            core = sim["cores"][0]
            miss = sum(sum(sim["LLC"][k]["miss"]) for k in
                       ("LOAD", "RFO", "WRITE", "PREFETCH", "TRANSLATION"))
            rows[(tr, pol)] = (core["instructions"], core["cycles"], miss)
            if not (args.min_instr <= core["instructions"] <= args.max_instr):
                bad.append(("instr", pol, tr, core["instructions"]))
            if core["cycles"] <= 0:
                bad.append(("cycles", pol, tr, core["cycles"]))
            tpath = os.path.join(args.root, pol, tr + ".time")
            if not os.path.exists(tpath) or _parse_elapsed(open(tpath).read()) <= 0:
                bad.append(("time", pol, tr))
            for ext in (".err", ".log"):
                epath = os.path.join(args.root, pol, tr + ext)
                if os.path.exists(epath):
                    text = open(epath, errors="ignore").read().lower()
                    for word in BAD_WORDS:
                        if word in text:
                            bad.append((ext.lstrip("."), pol, tr, word))

    if args.csv:
        csv_rows = list(csv.DictReader(open(args.csv)))
        if len(csv_rows) != len(args.traces) * len(args.policies):
            bad.append(("csv_rows", len(csv_rows)))
        for r in csv_rows:
            key = (r["trace"], r["policy"])
            if key not in rows:
                bad.append(("csv_missing", key))
                continue
            ins, cyc, miss = rows[key]
            ipc = ins / cyc
            mpki = miss * 1000 / ins
            if abs(ipc - float(r["ipc"])) > 1e-3 or abs(mpki - float(r["llc_mpki"])) > 1e-2:
                bad.append(("csv_mismatch", key, ipc, mpki, r["ipc"], r["llc_mpki"]))

    print("json_count", len(glob.glob(os.path.join(args.root, "*", "*.json"))))
    print("expected_runs", len(args.traces) * len(args.policies))
    print("bad", bad if bad else "NONE")
    for pol in args.policies:
        if pol == args.baseline:
            continue
        speedups, ratios = [], []
        for tr in args.traces:
            if (tr, args.baseline) not in rows or (tr, pol) not in rows:
                continue
            lru = rows[(tr, args.baseline)]
            cur = rows[(tr, pol)]
            speedups.append((cur[0] / cur[1]) / (lru[0] / lru[1]))
            ratios.append((cur[2] / cur[0]) / (lru[2] / lru[0]))
        if speedups:
            geo = lambda v: math.exp(sum(math.log(x) for x in v) / len(v))
            print(pol, "ipc_geo", round(geo(speedups), 4), "mpki_geo", round(geo(ratios), 4))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())