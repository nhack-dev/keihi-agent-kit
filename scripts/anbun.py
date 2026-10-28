#!/usr/bin/env python3
"""按分の決まり（config/anbun.json）に当たる行を、割合で分ける（ネットにつながない）

  python3 scripts/anbun.py out/an.jsonl --out out/anbun.jsonl

  決まりのある行だけ分ける。決まりの無い行はそのまま（勝手に割合を決めない）。
  分けた結果は anbun: [{"saki": "事業", "amount": 3600}, {"saki": "私用", "amount": 2400}] で持つ。
  1円未満の端数は kiri の決まりで寄せる。分けた合計は元の金額と1円まで同じになる。
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import re

import kit


def wakeru(amount, wariai, kiri):
    names = list(wariai)
    parts = [int(amount * wariai[n]) for n in names]  # 切り捨て
    rest = amount - sum(parts)
    idx = 0 if kiri == "jigyou" else len(parts) - 1
    parts[idx] += rest
    return [{"saki": n, "amount": p} for n, p in zip(names, parts)]


def main():
    ap = argparse.ArgumentParser(description="按分")
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = kit.config("anbun")
    rows, n = [], 0
    for r in kit.read_jsonl(a.jsonl):
        text = kit.seiki(f"{r.get('mise', '')} {r.get('memo', '')}")
        for rule in cfg["rules"]:
            if re.search(rule["re"], text, flags=re.IGNORECASE) and isinstance(r.get("amount"), int):
                s = sum(rule["wariai"].values())
                if abs(s - 1) > 1e-9:
                    raise SystemExit(f"止めます：按分の割合の合計が 1 ではありません（{rule['re']}：{s}）")
                r["anbun"] = wakeru(r["amount"], rule["wariai"], cfg["kiri"])
                r["anbun_riyuu"] = rule.get("riyuu", "")
                assert sum(p["amount"] for p in r["anbun"]) == r["amount"]
                r["kakunin"] = [k for k in r.get("kakunin", []) if not k.startswith("私用と混ざりやすい")]
                n += 1
                break
        rows.append(r)
    kit.write_jsonl(a.out, rows)
    print(f"{len(rows)} 件のうち 按分した {n} 件（決まりのある行だけ）→ {a.out}")
    for r in rows:
        if r.get("anbun"):
            print(f"  {r['date']} {r['mise']} {kit.yen(r['amount'])} → " + "／".join(f"{p['saki']} {kit.yen(p['amount'])}" for p in r["anbun"]))


if __name__ == "__main__":
    main()
