#!/usr/bin/env python3
"""Analyze ChampSim JSON + g_probe logs across policies for causal attribution & comparison."""
import argparse
import csv
import json
import math
import pathlib
import re

TRACES = [
    "400.perlbench-41B", "403.gcc-16B", "410.bwaves-945B", "429.mcf-22B",
    "437.leslie3d-134B", "450.soplex-92B", "470.lbm-1274B", "483.xalancbmk-127B",
]
TYPES = ("LOAD", "RFO", "PREFETCH", "WRITE", "TRANSLATION")

RE_PROBE = re.compile(
    r"mpppb: fills=(\d+) matched=(\d+) unmatched=(\d+) bypass=(\d+) promote=(\d+) keep=(\d+) buckets\([^)]*\)=([\d,]+)"
)
RE_TA = re.compile(
    r"mpppb_ta: demand_bypass=(\d+) pref_bypass=(\d+) write_fills=(\d+) trans_access=(\d+) trans_hit=(\d+) trans_fills=(\d+)"
)
RE_DET = re.compile(
    r"mpppb_detail: demand_fills=(\d+) pref_fills=(\d+) trans_bypass=(\d+) write_samp_hit=(\d+) "
    r"write_samp_miss=(\d+) pref_samp_hit=(\d+) pref_samp_miss=(\d+) psel=(-?\d+)"
)


def parse_run(jpath: pathlib.Path, lpath: pathlib.Path):
    sim = json.loads(jpath.read_text())[0]["sim"]
    core = sim["cores"][0]
    instr = core["instructions"]
    cycles = core["cycles"]
    llc = sim["LLC"]
    out = {
        "instructions": instr,
        "cycles": cycles,
        "ipc": instr / cycles if cycles else 0.0,
        "llc_miss": sum(sum(llc[t]["miss"]) for t in TYPES),
        "llc_access": sum(sum(llc[t]["hit"]) + sum(llc[t]["miss"]) for t in TYPES),
    }
    for t in TYPES:
        h = sum(llc[t]["hit"])
        m = sum(llc[t]["miss"])
        out[f"{t.lower()}_hit"] = h
        out[f"{t.lower()}_miss"] = m
    if lpath.exists():
        txt = lpath.read_text(errors="ignore")
        ms = RE_PROBE.findall(txt)
        if ms:
            f, ma, un, bp, pr, kp, bks = ms[-1]
            out.update({"fills": int(f), "matched": int(ma), "bypass": int(bp), "promote": int(pr), "keep": int(kp), "buckets": bks})
        ta = RE_TA.findall(txt)
        if ta:
            db, pb, wf, ta_a, ta_h, tf = ta[-1]
            out.update({
                "demand_bypass": int(db), "pref_bypass": int(pb),
                "write_fills": int(wf), "trans_fills": int(tf),
            })
        det = RE_DET.findall(txt)
        if det:
            df, pf, tb, wsh, wsm, psh, psm, psel = det[-1]
            out.update({
                "demand_fills": int(df), "pref_fills": int(pf), "trans_bypass": int(tb),
                "write_samp_hit": int(wsh), "write_samp_miss": int(wsm),
                "pref_samp_hit": int(psh), "pref_samp_miss": int(psm), "psel": int(psel),
            })
    return out


def geomean(vals):
    vals = [v for v in vals if v > 0]
    return math.exp(sum(math.log(v) for v in vals) / len(vals)) if vals else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", required=True, help="Directories containing <policy>/<trace>.json")
    ap.add_argument("--baseline", required=True, help="Baseline policy name")
    ap.add_argument("--policies", nargs="+", default=None, help="Ordered list of policies to print")
    ap.add_argument("--csv", default=None, help="Optional flat CSV export path")
    args = ap.parse_args()

    data = {}
    for r in args.roots:
        rp = pathlib.Path(r)
        if not rp.exists():
            continue
        for pdir in sorted(rp.iterdir()):
            if not pdir.is_dir():
                continue
            pol = pdir.name
            for jp in sorted(pdir.glob("*.json")):
                tr = jp.stem
                if tr not in TRACES:
                    continue
                data[(pol, tr)] = parse_run(jp, jp.with_suffix(".log"))

    policies = args.policies or sorted({pol for pol, _ in data})
    if args.baseline not in {pol for pol, _ in data}:
        raise SystemExit(f"Baseline {args.baseline!r} not found")

    header = f"{'Policy':<18} {'GMeanIPC':>9} {'vsBase%':>8} | " + " ".join(f"{t.split('.')[1][:6]:>7}" for t in TRACES)
    print(header)
    print("-" * len(header))
    for pol in policies:
        ratios = []
        ipcs = []
        cells = []
        for tr in TRACES:
            if (pol, tr) not in data or (args.baseline, tr) not in data:
                cells.append("    N/A")
                continue
            r = data[(pol, tr)]["ipc"] / data[(args.baseline, tr)]["ipc"]
            ratios.append(r)
            ipcs.append(data[(pol, tr)]["ipc"])
            cells.append(f"{(r - 1.0)*100:+6.2f}%")
        gm_r = geomean(ratios)
        gm_i = geomean(ipcs)
        print(f"{pol:<18} {gm_i:9.4f} {(gm_r-1)*100:+7.2f}% | " + " ".join(cells))

    if args.csv:
        rows = []
        for pol in policies:
            for tr in TRACES:
                if (pol, tr) in data:
                    row = {"policy": pol, "trace": tr}
                    row.update(data[(pol, tr)])
                    rows.append(row)
        if rows:
            keys = list(dict.fromkeys(k for row in rows for k in row.keys()))
            with open(args.csv, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(rows)
            print("Wrote", len(rows), "rows ->", args.csv)


if __name__ == "__main__":
    main()
