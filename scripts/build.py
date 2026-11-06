"""Bouwt de categoriseeromgeving.

  python3 scripts/build.py [--raw private/raw] [--out private]

Leest alle bankexports in --raw, categoriseert ze automatisch en schrijft:
  <out>/transactions.json   genormaliseerde, gecategoriseerde transacties
  <out>/categoriseren.html  de interactieve omgeving (template + data)
Persoonlijke regels: <out>/personal_rules.json (niet in git).
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from categories import AARD, CATEGORIES, categorize, load_personal  # noqa: E402
from parse_sources import load_all  # noqa: E402

GUESS_CATS = {"gedeeld", "terugbetaling", "kaart_onbekend", "overig_in", "verkoop", "gift_in"}


def is_guess(t: dict) -> bool:
    """Automatische keuzes waar we minder zeker van zijn: even laten checken."""
    return t["cat"] in GUESS_CATS or t["why"].startswith("regel: ^(ls ")


START, END = "2024-01-01", "2026-12-31"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "private" / "raw"))
    ap.add_argument("--out", default=str(ROOT / "private"))
    a = ap.parse_args()
    out = Path(a.out)
    personal = load_personal(out / "personal_rules.json")

    txs = [t for t in load_all(Path(a.raw)) if START <= t["date"] <= END]
    for t in txs:
        t["cat"], t["why"] = categorize(t, personal)

    slim = [
        {
            "id": t["id"], "d": t["date"], "t": t["time"], "a": t["account"][0],
            "v": t["amount"], "p": t["party"], "o": t["desc"][:160],
            "m": t["method"], "c": t["cat"], "w": t["why"],
            **({"q": 1} if is_guess(t) else {}),
            **({"fx": f'{t["orig_amount"]} {t["orig_currency"]}'} if t["orig_currency"] else {}),
        }
        for t in txs
    ]
    (out / "transactions.json").write_text(json.dumps(txs, ensure_ascii=False, indent=1), encoding="utf-8")

    cats = [
        {"id": k, "label": v[0], "group": v[1], "kind": v[2], "aard": v[3]}
        for k, v in CATEGORIES.items()
    ]
    payload = {"tx": slim, "cats": cats, "aard": AARD,
               "accounts": {"R": "Rabo privé", "K": "Knab zakelijk", "C": "Crypto.com kaart"}}
    tpl = (ROOT / "app" / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    (out / "categoriseren.html").write_text(html, encoding="utf-8")

    c = collections.Counter(t["cat"] for t in txs)
    print(f"{len(txs)} transacties, {c['onbekend']} te beoordelen")
    for k, n in c.most_common():
        print(f"  {n:5d}  {CATEGORIES[k][0]}")


if __name__ == "__main__":
    main()
