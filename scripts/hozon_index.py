#!/usr/bin/env python3
"""領収書・請求書の保存の一覧（取引年月日・取引金額・取引先で探せる表）と、決まった名前の写しを作る

  python3 scripts/hozon_index.py out/an.jsonl                      # 試し運転：一覧と名前の案だけ
  python3 scripts/hozon_index.py out/an.jsonl --go --dir hozon     # 写しを hozon/ に作り、一覧を書く

  国税庁の電子帳簿保存法 一問一答（電子取引関係）は、検索の条件として「取引年月日・取引金額・取引先」を
  挙げ、表計算ソフトで一覧を作って探せる形にする方法や、ファイル名に決まった形で項目を入れる方法も示している。
  このキットはその両方を作る（要件を満たすかの最終判断は、国税庁の案内か税理士で確かめる）。
  元のファイルは消さない・書き換えない。写しの名前 … YYYYMMDD_金額_取引先.拡張子
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import csv
import re
import shutil
from pathlib import Path

import kit


def safe(s):
    s = re.sub(r'[\\/:*?"<>|\s]+', "", kit.seiki(s))
    return s[:40] or "不明"


def main():
    ap = argparse.ArgumentParser(description="保存の一覧と写し")
    ap.add_argument("jsonl")
    ap.add_argument("--dir", default="hozon")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    rows = [r for r in kit.read_jsonl(a.jsonl) if r.get("file")]
    dest = kit.HOME / a.dir
    plan, used = [], set()
    for r in rows:
        src = Path(r["file"])
        name = f"{(r.get('date') or '').replace('-', '')}_{r.get('amount')}_{safe(r.get('mise'))}{src.suffix.lower()}"
        base, n = name, 2
        while name in used:
            name = base.replace(src.suffix.lower(), f"_{n}{src.suffix.lower()}")
            n += 1
        used.add(name)
        plan.append((r, src, name))
    if not a.go:
        print(f"試し運転です。ファイルのある記録 {len(plan)} 件：")
        for r, src, name in plan[:20]:
            print(f"  {src} → {a.dir}/{name}" + ("" if src.exists() else "  ※ 元のファイルが見つからない"))
        print("--go で写しと一覧（hozon/ichiran.csv）を作る（元のファイルは触らない）")
        return
    dest.mkdir(parents=True, exist_ok=True)
    n_ok, miss = 0, []
    for r, src, name in plan:
        if not src.exists():
            miss.append(str(src))
            continue
        if not (dest / name).exists():
            shutil.copy2(src, dest / name)
        n_ok += 1
    with open(dest / "ichiran.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["取引年月日", "取引金額", "取引先", "登録番号", "科目の案", "保存の名前", "元のファイル"])
        for r, src, name in plan:
            w.writerow([r.get("date"), r.get("amount"), r.get("mise"), r.get("invoice_no") or "", r.get("kamoku") or "", name, str(src)])
    print(f"写した {n_ok} 件 ／ 元が無い {len(miss)} 件 → {dest}/ と {dest}/ichiran.csv")
    for m in miss[:10]:
        print("  見つからない：" + m)


if __name__ == "__main__":
    main()
