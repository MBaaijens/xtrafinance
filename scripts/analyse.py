"""Aggregaten voor het patronenrapport (geen losse transacties).

  python3 scripts/analyse.py -> private/analyse.json
"""
import collections, datetime as dt, json, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from categories import CATEGORIES, AARD  # noqa

P = Path(__file__).resolve().parent.parent / "private"
t = json.loads((P / "final.json").read_text())
K = lambda c: CATEGORIES[c][2]; A = lambda c: CATEGORIES[c][3]; L = lambda c: CATEGORIES[c][0]; G = lambda c: CATEGORIES[c][1]
D = dt.date.fromisoformat
Y = ("2024", "2025", "2026")
ONLINE = {"software_ai", "streaming", "online_shopping", "dating", "games_gokken", "zakelijk"}
out = {}

months = sorted({x["date"][:7] for x in t})
mi = collections.defaultdict(float); mo = collections.defaultdict(float); md = collections.defaultdict(float)
cat = collections.defaultdict(lambda: collections.defaultdict(float))
aard = collections.defaultdict(lambda: collections.defaultdict(float))
for x in t:
    k = K(x["cat"]); m = x["date"][:7]; y = m[:4]
    if k == "in": mi[m] += x["amount"]; cat[x["cat"]][y] += x["amount"]
    elif k == "out":
        mo[m] -= x["amount"]; cat[x["cat"]][y] -= x["amount"]; aard[A(x["cat"])][y] -= x["amount"]
        if A(x["cat"]) in ("gemak", "genieten"): md[m] -= x["amount"]
out["monthly"] = [{"m": m, "in": round(mi[m]), "out": round(mo[m]), "disc": round(md[m])} for m in months]
out["cats"] = [{"id": c, "label": L(c), "group": G(c), "kind": K(c), "aard": A(c), **{y: round(v.get(y, 0)) for y in Y}} for c, v in cat.items()]
out["aard"] = {a: {y: round(v.get(y, 0)) for y in Y} for a, v in aard.items()}
out["aard_labels"] = AARD

cl = collections.defaultdict(lambda: collections.defaultdict(float))
for x in t:
    if x["cat"] == "omzet":
        p = x["party"].replace("The Compliance Fact. BV", "The Compliance Factory B.V.").replace("FINQLE BV", "Finqle B.V.")
        cl[p][x["date"][:4]] += x["amount"]
out["clients"] = sorted([{"p": p, **{y: round(v.get(y, 0)) for y in Y}} for p, v in cl.items()], key=lambda r: -sum(r[y] for y in Y))

for c in ("sparen", "beleggen", "familie"):
    out["flow_" + c] = {y: round(-sum(x["amount"] for x in t if x["cat"] == c and x["date"].startswith(y))) for y in Y}

# tijdstip (fysieke betalingen in NL-tijd, geen buitenland/online)
phys = [x for x in t if K(x["cat"]) == "out" and x["amount"] < 0 and x["time"] and not x["orig_currency"] and x["cat"] not in ONLINE]
hrs = [{"h": h, "n": sum(1 for x in phys if int(x["time"][:2]) == h), "eur": round(-sum(x["amount"] for x in phys if int(x["time"][:2]) == h))} for h in range(24)]
out["hours"] = hrs
late = [x for x in phys if int(x["time"][:2]) >= 22 or int(x["time"][:2]) < 5]
out["late"] = {"n": len(late), "eur": round(-sum(x["amount"] for x in late)), "of": len(phys),
               "by_year": dict(collections.Counter(x["date"][:4] for x in late)),
               "cats": collections.Counter(L(x["cat"]) for x in late).most_common(5)}
tick = {}
for c in ("horeca", "uitgaan"):
    a = [-x["amount"] for x in phys if x["cat"] == c and (int(x["time"][:2]) >= 22 or int(x["time"][:2]) < 5)]
    b = [-x["amount"] for x in phys if x["cat"] == c and 8 <= int(x["time"][:2]) < 22]
    tick[c] = {"late": round(st.mean(a), 2), "day": round(st.mean(b), 2), "n_late": len(a)}
out["ticket"] = tick

disc = [x for x in t if K(x["cat"]) == "out" and x["amount"] < 0 and A(x["cat"]) in ("gemak", "genieten")]
out["weekday"] = [round(-sum(x["amount"] for x in disc if D(x["date"]).weekday() == d)) for d in range(7)]

spend = [x for x in t if K(x["cat"]) == "out" and x["amount"] < 0]
small = [x for x in spend if -x["amount"] < 10]
out["small"] = {"n": len(small), "of": len(spend), "eur": round(-sum(x["amount"] for x in small)),
                "onderweg": {y: {"n": sum(1 for x in spend if x["cat"] == "onderweg" and x["date"].startswith(y)),
                                 "eur": round(-sum(x["amount"] for x in spend if x["cat"] == "onderweg" and x["date"].startswith(y)))} for y in Y},
                "morning_kiosk": sum(1 for x in spend if x["cat"] == "onderweg" and x["time"] and 6 <= int(x["time"][:2]) < 9)}

# geld-in-de-zak: discretionaire uitgaven per dag in de 4 dagen na een aanvulling van de privérekening
pay = sorted({D(x["date"]) for x in t if x["account"] == "Rabo privé" and x["cat"] == "intern" and x["amount"] >= 300})
start, end = D(t[0]["date"]), D(t[-1]["date"])
days = [start + dt.timedelta(i) for i in range((end - start).days + 1)]
aft = lambda d: any(0 <= (d - p).days <= 3 for p in pay)
na = sum(1 for d in days if aft(d)); sa = -sum(x["amount"] for x in disc if aft(D(x["date"]))); stt = -sum(x["amount"] for x in disc)
out["payday"] = {"events": len(pay), "after": round(sa / na, 1), "other": round((stt - sa) / (len(days) - na), 1)}

I = [mi[m] for m in months[:-1]]; S = [md[m] for m in months[:-1]]
cor = lambda a, b: sum((p - st.mean(a)) * (q - st.mean(b)) for p, q in zip(a, b)) / (len(a) * st.pstdev(a) * st.pstdev(b))
out["corr_income_disc"] = round(cor(I, S), 2)
gap = ["2026-04", "2026-05", "2026-06"]; rest = [m for m in months[:-1] if m.startswith("2026") and m not in gap]
out["gap2026"] = {"disc_gap": round(st.mean(md[m] for m in gap)), "disc_rest": round(st.mean(md[m] for m in rest)),
                  "inc_gap": round(sum(mi[m] for m in gap))}
out["income_cv"] = {y: round(st.pstdev([mi[m] for m in months if m.startswith(y) and m != months[-1]]) / st.mean([mi[m] for m in months if m.startswith(y) and m != months[-1]]), 2) for y in Y}

# saldo privérekening
last = {}
for x in t:
    if x["account"] == "Rabo privé": last[x["date"]] = x["balance"]
bm = collections.defaultdict(list)
for d, b in last.items(): bm[d[:7]].append(b)
out["balance"] = [{"m": m, "min": round(min(v)), "max": round(max(v))} for m, v in bm.items()]
out["lowdays"] = {y: sum(1 for d, b in last.items() if b < 50 and d.startswith(y)) for y in Y}
ref = [x for x in t if x["account"] == "Rabo privé" and x["cat"] in ("intern", "sparen") and x["amount"] > 0]
out["refills"] = {"n": len(ref), "median": st.median([x["amount"] for x in ref]), "by_year": dict(collections.Counter(x["date"][:4] for x in ref))}
cp = [x for x in t if x["party"] == "OpenPayd"]
out["card_topups"] = {"n": len(cp), "median": st.median([-x["amount"] for x in cp])}

subs = {}
for y in Y:
    m = {x["party"].lower().replace("paypal *", "")[:14] for x in t if x["cat"] in ("streaming", "software_ai") and x["date"].startswith(y) and x["amount"] < 0}
    subs[y] = len(m)
out["subs_merchants"] = subs
out["tikkie"] = {y: {"terug": round(sum(x["amount"] for x in t if x["cat"] == "terugbetaling" and x["date"].startswith(y))),
                     "gedeeld": round(-sum(x["amount"] for x in t if x["cat"] == "gedeeld" and x["date"].startswith(y)))} for y in Y}
out["period"] = {"from": t[0]["date"], "to": t[-1]["date"], "n": len(t)}
(P / "analyse.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: out[k] for k in ("payday", "corr_income_disc", "gap2026", "income_cv", "lowdays", "refills", "subs_merchants", "late", "ticket", "small")}, ensure_ascii=False))
