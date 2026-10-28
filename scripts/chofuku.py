#!/usr/bin/env python3
"""明細と領収書を1つにまとめ、二重の計上と重複らしいものを見つける（ネットにつながない）

  python3 scripts/chofuku.py out/meisai.jsonl out/ryoushuu.jsonl --out out/matome.jsonl
  python3 scripts/chofuku.py out/*.jsonl --out out/matome.jsonl --hi 5      # 日付のずれを5日まで許す

考え方
  1. 同じ記録（同じ id）を2回読み込んだもの → 1件にする（読み込みの重ね）
  2. 領収書と明細が同じ買い物 → 明細の行に領収書をつなぎ、1件にする（2回計上しない）
       金額が同じ ／ 日付のずれが --hi 日以内（カードは利用日と計上日がずれる）／ 店の名前が似ている
       1本の明細には領収書を1枚だけつなぐ（件数でつなぐ）
  3. 同じ日・同じ店・同じ金額が複数 → 消さない。本当に2回買ったことがあるので「要確認」で並べる
  4. つながらなかった領収書 → 現金払い・別のカードの可能性。要確認（支払いが「現金」の領収書は除く）
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
from collections import defaultdict
from datetime import date

import kit


def norm(s):
    s = kit.seiki(s).upper()
    for w in ("株式会社", "(株)", "（株）", "有限会社", "店", " ", "　", "・", "-", "_"):
        s = s.replace(w, "")
    return s


def niteru(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    ga = {a[i:i + 2] for i in range(len(a) - 1)} or {a}
    gb = {b[i:i + 2] for i in range(len(b) - 1)} or {b}
    return len(ga & gb) / len(ga | gb)


def days(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return 999


def main():
    ap = argparse.ArgumentParser(description="明細と領収書をまとめる")
    ap.add_argument("jsonl", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hi", type=int, default=3, help="日付のずれを何日まで同じ買い物とみるか")
    ap.add_argument("--niteru", type=float, default=0.3, help="店の名前がどれだけ似ていれば同じとみるか（0〜1）")
    a = ap.parse_args()

    seen, rows, kasane = set(), [], 0
    for p in a.jsonl:
        for r in kit.read_jsonl(p):
            if r["id"] in seen:
                kasane += 1
                continue
            seen.add(r["id"])
            r.setdefault("kakunin", [])
            rows.append(r)
    lines = [r for r in rows if r.get("source") in ("card", "bank")]
    recs = [r for r in rows if r.get("source") == "ryoushuu"]

    # 2. 領収書 → 明細（候補の良い順に1対1）
    cands = []
    for i, rc in enumerate(recs):
        if not isinstance(rc.get("amount"), int):
            continue
        for j, ln in enumerate(lines):
            if ln["amount"] != rc["amount"]:
                continue
            dd = days(ln["date"], rc.get("date"))
            if dd > a.hi:
                continue
            sim = niteru(ln.get("mise"), rc.get("mise"))
            if sim < a.niteru:
                continue
            cands.append((dd, -sim, i, j))
    cands.sort()
    used_r, used_l = set(), set()
    for dd, nsim, i, j in cands:
        if i in used_r or j in used_l:
            continue
        used_r.add(i)
        used_l.add(j)
        ln, rc = lines[j], recs[i]
        for f in ("file", "invoice_no", "uchiwake", "zeiritsu", "naiyou", "dousekisha", "yomi"):
            if rc.get(f) not in (None, "", {}):
                ln[f] = rc[f]
        ln["ryoushuu_id"] = rc["id"]
        ln["kakunin"] = ln["kakunin"] + [k for k in rc.get("kakunin", []) if k not in ln["kakunin"]]
        if dd:
            ln["kakunin"].append(f"領収書の日付と明細の日付が {dd} 日ずれている（計上日のずれか確かめる）")

    out = []
    for j, ln in enumerate(lines):
        if j not in used_l:
            ln["ryoushuu_nashi"] = True
        out.append(ln)
    tanpin = 0
    for i, rc in enumerate(recs):
        if i in used_r:
            continue
        if (rc.get("kouza") or "") != "現金":
            rc["kakunin"].append("明細とつながらない（現金払いか・別のカードか・明細がまだ来ていないか）")
        tanpin += 1
        out.append(rc)

    # 3. 同じ日・同じ店・同じ額
    g = defaultdict(list)
    for r in out:
        g[(r.get("kouza"), r.get("date"), norm(r.get("mise")), r.get("amount"))].append(r)
    nijuu = 0
    for key, rs in g.items():
        if len(rs) > 1:
            nijuu += 1
            for r in rs:
                r["kakunin"].append(f"同じ日・同じ店・同じ額が {len(rs)} 件（2回買ったのか、重なりか）")

    out.sort(key=lambda r: (r.get("date") or "", r.get("mise") or ""))
    kit.write_jsonl(a.out, out)
    nashi = sum(1 for r in out if r.get("ryoushuu_nashi"))
    print(f"明細 {len(lines)} 件 ＋ 領収書 {len(recs)} 件 → まとめて {len(out)} 件")
    print(f"  つながった {len(used_r)} 件 ／ 領収書だけ {tanpin} 件 ／ 領収書の無い明細 {nashi} 件")
    print(f"  同じ日・同じ店・同じ額の組 {nijuu} 組（消していない）／ 同じ記録の読み込み重ね {kasane} 件（1件にした）")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
