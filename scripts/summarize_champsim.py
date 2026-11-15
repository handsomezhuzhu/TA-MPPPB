#!/usr/bin/env python3
"""把 ChampSim 的 JSON 输出汇总为 CSV。

用法: summarize_champsim.py <json_root> <out.csv>
json_root 结构: <root>/<policy>/<trace>.json
"""
import csv
import json
import os
import sys


def llc_parts(block):
    """返回 (access, miss)，统计 LLC 上所有请求类型。"""
    acc = miss = 0
    for access_type in ("LOAD", "RFO", "WRITE", "PREFETCH", "TRANSLATION"):
        d = block.get(access_type, {})
        acc += sum(d.get("hit", [])) + sum(d.get("miss", []))
        miss += sum(d.get("miss", []))
    return acc, miss


def main(root, out_csv):
    rows = []
    for policy in sorted(os.listdir(root)):
        pdir = os.path.join(root, policy)
        if not os.path.isdir(pdir):
            continue
        for fn in sorted(os.listdir(pdir)):
            if not fn.endswith(".json"):
                continue
            trace = fn[:-5]
            try:
                data = json.load(open(os.path.join(pdir, fn)))
                sim = data[0]["sim"]
            except Exception as e:  # JSON 不完整/仿真中断
                print(f"skip {policy}/{trace}: {e}", file=sys.stderr)
                continue
            acc, miss = llc_parts(sim.get("LLC", {}))
            core = sim.get("cores", [{}])[0]
            instr = core.get("instructions", 0) or 0
            cycles = core.get("cycles", 0) or 0
            dram = sim.get("DRAM", [{}])
            rows.append(
                {
                    "trace": trace,
                    "policy": policy,
                    "instructions": instr,
                    "cycles": cycles,
                    "ipc": round(instr / cycles, 4) if cycles else "",
                    "llc_access": acc,
                    "llc_miss": miss,
                    "llc_mpki": round(miss * 1000 / instr, 4) if instr else "",
                    "dram_cycles": dram[0].get("AVG DBUS CONGESTED CYCLE", "") if dram else "",
                }
            )
    rows.sort(key=lambda r: (r["trace"], r["policy"]))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["trace"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_csv}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])