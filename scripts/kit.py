"""道具で共通に使うもの（設定・記録の読み書き・鍵）。単独では動かさない。

置き場
  KIT_HOME（環境変数）… このフォルダの場所。無ければこのファイルの1つ上
  .env               … 鍵（リポジトリに入れない）
  config/<名前>.json  … オーナーの設定（無ければ <名前>.example.json を読む）

記録の形（1行1件の JSON・.jsonl）
  id        … 道具が付ける印（同じ行からは同じ印）
  date      … 取引年月日 YYYY-MM-DD
  amount    … 税込の金額（円・整数。返金・取り消しはマイナス）
  mise      … 店・取引先の名前
  source    … card / bank / ryoushuu
  kouza     … 支払った口座・カードの名前（会計ソフトの口座名に合わせる）
  memo, invoice_no, zeiritsu, file, kamoku, zei, kakunin[] ほか
"""

import os as _ng_os, sys as _ng_sys  # N-Hack 専用の門（下の3行を消すとこのキットは動きません）
_ng_sys.path.insert(0, _ng_os.path.dirname(_ng_os.path.abspath(__file__)))
import nhack_gate as _nhack_gate  # noqa: E402,F401

import hashlib
import json
import os
import sys
import unicodedata
from pathlib import Path

HOME = Path(os.environ.get("KIT_HOME") or Path(__file__).resolve().parent.parent)


def config(name):
    p = HOME / "config" / f"{name}.json"
    if not p.exists():
        p = HOME / "config" / f"{name}.example.json"
    return json.loads(p.read_text(encoding="utf-8"))


def config_is_example(name):
    return not (HOME / "config" / f"{name}.json").exists()


def env(name, required=False):
    """環境変数 → .env の順に読む。値はどこにも書き出さない。"""
    v = os.environ.get(name)
    if v is None:
        p = HOME / ".env"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    if k.strip() == name:
                        v = val.strip()
                        break
    if required and not v:
        sys.exit(f"止めます：{name} が .env にありません（playbooks/07-freee-api.md）")
    return v or None


def env_set(name, value):
    """.env の1行だけを書き換える（freee の refresh token は1回しか使えないため）。"""
    p = HOME / ".env"
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == name:
            out.append(f"{name}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{name}={value}")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.chmod(p, 0o600)


def seiki(t):
    return unicodedata.normalize("NFKC", t or "").strip()


def make_id(*parts):
    return hashlib.sha1("|".join(str(x) for x in parts).encode("utf-8")).hexdigest()[:12]


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"止めます：{path} の {n} 行目が JSON として読めません（{e}）")
    return out


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def yen(x):
    return "未確認" if x is None else f"{int(x):,}円"
