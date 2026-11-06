"""Inlezen en normaliseren van bankexports.

Ondersteunde bronnen:
  - Rabobank CSV-export (CSV_A_...csv, latin-1, komma-gescheiden)
  - Knab transactieoverzicht (puntkomma-gescheiden)
  - Crypto.com kaart (card_transactions_record_...csv)

Elke transactie wordt een dict met vaste velden, zodat categoriseren en
analyseren los staan van het bronformaat.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:  # Nederlandse tijd voor kaarttransacties (export staat in UTC)
    from zoneinfo import ZoneInfo

    AMS = ZoneInfo("Europe/Amsterdam")
except Exception:  # pragma: no cover
    AMS = timezone(timedelta(hours=1))


def _num_nl(s: str) -> float:
    """'+1.234,56' / '-8,70' / '2499' -> float."""
    s = (s or "").strip().replace("+", "")
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _tx_id(*parts) -> str:
    h = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()
    return h[:12]


def parse_rabobank(path: Path) -> list[dict]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        desc = _clean(" ".join(r.get(f"Omschrijving-{i}", "") for i in (1, 2, 3)))
        party = _clean(r.get("Naam tegenpartij"))
        # Tijdstip staat bij pinbetalingen in de omschrijving: 'Betaalautomaat 00:54'
        m = re.search(r"(?:Betaalautomaat|Geldautomaat)\s+(\d{2}:\d{2})", desc)
        if not m:
            m = re.search(r",\s*(\d{2}:\d{2})\s*\.\s*Pas", desc)
        out.append(
            {
                "id": "R" + _tx_id(r["IBAN/BBAN"], r["Volgnr"]),
                "date": r["Datum"],
                "time": m.group(1) if m else "",
                "account": "Rabo privé",
                "amount": round(_num_nl(r["Bedrag"]), 2),
                "party": party or _clean(r.get("Naam uiteindelijke partij")) or desc[:40],
                "iban": _clean(r.get("Tegenrekening IBAN/BBAN")),
                "desc": desc,
                "method": r.get("Code", ""),
                "orig_currency": _clean(r.get("Oorspr munt")),
                "orig_amount": _clean(r.get("Oorspr bedrag")),
                "balance": _num_nl(r.get("Saldo na trn", "")),
            }
        )
    return out


def parse_knab(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            sign = 1 if r["CreditDebet"].lower().startswith("bij") else -1
            d = datetime.strptime(r["Transactiedatum"], "%d-%m-%Y").date().isoformat()
            desc = _clean(r.get("Omschrijving"))
            out.append(
                {
                    "id": "K" + _tx_id(r["Rekeningnummer"], r["Referentie"], r["Transactiedatum"], r["Bedrag"]),
                    "date": d,
                    "time": "",
                    "account": "Knab zakelijk",
                    "amount": round(sign * _num_nl(r["Bedrag"]), 2),
                    "party": _clean(r.get("Tegenrekeninghouder")) or desc[:40],
                    "iban": _clean(r.get("Tegenrekeningnummer")),
                    "desc": desc,
                    "method": _clean(r.get("Betaalwijze")),
                    "orig_currency": "",
                    "orig_amount": "",
                    "balance": None,
                }
            )
    return out


def parse_cryptocom_card(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            ts = datetime.strptime(r["Timestamp (UTC)"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            local = ts.astimezone(AMS)
            native = float(r["Native Amount"] or r["Amount"])
            cur = r["Currency"]
            desc = _clean(r["Transaction Description"])
            # Winkelnummers weghalen voor een leesbare tegenpartij
            party = re.sub(r"^(Refund:\s*)", "", desc)
            out.append(
                {
                    "id": "C" + _tx_id(r["Timestamp (UTC)"], desc, r["Amount"], i),
                    "date": local.date().isoformat(),
                    "time": local.strftime("%H:%M"),
                    "account": "Crypto.com kaart",
                    "amount": round(native, 2),
                    "party": party,
                    "iban": "",
                    "desc": desc,
                    "method": "kaart",
                    "orig_currency": cur if cur != "EUR" else "",
                    "orig_amount": r["Amount"] if cur != "EUR" else "",
                    "balance": None,
                }
            )
    return out


def load_all(raw_dir: Path) -> list[dict]:
    txs: list[dict] = []
    for p in sorted(raw_dir.glob("*.csv")):
        head = p.read_bytes()[:400].decode("latin-1")
        if "IBAN/BBAN" in head and "Volgnr" in head:
            txs += parse_rabobank(p)
        elif "Tegenrekeninghouder" in head and "CreditDebet" in head:
            txs += parse_knab(p)
        elif "Timestamp (UTC)" in head and "Native Amount" in head:
            txs += parse_cryptocom_card(p)
        else:
            print(f"Onbekend formaat, overgeslagen: {p.name}")
    txs.sort(key=lambda t: (t["date"], t["time"], t["id"]))
    return txs
