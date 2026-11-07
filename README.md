# xtrafinance

Persoonlijk kasboek: bankexports inlezen, automatisch categoriseren en in een
interactieve pagina nakijken en corrigeren. Basis voor analyse van inkomsten-
en uitgavenpatronen (inclusief een psychologische lens: noodzaak, gemak &
impuls, genieten & sociaal, groei & gezondheid).

## Gebruik

1. Zet de exports in `private/raw/` (Rabobank CSV, Knab transactieoverzicht,
   Crypto.com `card_transactions_record_*.csv`).
2. Optioneel: persoonlijke regels in `private/personal_rules.json`
   (eigen rekeningnummers, verhuurder, klanten).
3. `python3 scripts/build.py`
   - `private/transactions.json`: genormaliseerde, gecategoriseerde transacties
   - `private/categoriseren.html`: de interactieve omgeving

**`private/` staat in `.gitignore`.** Deze repo is openbaar; er komen nooit
transacties, namen of rekeningnummers in.

## Opbouw

| Bestand | Wat |
|---|---|
| `scripts/parse_sources.py` | Inlezen en normaliseren van de drie bankformaten |
| `scripts/categories.py` | Categorieën (groep, soort, aard) en algemene regels |
| `scripts/build.py` | Categoriseert en bouwt de pagina |
| `app/template.html` | De categoriseeromgeving (wachtrij, lijst, overzicht, regels) |
| `scripts/apply_choices.py` | Past de keuzes uit de pagina (export van de database naar `private/db/`) toe |
| `scripts/analyse.py` | Berekent de aggregaten voor het patronenrapport (`private/analyse.json`) |

Volgorde van categorisering: handmatige keuze per transactie → eigen regel per
tegenpartij (gemaakt in de pagina) → persoonlijke regels → algemene regels.
Eigen overboekingen, sparen, beleggen en lenen binnen de familie tellen niet
mee als inkomen of uitgave.
