#!/usr/bin/env python3
"""freee会計 API に取引（と領収書のファイル）を登録する（既定は試し運転・あなたのアプリと事業所で）

  python3 scripts/freee_api.py out/anbun.jsonl                         # 試し運転：送る中身だけ見せる（ネットにつながない）
  python3 scripts/freee_api.py out/anbun.jsonl --go --limit 1          # 1件だけ本当に登録（最初は必ずこれ）
  python3 scripts/freee_api.py --ichiran --go                          # 勘定科目・税区分・口座の名前の一覧（kaikei.json を写すため）

使う操作（freee 公式の API 定義 github.com/freee/freee-api-schema で確かめた）
  認可       OAuth2（認可コード）。refresh token は1回しか使えない → 使ったら新しいものを .env に書き戻す
  事業所     GET  /api/1/companies
  科目・税区分・口座  GET /api/1/account_items ・ GET /api/1/taxes/companies/{company_id} ・ GET /api/1/walletables
  証憑ファイル POST /api/1/receipts（multipart・company_id と receipt が必須）
  取引       POST /api/1/deals（company_id・issue_date・type=expense・details[tax_code, account_item_id, amount] が必須）
             payments[amount, date, from_walletable_type, from_walletable_id] で決済済みにする
  1日の回数の上限（事業所×アプリ）… 法人エンタープライズ 10,000 ／ 法人アドバンス 5,000 ／ それ以外 3,000（公式の説明より）
  有料プランの事業所だけで使える API がある（エラー freee_plan_limit）

同じ記録を2回登録しないように、登録した記録の id を out/freee_sumi.jsonl に残し、次から飛ばす。
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import argparse
import json
import mimetypes
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

import gyou
import kit

API = "https://api.freee.co.jp"
TOKEN = "https://accounts.secure.freee.co.jp/public_api/token"


def token():
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": kit.env("FREEE_CLIENT_ID", required=True),
        "client_secret": kit.env("FREEE_CLIENT_SECRET", required=True),
        "refresh_token": kit.env("FREEE_REFRESH_TOKEN", required=True),
    }).encode()
    d = http("POST", TOKEN, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if d.get("refresh_token"):
        kit.env_set("FREEE_REFRESH_TOKEN", d["refresh_token"])  # 1回しか使えないので必ず書き戻す
    if not d.get("access_token"):
        sys.exit("止めます：アクセストークンが取れませんでした（playbooks/07-freee-api.md）")
    return d["access_token"]


def http(method, url, body=None, headers=None):
    import urllib.error
    import urllib.request
    h = {"Accept": "application/json", "User-Agent": "agent-kit/1.0"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:600]}") from None


def api(tok, method, path, q=None, js=None, raw=None, ctype=None):
    url = API + path + ("?" + urllib.parse.urlencode(q) if q else "")
    h = {"Authorization": f"Bearer {tok}"}
    body = None
    if js is not None:
        body = json.dumps(js).encode()
        h["Content-Type"] = "application/json"
    elif raw is not None:
        body, h["Content-Type"] = raw, ctype
    return http(method, url, body=body, headers=h)


def multipart(fields, file_field, path):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        if v in (None, ""):
            continue
        out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{k}"'.encode(), b"", str(v).encode()]
    p = Path(path)
    ct = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    out += [f"--{b}".encode(), f'Content-Disposition: form-data; name="{file_field}"; filename="{p.name}"'.encode(),
            f"Content-Type: {ct}".encode(), b"", p.read_bytes(), f"--{b}--".encode(), b""]
    return b"\r\n".join(out), f"multipart/form-data; boundary={b}"


def ichiran(tok, cid):
    ai = api(tok, "GET", "/api/1/account_items", {"company_id": cid}).get("account_items", [])
    tx = api(tok, "GET", f"/api/1/taxes/companies/{cid}", {"available": "true"}).get("taxes", [])
    wl = api(tok, "GET", "/api/1/walletables", {"company_id": cid}).get("walletables", [])
    return ai, tx, wl


def main():
    ap = argparse.ArgumentParser(description="freee に取引を登録（既定は試し運転）")
    ap.add_argument("jsonl", nargs="?")
    ap.add_argument("--go", action="store_true", help="本当に送る")
    ap.add_argument("--limit", type=int, default=0, help="この件数だけ登録する（最初は 1）")
    ap.add_argument("--ichiran", action="store_true", help="科目・税区分・口座の名前の一覧を出す")
    ap.add_argument("--kakunin-mo", action="store_true")
    a = ap.parse_args()

    if a.ichiran:
        if not a.go:
            print("試し運転です。--go を付けると、あなたの事業所の科目・税区分・口座の名前を読みます（読むだけ）")
            return
        tok = token()
        cid = kit.env("FREEE_COMPANY_ID") or str(api(tok, "GET", "/api/1/companies")["companies"][0]["id"])
        ai, tx, wl = ichiran(tok, cid)
        print(f"事業所 {cid}")
        print("勘定科目：" + "、".join(x["name"] for x in ai))
        print("税区分：" + "、".join(f"{x['name_ja']}（code {x['code']}）" for x in tx))
        print("口座：" + "、".join(f"{x['name']}（{x['type']}）" for x in wl))
        print("→ config/kaikei.json の名前をこの一覧から1字ずつ写す")
        return
    if not a.jsonl:
        ap.error("記録のファイル（out/anbun.jsonl など）が要ります")

    k = gyou.kaikei_check()
    sumi_p = kit.HOME / "out" / "freee_sumi.jsonl"
    sumi = {r["id"] for r in kit.read_jsonl(sumi_p)} if sumi_p.exists() else set()
    dasu, dasanai = gyou.wakeru(kit.read_jsonl(a.jsonl), a.kakunin_mo)
    dasu = [(r, p) for r, p in dasu if r["id"] not in sumi]
    if a.limit:
        dasu = dasu[:a.limit]

    if not a.go:
        print(f"試し運転です（送りません）。登録する予定 {len(dasu)} 件（登録済みで飛ばす {len(sumi)} 件）：")
        for r, parts in dasu[:5]:
            body = {"company_id": "（FREEE_COMPANY_ID）", "issue_date": r["date"], "type": "expense",
                    "ref_number": r["id"],
                    "details": [{"account_item_id": f"（{r['kamoku']} の id）", "tax_code": f"（{k['zei_freee'].get(z, z)} の code）",
                                 "amount": v, "description": gyou.tekiyou(r)} for z, v in parts],
                    "payments": [{"date": r["date"], "from_walletable_type": "（口座の種類）",
                                  "from_walletable_id": f"（{(k['kouza'].get(r.get('kouza') or '') or {}).get('freee', '口座')} の id）",
                                  "amount": sum(v for _, v in parts)}]}
            print("  POST /api/1/deals " + json.dumps(body, ensure_ascii=False))
            if r.get("file"):
                print(f"  POST /api/1/receipts（ファイル {r['file']}）→ 取引の receipt_ids に入れる")
        gyou.show_dasanai(dasanai)
        print("本当に送るときは、オーナーの許可を取ってから --go --limit 1 で1件だけ試す")
        return

    tok = token()
    cid = kit.env("FREEE_COMPANY_ID") or str(api(tok, "GET", "/api/1/companies")["companies"][0]["id"])
    ai, tx, wl = ichiran(tok, cid)
    ai_id = {x["name"]: x["id"] for x in ai}
    tx_code = {x["name_ja"]: x["code"] for x in tx}
    wl_id = {x["name"]: (x["type"], x["id"]) for x in wl}
    n_ok = 0
    for r, parts in dasu:
        miss = []
        if r["kamoku"] not in ai_id:
            miss.append(f"勘定科目「{r['kamoku']}」")
        for z, _ in parts:
            if k["zei_freee"].get(z) not in tx_code:
                miss.append(f"税区分「{k['zei_freee'].get(z, z)}」")
        wname = (k["kouza"].get(r.get("kouza") or "") or {}).get("freee")
        if wname not in wl_id:
            miss.append(f"口座「{wname}」")
        if miss:
            print(f"  飛ばす {r['date']} {r['mise']}：freee に無い名前 " + "・".join(miss))
            continue
        receipt_ids = []
        if r.get("file") and Path(r["file"]).exists():
            body, ct = multipart({"company_id": cid, "description": gyou.tekiyou(r)[:255],
                                  "receipt_metadatum_partner_name": r.get("mise"),
                                  "receipt_metadatum_issue_date": r["date"],
                                  "receipt_metadatum_amount": r["amount"]}, "receipt", r["file"])
            rc = api(tok, "POST", "/api/1/receipts", raw=body, ctype=ct)
            receipt_ids = [rc["receipt"]["id"]]
        wtype, wid = wl_id[wname]
        deal = {"company_id": int(cid), "issue_date": r["date"], "type": "expense", "ref_number": r["id"][:255],
                "details": [{"account_item_id": ai_id[r["kamoku"]], "tax_code": tx_code[k["zei_freee"][z]],
                             "amount": v, "description": gyou.tekiyou(r)[:250]} for z, v in parts],
                "payments": [{"date": r["date"], "from_walletable_type": wtype, "from_walletable_id": wid,
                              "amount": sum(v for _, v in parts)}]}
        if receipt_ids:
            deal["receipt_ids"] = receipt_ids
        res = api(tok, "POST", "/api/1/deals", js=deal)
        did = (res.get("deal") or {}).get("id")
        with open(sumi_p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": r["id"], "deal_id": did, "receipt_ids": receipt_ids}, ensure_ascii=False) + "\n")
        n_ok += 1
        print(f"  登録 {r['date']} {r['mise']} {kit.yen(r['amount'])} → 取引 {did}")
        time.sleep(0.5)
    print(f"登録 {n_ok} 件 ／ 予定 {len(dasu)} 件。freee の画面で1件ずつ確かめる")


if __name__ == "__main__":
    main()
