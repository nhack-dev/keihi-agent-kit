#!/usr/bin/env python3
"""1件ずつ勘定科目と税区分の「案」を出す（ネットにつながない・決めるのは人）

  python3 scripts/kamoku_an.py out/matome.jsonl --out out/an.jsonl

案の出し方（上から順に）
  1. config/kamoku_kimari.json の jigyou_igai に当たる → 「事業以外」（確からしさ 高・オーナーの決まり）
  2. config/kamoku_kimari.json の mise に当たる       → その科目（確からしさ 高・オーナーの決まり）
  3. config/kamoku_ippan.json の rules に当たる        → 一般的な案（確からしさ 低・必ず人が見る）
  4. どれにも当たらない                               → 案なし（要確認）
いつも「要確認」にするもの … 高額・飲食・私用と混ざりやすいもの・マイナス・登録番号なし・読み取りが怪しい

税区分（zei）の記号 … kazei10 / kazei8 / hikazei / taishougai / fumei（分からない）
  領収書に税率ごとの内訳（uchiwake: {"10": 金額, "8": 金額}）があれば、それを優先して zei_uchiwake に分ける。
  会計ソフトの税区分の名前への読み替えは export_*.py が config/kaikei.json で行う。
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import re

import kit


def match(rules, text):
    for r in rules:
        if re.search(r["re"], text, flags=re.IGNORECASE):
            return r
    return None


def an(r, kimari, ippan):
    text = kit.seiki(f"{r.get('mise', '')} {r.get('memo', '')} {r.get('naiyou', '')}").upper()
    kk = list(r.get("kakunin") or [])
    out = {"kamoku": None, "zei": "fumei", "kakushin": "なし", "riyuu": ""}
    hit = match(kimari.get("jigyou_igai", []), text)
    if hit:
        out.update(kamoku="事業以外", zei="taishougai", kakushin="高", riyuu="オーナーの決まり：" + hit.get("riyuu", ""))
    else:
        hit = match(kimari.get("mise", []), text)
        if hit:
            out.update(kamoku=hit["kamoku"], zei=hit.get("zei", "fumei"), kakushin="高",
                       riyuu="オーナーの決まり（" + hit.get("kimeta", "") + "）" + (("／" + hit["riyuu"]) if hit.get("riyuu") else ""))
        else:
            hit = match(ippan["rules"], text)
            if hit:
                out.update(kamoku=hit["kamoku"], zei=hit.get("zei", "fumei"), kakushin="低", riyuu="店の名前からの一般的な案")
                kk.append("決まりが無い一般的な案（科目を確かめる）" + (("：" + hit["kakunin"]) if hit.get("kakunin") else ""))
                if hit.get("inshoku") and not r.get("dousekisha"):
                    kk.append("飲食：会議か接待か・人数・相手をオーナーに聞く")
            else:
                kk.append("科目の案が出せない（店の名前だけでは分からない。何を買ったかを聞く）")
    amt = r.get("amount") if isinstance(r.get("amount"), int) else 0
    if out["kamoku"] != "事業以外":
        if amt >= ippan["takagaku_en"]:
            kk.append(f"1件 {amt:,} 円：資産として扱うか（減価償却）を税理士に確かめる")
        if any(w.upper() in text for w in ippan["shiyou_majiri"]):
            kk.append("私用と混ざりやすい（按分の決まり anbun.json があるか確かめる）")
    chuui = list(r.get("chuui") or [])
    if r.get("ryoushuu_nashi") and amt > 0 and out["kamoku"] != "事業以外":
        chuui.append("領収書が無い（登録番号を確かめられない・08-hozon.md）")
    out["chuui"] = chuui
    uchi = r.get("uchiwake") or {}
    if uchi:
        zu = {}
        for k, v in uchi.items():
            key = {"10": "kazei10", "8": "kazei8", "0": "taishougai"}.get(str(k), "fumei")
            zu[key] = zu.get(key, 0) + int(v)
        out["zei_uchiwake"] = zu
        if len(zu) == 1:
            out["zei"] = next(iter(zu))
    elif str(r.get("zeiritsu")) == "8" and out["zei"] == "kazei10":
        out["zei"] = "kazei8"
    if out["zei"] == "fumei" and out["kamoku"] not in (None, "事業以外"):
        kk.append("税区分が分からない（国内・国外・非課税のどれか確かめる）")
    seen = []
    for x in kk:
        if x not in seen:
            seen.append(x)
    return {**r, **out, "kakunin": seen, "an": True}


def main():
    ap = argparse.ArgumentParser(description="科目と税区分の案")
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kimari, ippan = kit.config("kamoku_kimari"), kit.config("kamoku_ippan")
    rows = [an(r, kimari, ippan) for r in kit.read_jsonl(a.jsonl)]
    kit.write_jsonl(a.out, rows)
    kaku = [r for r in rows if r["kakunin"]]
    kei = {}
    for r in rows:
        kei[r["kamoku"] or "（案なし）"] = kei.get(r["kamoku"] or "（案なし）", 0) + (r["amount"] or 0)
    print(f"{len(rows)} 件 → 決まりで決まった {sum(1 for r in rows if r['kakushin'] == '高')} ／ 一般的な案 {sum(1 for r in rows if r['kakushin'] == '低')} ／ 案なし {sum(1 for r in rows if r['kakushin'] == 'なし')}")
    print(f"要確認 {len(kaku)} 件（オーナーに見てもらう・templates/kakunin-hyou.md）")
    print(f"注意（取り込みは止めない）{sum(1 for r in rows if r.get('chuui'))} 件 … 領収書が無い明細など。月の報告で数を出す")
    for k, v in sorted(kei.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {kit.yen(v)}")
    print("※ すべて案です。最後に決めるのはオーナーか税理士です")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
