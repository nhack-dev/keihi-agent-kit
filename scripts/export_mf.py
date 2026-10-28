#!/usr/bin/env python3
"""マネーフォワード クラウド会計の「仕訳帳のインポート」用 CSV を作る（ネットにつながない・取り込むのは人）

  python3 scripts/export_mf.py out/anbun.jsonl --out out/mf_import.csv
  python3 scripts/export_mf.py out/anbun.jsonl --out out/mf_import.csv --sjis

列（MF 公式ヘルプ「仕訳帳のインポート」2026-07-09 更新版で確かめた A〜AA 列）
  取引No 取引日 借方勘定科目 借方補助科目 借方部門 借方取引先 借方税区分 借方インボイス 借方金額(円) 借方税額
  貸方勘定科目 貸方補助科目 貸方部門 貸方取引先 貸方税区分 貸方インボイス 貸方金額(円) 貸方税額
  摘要 仕訳メモ タグ MF仕訳タイプ 決算整理仕訳 作成日時 作成者 最終更新日時 最終更新者
  ・必須は 取引日・勘定科目・金額 ・取引日は yyyy/MM/dd ・税額は 0 か空欄（空欄にする）
  ・取引No と取引日が同じで貸借の合計が合う行は複合仕訳になる（税率の違う行をまとめる）
  ・最後の4列は入力不要 ・取り込むたびに新しい仕訳になる（2回入れると二重）
  ・「借方インボイス」が空欄だと適格とみなされる → 登録番号の無い仕入れは config/kaikei.json の mf_invoice.nai を入れる
  ・公式は「指定のサンプルフォーマットを使い、1行目を編集しない」としている。取り込みで止まったら画面のサンプルと列名を比べる
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import csv

import gyou
import kit

COLS = ["取引No", "取引日", "借方勘定科目", "借方補助科目", "借方部門", "借方取引先", "借方税区分", "借方インボイス",
        "借方金額(円)", "借方税額", "貸方勘定科目", "貸方補助科目", "貸方部門", "貸方取引先", "貸方税区分", "貸方インボイス",
        "貸方金額(円)", "貸方税額", "摘要", "仕訳メモ", "タグ", "MF仕訳タイプ", "決算整理仕訳", "作成日時", "作成者",
        "最終更新日時", "最終更新者"]


def main():
    ap = argparse.ArgumentParser(description="MF 仕訳帳インポート用 CSV")
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sjis", action="store_true")
    ap.add_argument("--kakunin-mo", action="store_true", help="要確認の行も出す（タグに『要確認』）")
    a = ap.parse_args()
    k = gyou.kaikei_check()
    dasu, dasanai = gyou.wakeru(kit.read_jsonl(a.jsonl), a.kakunin_mo)
    out, miss = [], set()
    for no, (r, parts) in enumerate(dasu, 1):
        kz = k["kouza"].get(r.get("kouza") or "") or {}
        if not kz:
            miss.add(r.get("kouza") or "（空）")
        inv = k["mf_invoice"]["aru"] if r.get("invoice_no") else k["mf_invoice"]["nai"]
        for z, v in parts:
            row = {c: "" for c in COLS}
            row.update({
                "取引No": no, "取引日": r["date"].replace("-", "/"),
                "借方勘定科目": r["kamoku"], "借方取引先": r.get("mise", ""),
                "借方税区分": k["zei_mf"].get(z, ""), "借方インボイス": inv, "借方金額(円)": v,
                "貸方勘定科目": kz.get("mf_kamoku", ""), "貸方補助科目": kz.get("mf_hojo", ""),
                "貸方税区分": k["zei_mf"].get("taishougai", ""), "貸方金額(円)": v,
                "摘要": gyou.tekiyou(r), "仕訳メモ": r["id"], "タグ": "要確認" if r.get("kakunin") else "",
            })
            out.append(row)
    enc = "cp932" if a.sjis else "utf-8-sig"
    with open(a.out, "w", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    print(f"仕訳 {len(dasu)} 件（行 {len(out)}）→ {a.out}（{enc}）")
    if miss:
        print(f"※ 支払いの口座が config/kaikei.json に無い：{sorted(miss)}（貸方を空欄で出した）")
    if k["mf_invoice"]["nai"] == "要確認":
        print("※ 登録番号の無い仕入れのインボイス列が『要確認』のままです（このままだと取り込みで止まります）。国税庁・税理士で今の扱いを確かめて config/kaikei.json に入れる")
    gyou.show_dasanai(dasanai)
    print("取り込む前に、オーナーが中身を確かめる。取り込みは MF の［仕訳帳］→［インポート］")


if __name__ == "__main__":
    main()
