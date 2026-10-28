#!/usr/bin/env python3
"""カード・銀行の明細 CSV を読み込み、記録の形（.jsonl）にそろえる（ネットにつながない）

  python3 scripts/meisai_yomu.py samples/card_meisai.csv --kouza 見本カード --out out/meisai.jsonl
  python3 scripts/meisai_yomu.py data/bank.csv --kouza 普通預金 --source bank --out out/bank.jsonl

  文字コードは UTF-8（BOM あり・なし）→ Shift_JIS（cp932）の順に試す。
  列名は config/csv_katachi.json の候補から探す。見つからなければ止まって、1行目の列名を見せる。
  金額の「1,234」「¥1,234」「-1,234」「(1,234)」を読む。マイナス（返金・取り消し）は要確認にする。
  合計・小計の行は読まない。同じ行は同じ id になる（読み直しても増えない）。
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import csv
import io
import re
import sys
from datetime import datetime

import kit


def open_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    sys.exit("止めます：文字コードが UTF-8 でも Shift_JIS でもありません")


def find_header(rows, k):
    """最初の数行から、日付と金額の列名がそろう行を見つける（カード会社の CSV は上に案内の行があることが多い）。"""
    for i, row in enumerate(rows[:15]):
        cells = [kit.seiki(c) for c in row]
        if any(n in cells for n in k["date"]) and (any(n in cells for n in k["amount"]) or any(n in cells for n in k["nyukin"])):
            return i, cells
    return None, None


def col(cells, names):
    for n in names:
        if n in cells:
            return cells.index(n)
    return None


def parse_date(s):
    s = kit.seiki(s).replace("年", "/").replace("月", "/").replace("日", "").replace("-", "/").replace(".", "/")
    for fmt in ("%Y/%m/%d", "%y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s.split(" ")[0], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_amount(s):
    s = kit.seiki(s).replace(",", "").replace("¥", "").replace("円", "").replace("\\", "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    v = int(round(float(s)))
    return -v if neg else v


def main():
    ap = argparse.ArgumentParser(description="明細 CSV を読み込む")
    ap.add_argument("csv")
    ap.add_argument("--kouza", required=True, help="このカード・口座の名前（config/kaikei.json の kouza と同じ名前）")
    ap.add_argument("--source", default="card", choices=["card", "bank"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    k = kit.config("csv_katachi")
    text, enc = open_text(a.csv)
    rows = list(csv.reader(io.StringIO(text)))
    hi, cells = find_header(rows, k)
    if hi is None:
        print("止めます：日付と金額の列が見つかりません。1行目〜3行目：")
        for r in rows[:3]:
            print("  ", r)
        sys.exit("→ config/csv_katachi.json の候補に、この CSV の列名を足してください")
    ci = {f: col(cells, k[f]) for f in ("date", "mise", "amount", "nyukin", "memo")}
    out, skip, ng = [], 0, []
    for n, row in enumerate(rows[hi + 1:], hi + 2):
        if not any(c.strip() for c in row):
            continue
        g = lambda f: row[ci[f]] if ci[f] is not None and ci[f] < len(row) else ""
        mise = kit.seiki(g("mise"))
        if any(mise.startswith(w) for w in k["skip_mise"]):
            skip += 1
            continue
        d = parse_date(g("date"))
        amt = parse_amount(g("amount"))
        if amt is None and ci["nyukin"] is not None:
            nyu = parse_amount(g("nyukin"))
            amt = -nyu if nyu is not None else None
        if d is None or amt is None:
            ng.append(n)
            continue
        rec = {"id": kit.make_id(a.kouza, d, mise, amt, n), "date": d, "amount": amt, "mise": mise,
               "source": a.source, "kouza": a.kouza, "memo": kit.seiki(g("memo")), "kakunin": []}
        if amt < 0:
            rec["kakunin"].append("マイナス（返金・取り消し・入金）。元の取引とつなぐ")
        out.append(rec)
    kit.write_jsonl(a.out, out)
    print(f"読んだ {len(out)} 件（文字コード {enc}・列の行 {hi + 1} 行目）／合計の行を外した {skip} 件／読めない行 {len(ng)} 件")
    if ng:
        print("  読めない行の番号：" + ", ".join(map(str, ng[:20])) + ("…" if len(ng) > 20 else ""))
        print("  → 日付か金額の形が違います。CSV を開いて確かめ、推測で埋めないでください")
    print(f"合計 {kit.yen(sum(r['amount'] for r in out))} → {a.out}")


if __name__ == "__main__":
    main()
