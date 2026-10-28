#!/usr/bin/env python3
"""エージェントが領収書の画像を読んで書いた記録を確かめ、形をそろえる（ネットにつながない）

  python3 scripts/ryoushuu_kensa.py data/ryoushuu.jsonl --out out/ryoushuu.jsonl

記録の書き方は templates/ryoushuu-kiroku.md。1枚1行。
確かめること
  日付・金額・店が読めているか／金額が整数か
  登録番号が「T＋13桁」か（無い・形が違う → 要確認）
  税率ごとの内訳（uchiwake）があるとき、合計が金額と合うか
  読みの確からしさ（yomi: 高/中/低）が「低」、または yomenai に何か書いてある → 要確認
  ファイル（file）が実際にあるか
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import re
from pathlib import Path

import kit

T_RE = re.compile(r"^T\d{13}$")


def main():
    ap = argparse.ArgumentParser(description="領収書の記録を確かめる")
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = kit.read_jsonl(a.jsonl)
    base = Path(a.jsonl).resolve().parent
    out, n_kaku = [], 0
    for i, r in enumerate(rows, 1):
        kk = list(r.get("kakunin") or [])
        d = r.get("date")
        if not d or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d)):
            kk.append("日付が読めていない（YYYY-MM-DD）")
        amt = r.get("amount")
        if not isinstance(amt, int):
            kk.append("金額が整数で入っていない")
        if not r.get("mise"):
            kk.append("店・発行元が読めていない")
        inv = kit.seiki(str(r.get("invoice_no") or "")).replace("-", "").replace(" ", "").upper()
        if not inv:
            kk.append("登録番号が無い（インボイスでない・読めない）")
        elif not T_RE.match(inv):
            kk.append(f"登録番号の形が違う（{inv}）")
        uchi = r.get("uchiwake") or {}
        if uchi and isinstance(amt, int):
            s = sum(int(v) for v in uchi.values())
            if s != amt:
                kk.append(f"税率ごとの内訳の合計 {s:,} 円が金額 {amt:,} 円と合わない")
        if r.get("yomi") == "低" or r.get("yomenai"):
            kk.append("読み取りが怪しい：" + str(r.get("yomenai") or "確からしさ 低"))
        f = r.get("file")
        rid = r.get("id") or kit.make_id("ryoushuu", d, r.get("mise"), amt, f, i)
        if f:
            if (base / f).exists():
                f = str((base / f).resolve())
            elif Path(f).exists():
                f = str(Path(f).resolve())
            else:
                kk.append(f"ファイルが見つからない（{f}）")
        rec = {**r, "file": f, "source": "ryoushuu", "invoice_no": inv or None, "kakunin": kk,
               "id": rid}
        rec.setdefault("kouza", r.get("shiharai") or "")
        if kk:
            n_kaku += 1
        out.append(rec)
    kit.write_jsonl(a.out, out)
    print(f"領収書 {len(out)} 件 → 要確認 {n_kaku} 件 → {a.out}")
    for r in out:
        if r["kakunin"]:
            print(f"  [{r.get('date')} {r.get('mise')} {kit.yen(r.get('amount')) if isinstance(r.get('amount'), int) else '金額？'}] " + "／".join(r["kakunin"]))


if __name__ == "__main__":
    main()
