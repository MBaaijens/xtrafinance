"""Past de keuzes uit de pagina (regels + handmatige keuzes) toe op de transacties.

  python3 scripts/apply_choices.py  ->  private/final.json
Verwacht private/db/rules/*.json en private/db/overrides/*.json (export van de db).
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "private"
norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())

def load(d):
    out = {}
    for f in (P / "db" / d).glob("*.json"):
        j = json.loads(f.read_text())
        out[f.stem] = j.get("data", j)
    return out

def main():
    tx = json.loads((P / "transactions.json").read_text())
    rules, ovr = load("rules"), load("overrides")
    rmap = {(norm(r["p"]), r["dir"]): r["c"] for r in rules.values()}
    for t in tx:
        d = "in" if t["amount"] >= 0 else "out"
        t["auto_cat"] = t["cat"]; t["src"] = "auto"
        r = rmap.get((norm(t["party"]), d)) or rmap.get((norm(t["party"]), "all"))
        if r: t["cat"], t["src"] = r, "regel"
        o = ovr.get(t["id"])
        if o and o.get("c"): t["cat"], t["src"] = o["c"], "handmatig"
        if o and o.get("n"): t["note"] = o["n"]
    (P / "final.json").write_text(json.dumps(tx, ensure_ascii=False, indent=1))
    return tx, rules, ovr

if __name__ == "__main__":
    tx, rules, ovr = main()
    import collections
    print(len(rules), "regels,", len(ovr), "handmatig; onbekend:", sum(t["cat"] == "onbekend" for t in tx))
    print(collections.Counter(t["src"] for t in tx))
