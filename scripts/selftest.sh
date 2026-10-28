#!/bin/bash
# 道具を全部、見本のデータで1回ずつ動かす（ネットにつながない）。最後に「落ちた道具 0本」と出れば正常
cd "$(dirname "$0")/.." || exit 1
ochi=0
tmp=$(mktemp)
work=$(mktemp -d)
t() {
  local want=$1 name=$2; shift 2
  "$@" > "$tmp" 2>&1; local rc=$?
  if [ "$rc" = "$want" ]; then echo "  ok  $name"; else echo "  NG  ${name}（終了コード ${rc}／期待 ${want}）"; tail -5 "$tmp" | sed 's/^/      /'; ochi=$((ochi+1)); fi
}
echo "経費キットの試し運転（書き出し先 ${work}）"
t 0 "明細の読み込み" python3 scripts/meisai_yomu.py samples/card_meisai.csv --kouza 見本カード --out "$work/meisai.jsonl"
t 0 "領収書の記録の確かめ" python3 scripts/ryoushuu_kensa.py samples/ryoushuu.jsonl --out "$work/ryoushuu.jsonl"
t 0 "まとめと重複" python3 scripts/chofuku.py "$work/meisai.jsonl" "$work/ryoushuu.jsonl" --out "$work/matome.jsonl"
t 0 "科目と税区分の案" python3 scripts/kamoku_an.py "$work/matome.jsonl" --out "$work/an.jsonl"
t 0 "按分" python3 scripts/anbun.py "$work/an.jsonl" --out "$work/anbun.jsonl"
t 0 "freee 用 CSV" python3 scripts/export_freee.py "$work/anbun.jsonl" --out "$work/freee.csv"
t 0 "freee 用 CSV（Shift_JIS）" python3 scripts/export_freee.py "$work/anbun.jsonl" --out "$work/freee_sjis.csv" --sjis
t 0 "MF 用 CSV" python3 scripts/export_mf.py "$work/anbun.jsonl" --out "$work/mf.csv"
t 0 "freee API（試し運転）" python3 scripts/freee_api.py "$work/anbun.jsonl"
t 0 "保存の一覧（試し運転）" python3 scripts/hozon_index.py "$work/an.jsonl"
python3 - "$work" <<'PY' || ochi=$((ochi+1))
import csv, json, sys
w = sys.argv[1]
rows = [json.loads(l) for l in open(f"{w}/anbun.jsonl", encoding="utf-8")]
m = [json.loads(l) for l in open(f"{w}/meisai.jsonl", encoding="utf-8")]
assert len(m) == 9, len(m)                                   # 合計の行を外して9件
assert sum(r["amount"] for r in m) == 143090                 # CSV の合計と1円まで同じ
cafe = [r for r in rows if "カフェ" in r["mise"]]
assert len(cafe) == 2 and all(any("同じ日" in k for k in r["kakunin"]) for r in cafe)   # 消さずに要確認
assert sum(1 for r in rows if r.get("ryoushuu_id")) == 2     # 領収書2枚が明細につながった
mob = [r for r in rows if r["mise"] == "見本モバイル"][0]
assert sum(p["amount"] for p in mob["anbun"]) == 6000        # 按分の合計が元と同じ
big = [r for r in rows if r["amount"] >= 100000][0]
assert any("資産" in k for k in big["kakunin"])               # 高額は要確認
hdr = next(csv.reader(open(f"{w}/freee.csv", encoding="utf-8-sig")))
assert hdr[:3] == ["収支区分", "管理番号", "発生日"] and "決済口座" in hdr
hdr = next(csv.reader(open(f"{w}/mf.csv", encoding="utf-8-sig")))
assert len(hdr) == 27 and hdr[0] == "取引No" and hdr[-1] == "最終更新者"
open(f"{w}/freee_sjis.csv", encoding="cp932").read()
print("  ok  中身の検算（件数・合計・つながり・按分・高額・列）")
PY
rm -rf "$tmp" "$work"
echo "落ちた道具 ${ochi}本"
[ "$ochi" = 0 ]
