"""取り込み用の行に分ける（export_freee.py / export_mf.py / freee_api.py が使う）。単独では動かさない。

1件の記録 → 会計ソフトに入れる行（税区分ごと・按分の事業分だけ）
  出さないもの … 事業以外 ／ 私用の按分分 ／ マイナス（返金は元の取引を直す）／ 要確認が残っている行（--kakunin-mo で出せる）
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import kit


def bubun(r, shiyou_label):
    """[(zei, 金額)] を返す。按分があれば事業の割合で税区分ごとに縮める。"""
    base = dict(r.get("zei_uchiwake") or {r.get("zei", "fumei"): r["amount"]})
    total = sum(base.values())
    if r.get("anbun"):
        jigyou = sum(p["amount"] for p in r["anbun"] if p["saki"] != shiyou_label)
        if total == 0:
            return []
        keys = list(base)
        scaled = {k: int(base[k] * jigyou / total) for k in keys}
        scaled[keys[0]] += jigyou - sum(scaled.values())
        base = scaled
    return [(z, v) for z, v in base.items() if v]


def wakeru(rows, kakunin_mo=False):
    """(出す行, 出さない行と理由) を返す。"""
    anbun = kit.config("anbun")
    dasu, dasanai = [], []
    for r in rows:
        why = None
        if r.get("kamoku") == "事業以外":
            why = "事業以外"
        elif not isinstance(r.get("amount"), int):
            why = "金額が無い"
        elif r["amount"] < 0:
            why = "マイナス（返金・取り消し）：元の取引を直す（手で）"
        elif not r.get("kamoku"):
            why = "科目が決まっていない"
        elif r.get("kakunin") and not kakunin_mo:
            why = "要確認が残っている：" + "／".join(r["kakunin"])
        if why:
            dasanai.append((r, why))
            continue
        parts = bubun(r, anbun["shiyou_label"])
        if not parts:
            dasanai.append((r, "事業の分が0円"))
            continue
        dasu.append((r, parts))
    return dasu, dasanai


def tekiyou(r):
    t = r.get("mise") or ""
    if r.get("naiyou"):
        t += " " + r["naiyou"]
    if r.get("dousekisha"):
        t += f"（同席 {r['dousekisha']}）"
    if r.get("anbun"):
        t += f"（按分 {r.get('anbun_riyuu', '')}）"
    return t.strip()


def kaikei_check():
    k = kit.config("kaikei")
    if kit.config_is_example("kaikei") or not k.get("kakunin_zumi"):
        print("※ config/kaikei.json の科目・税区分・口座の名前が『例』のままです。会計ソフトの一覧から写して kakunin_zumi を true にしてください（取り込みで失敗するか、違う区分になります）")
    return k


def show_dasanai(dasanai, limit=15):
    if not dasanai:
        return
    print(f"出さなかった {len(dasanai)} 件（オーナーが決めてから作り直す）：")
    for r, why in dasanai[:limit]:
        print(f"  {r.get('date')} {r.get('mise')} {kit.yen(r.get('amount')) if isinstance(r.get('amount'), int) else ''} … {why}")
    if len(dasanai) > limit:
        print(f"  …ほか {len(dasanai) - limit} 件")
