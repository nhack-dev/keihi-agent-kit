#!/usr/bin/env python3
"""freee会計の「取引のインポート」用 CSV を作る（ネットにつながない・取り込むのは人）

  python3 scripts/export_freee.py out/anbun.jsonl --out out/freee_import.csv
  python3 scripts/export_freee.py out/anbun.jsonl --out out/freee_import.csv --sample freeeのサンプル.csv   # 列名を合わせる
  python3 scripts/export_freee.py out/anbun.jsonl --out out/freee_import.csv --sjis                       # 文字化けしたら

列（freee 公式ヘルプ「取引・口座振替のインポート（一括登録）」2026-09 更新版で確かめた並び）
  収支区分 管理番号 発生日 決済期日 取引先コード 取引先 勘定科目 税区分 金額 税計算区分 税額 備考 品目 部門 メモタグ 決済日 決済口座 決済金額
  ・1行目（ヘッダ）を消さない ・発生日 YYYY/MM/DD ・金額は税込 ・合計がマイナスの取引は入れられない
  ・収支区分を空にして上の行と発生日を合わせると複合（税率の違う行を1取引に）
  ・セグメント1〜3 は上位のプランだけ。使うときは --sample で自分のサンプルの列名を使う
  ・ファイルは 5MB まで。取り込みはすべて新しい取引になる（同じファイルを2回入れると二重になる）
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import csv
import io

import gyou
import kit

COLS = ["収支区分", "管理番号", "発生日", "決済期日", "取引先コード", "取引先", "勘定科目", "税区分", "金額",
        "税計算区分", "税額", "備考", "品目", "部門", "メモタグ", "決済日", "決済口座", "決済金額"]


def main():
    ap = argparse.ArgumentParser(description="freee 取引インポート用 CSV")
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", help="freee の画面から落としたサンプル CSV（列名をそれに合わせる）")
    ap.add_argument("--sjis", action="store_true", help="Shift_JIS で書く（既定は UTF-8 BOM つき）")
    ap.add_argument("--kakunin-mo", action="store_true", help="要確認の行も出す（メモタグに『要確認』）")
    a = ap.parse_args()

    k = gyou.kaikei_check()
    cols = COLS
    if a.sample:
        raw = open(a.sample, "rb").read()
        text = raw.decode("utf-8-sig", errors="strict") if raw[:3] == b"\xef\xbb\xbf" else raw.decode("cp932", errors="replace")
        cols = next(csv.reader(io.StringIO(text)))
        missing = [c for c in ("収支区分", "発生日", "勘定科目", "税区分", "金額") if c not in cols]
        if missing:
            raise SystemExit(f"止めます：サンプルに必須の列がありません：{missing}")
    rows = kit.read_jsonl(a.jsonl)
    dasu, dasanai = gyou.wakeru(rows, a.kakunin_mo)
    out, miss_zei, miss_kouza = [], set(), set()
    for r, parts in dasu:
        d = r["date"].replace("-", "/")
        kouza = (k["kouza"].get(r.get("kouza") or "") or {}).get("freee")
        if not kouza:
            miss_kouza.add(r.get("kouza") or "（空）")
        for n, (z, v) in enumerate(parts):
            zname = k["zei_freee"].get(z)
            if not zname:
                miss_zei.add(z)
            row = {c: "" for c in cols}
            row.update({
                "収支区分": "支出" if n == 0 else "", "管理番号": r["id"] if n == 0 else "", "発生日": d if n == 0 else "",
                "取引先": r.get("mise", "") if n == 0 else "", "勘定科目": r["kamoku"], "税区分": zname or "",
                "金額": v, "税計算区分": "内税", "備考": gyou.tekiyou(r) if n == 0 else "",
                "メモタグ": "要確認" if r.get("kakunin") else "",
                "決済日": d if n == 0 else "", "決済口座": (kouza or "") if n == 0 else "",
                "決済金額": sum(p[1] for p in parts) if n == 0 else "",
            })
            out.append({c: row.get(c, "") for c in cols})
    enc = "cp932" if a.sjis else "utf-8-sig"
    with open(a.out, "w", encoding=enc, newline="", errors="strict") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"取引 {len(dasu)} 件（行 {len(out)}）→ {a.out}（{enc}）")
    if miss_zei:
        print(f"※ 税区分の名前が config/kaikei.json に無い：{sorted(miss_zei)}（空欄で出した。取り込み前に決める）")
    if miss_kouza:
        print(f"※ 決済口座の名前が config/kaikei.json に無い：{sorted(miss_kouza)}（空欄で出した）")
    gyou.show_dasanai(dasanai)
    print("取り込む前に、オーナーが中身を確かめる。取り込みは freee の［取引］→［取引の一覧・登録］→［…］→［取引データのインポート］")


if __name__ == "__main__":
    main()
