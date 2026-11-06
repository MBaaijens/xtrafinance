"""Categorieën en automatische categorisatieregels.

Elke categorie heeft:
  group  - hoofdgroep voor overzichten
  kind   - 'in' (inkomen), 'out' (uitgave) of 'transfer' (telt niet mee)
  aard   - psychologische lens: waarom geef je dit uit?

Regels worden van boven naar beneden toegepast; de eerste match wint.
Persoonlijke regels (namen, eigen rekeningnummers) staan NIET in deze file
maar in private/personal_rules.json, zodat de repo niets persoonlijks bevat.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

AARD = {
    "noodzaak": "Noodzakelijk",
    "gemak": "Gemak & impuls",
    "genieten": "Genieten & sociaal",
    "groei": "Groei & gezondheid",
    "werk": "Werk & onderneming",
    "financieel": "Financieel",
    "inkomen": "Inkomen",
    "neutraal": "Neutraal",
}

# id: (label, group, kind, aard)
CATEGORIES: dict[str, tuple[str, str, str, str]] = {
    # Inkomsten
    "omzet": ("Omzet klanten", "Inkomsten", "in", "inkomen"),
    "salaris": ("Salaris (loondienst)", "Inkomsten", "in", "inkomen"),
    "huurbijdrage": ("Huurbijdrage huisgenoten", "Inkomsten", "in", "inkomen"),
    "toeslagen": ("Toeslagen & teruggaven", "Inkomsten", "in", "inkomen"),
    "terugbetaling": ("Terugbetaald door anderen", "Inkomsten", "in", "inkomen"),
    "gift_in": ("Geschenken & familie (ontvangen)", "Inkomsten", "in", "inkomen"),
    "verkoop": ("Verkoop spullen", "Inkomsten", "in", "inkomen"),
    "overig_in": ("Overige inkomsten", "Inkomsten", "in", "inkomen"),
    # Wonen & vaste lasten
    "huur": ("Huur & borg", "Wonen & vaste lasten", "out", "noodzaak"),
    "energie": ("Energie & water", "Wonen & vaste lasten", "out", "noodzaak"),
    "internet_tel": ("Internet & telefoon", "Wonen & vaste lasten", "out", "noodzaak"),
    "zorgverzekering": ("Zorgverzekering", "Wonen & vaste lasten", "out", "noodzaak"),
    "verzekeringen": ("Overige verzekeringen", "Wonen & vaste lasten", "out", "noodzaak"),
    "gemeente": ("Gemeente & overheid", "Wonen & vaste lasten", "out", "noodzaak"),
    "bank": ("Bankkosten", "Wonen & vaste lasten", "out", "noodzaak"),
    # Dagelijks
    "boodschappen": ("Boodschappen", "Dagelijks", "out", "noodzaak"),
    "onderweg": ("Onderweg & snacks", "Dagelijks", "out", "gemak"),
    "horeca": ("Uit eten & drinken", "Dagelijks", "out", "genieten"),
    "bezorging": ("Bezorgmaaltijden", "Dagelijks", "out", "gemak"),
    "verzorging": ("Verzorging & kapper", "Dagelijks", "out", "noodzaak"),
    "gezondheid": ("Gezondheid & supplementen", "Dagelijks", "out", "groei"),
    # Vervoer
    "ov": ("OV & trein", "Vervoer", "out", "noodzaak"),
    "taxi": ("Taxi & deelvervoer", "Vervoer", "out", "gemak"),
    "auto": ("Auto, fiets & parkeren", "Vervoer", "out", "noodzaak"),
    # Vrije tijd
    "sport": ("Sport & beweging", "Vrije tijd", "out", "groei"),
    "uitgaan": ("Uitgaan & ontspanning", "Vrije tijd", "out", "genieten"),
    "streaming": ("Streaming & media", "Vrije tijd", "out", "gemak"),
    "dating": ("Dating & sociale apps", "Vrije tijd", "out", "genieten"),
    "games_gokken": ("Games & gokken", "Vrije tijd", "out", "gemak"),
    "vakantie": ("Vakantie & reizen", "Vrije tijd", "out", "genieten"),
    "ontwikkeling": ("Opleiding & persoonlijke groei", "Vrije tijd", "out", "groei"),
    # Shopping
    "kleding": ("Kleding & schoenen", "Shopping", "out", "genieten"),
    "huis_inrichting": ("Huis & inrichting", "Shopping", "out", "noodzaak"),
    "online_shopping": ("Online shopping", "Shopping", "out", "gemak"),
    "elektronica": ("Elektronica & gadgets", "Shopping", "out", "genieten"),
    "cadeaus": ("Cadeaus & giften", "Shopping", "out", "genieten"),
    "gedeeld": ("Gedeelde kosten (Tikkie betaald)", "Shopping", "out", "genieten"),
    # Werk
    "software_ai": ("Software & AI-tools", "Werk & onderneming", "out", "werk"),
    "zakelijk": ("Overige zakelijke kosten", "Werk & onderneming", "out", "werk"),
    # Financieel
    "belasting": ("Belastingen (IB / btw)", "Financieel", "out", "financieel"),
    "boetes": ("Boetes", "Financieel", "out", "financieel"),
    "contant": ("Contant opnemen", "Financieel", "out", "neutraal"),
    "familie": ("Lenen & aflossen (familie)", "Financieel", "transfer", "financieel"),
    "beleggen": ("Beleggen & crypto", "Financieel", "transfer", "financieel"),
    "sparen": ("Sparen & reserveren", "Financieel", "transfer", "financieel"),
    "intern": ("Interne overboeking", "Financieel", "transfer", "neutraal"),
    "kaart_onbekend": ("Opwaardering kaart/Wise (details onbekend)", "Financieel", "out", "neutraal"),
    "onbekend": ("Te beoordelen", "Te beoordelen", "out", "neutraal"),
}

# (categorie, veld, regex, voorwaarde) — veld: party | desc | any
# voorwaarde: None, 'in' (bedrag > 0) of 'out' (bedrag < 0)
R = [
    # --- Financieel / overheid
    ("toeslagen", "any", r"zorgtoeslag|voorschot zorgtoes|teruggaaf|huurtoeslag", "in"),
    ("belasting", "party", r"belastingdienst", None),
    ("boetes", "party", r"justitie en veiligheid|cjib", None),
    ("gemeente", "party", r"gemeente|rdw\b|kvk|kamer van koophandel|vog-aanvraag|woningnet|pasfoto", None),
    ("bank", "party", r"^rabobank$|^knab$|pakketkosten|^kosten$", None),
    ("bank", "desc", r"pakketkosten|kosten rabo|rente", "out"),
    ("contant", "party", r"geldmaat|cardtronics|accesscash|\batm\b|rbc royal|td bank|geldautomaat", None),
    ("beleggen", "party", r"bitvavo|goudprijs|degiro|trading 212|meesman", None),
    ("kaart_onbekend", "party", r"^wise$|transferwise", "out"),
    # --- Wonen
    ("energie", "party", r"eneco|vattenfall|essent|greenchoice|vandebron|waternet|pwn|budget energie", None),
    ("internet_tel", "party", r"ziggo|kpn|simyo|budget mobiel|odido|t-mobile|vodafone|lebara|ben nl|youfone", None),
    ("zorgverzekering", "party", r"asr ziektekosten|asr ikz|asr aanvullende|zilveren kruis|cz\b|vgz|menzis|ditzo", None),
    ("verzekeringen", "party", r"nationale-nederlanden|interpolis|centraal beheer|total nn|ohra|aegon|unive", None),
    ("gezondheid", "party", r"infomedics|apotheek|tandarts|fysio|huisarts|ziekenhuis|vegro|zorgwinkel|hans anders|specsavers|iherb|sports supplements|microdose|wakingherbs|bulk\b", None),
    # --- Vervoer
    ("ov", "party", r"\bns\b|ns groep|ns reizigers|ns internationaal|ns-|^nlov|gvb|connexxion|arriva|ovpay|european sleeper|ov-chip|amsterdam cs|railway|sbb", None),
    ("taxi", "party", r"uber|bolt|taxi|felyx|gosharing", None),
    ("auto", "party", r"shell|esso|tamoil|total|bp\b|avia|lukoil|agip|tinq|tango|brandstof|tankstel|super tank|parkeer|parkeren|parking|easy ?park|q.?park|riverty|ultramar|couche.?tard|circle k|maple esso|drivetest|drive test|mto|canadian tire|p-zaailand|fietsparkeren|fietsenwinkel|fietsen|wheelgood|cbp champ", None),
    # --- Software / AI / werk
    ("software_ai", "party", r"anthropic|claude|openai|chatgpt|lovable|manus|cursor|descript|higgsfield|microsoft|google one|transip|mijndomein|notion|canva|skool|remotejobs|personality|n8n|zapier|github|figma", None),
    ("zakelijk", "party", r"humanication b\.v\. via tikkie|nordproducts|moonflash|stripe technology", None),
    # --- Media / streaming
    ("streaming", "party", r"you ?tube|netflix|pathe thuis|youtube|spotify|storytel|kobo|nextory|itunes|apple services|apple\.com|disney|videoland|hbo|npo\b|audible", None),
    ("dating", "party", r"breeze", None),
    ("gedeeld", "party", r"splitwise|wiebetaaltwat", None),
    ("cadeaus", "party", r"gofundme|gofndme|team alzheimer|stichting epop", None),
    ("zakelijk", "party", r"facebook payments|meta platforms|linkedin", None),
    ("bank", "party", r"temp auth hold", None),
    ("games_gokken", "party", r"toto|igaming|holland casino|lotto|staatsloterij|board game arena|blizzard|steam|playstation|nintendo", None),
    # --- Sport
    ("sport", "party", r"martial arts|teamsports|boulder|monk|klim|beest|beta boulders|be boulder|urban apes|de wadden|playtomic|padel|sportcity|basic.?fit|run x|breathcatchers|jumpskillz|yoga|hiihtokeskus|ski", None),
    # --- Opleiding
    ("ontwikkeling", "party", r"humanication|udemy|roc mondriaan|mbo college|dikke van dale|american book|black squirrel|bruna|boekhandel|coursera", None),
    # --- Boodschappen
    ("boodschappen", "party", r"albert heijn(?!.*to go)|^ah\b(?!.*to ?go)|jumbo|lidl|aldi|dekamarkt|deka|vomar|plus\b|dirk|coop|spar\b|ekoplaza|picnic|flink|metro\b|wal mart|walmart|farm boy|dollarama|costco|loblaws|van den tweel|kaas van faas|kaasspec|boer geert|vishandel|visspeciaal|visboer|slager|butcher|bakker|kissbakery|bakkerswinkel|rewe|denner|super u|super c|marche|m&m fruit|aardappelhandel|green fresh|universal meat|natuurvoord|landmarkt|bulk barn|schipholweg superm|aymer|koog supermarkten|carrefour|lcbo|gall & gall|statiegeld|lekkerhoning|snoepsmakelijk|poffertjes|grutto|kcs\b", None),
    # --- Onderweg (gemak)
    ("onderweg", "party", r"kiosk|ah to ?go|ah togo|smullers|febo|starbucks|hms ?host|wh smith|relay|selecta|coffee bike|cakes ?(&|en) ?candy|stationshuiskamer|subway|mcdonald|burger king|kfc|doner|kebab|snack|avondhapje|ijssalon|ijscuypje|massimo gelato|coca cola|bagels|bobino|cookie|tabac|broodje|burrito|next level surina|bolero", None),
    # --- Bezorging
    ("bezorging", "party", r"takeaway|thuisbezorgd|uber ?eats|deliveroo|sneleten", None),
    # --- Uitgaan
    ("uitgaan", "party", r"kuuma|photoboo|heuts leisure|^edc|pool|pong|pathe|tuschinski|kino|bioscoop|ticket|eventbrite|fever|stubhub|vangogh|museum|spa\b|nordik|sauna|thermen|fort resort|bmw driving|smartendr|famous player|calypso|escape|bowling|casino|concert|festival|tapastheater", None),
    # --- Horeca
    ("horeca", "party", r"restaurant|cafe|café|bar\b|bar |eetcafe|grandcafe|lunchroom|bistro|brasserie|pizz|burger|grill|diner|maoz|doner company|sushi|ramen|dim sum|tapas|proeflokaal|biertuin|kitchen|bagel|coffee|koffie|espresso|tst |lagom|bab el|papeneiland|noterij|bosburcht|dnb toorop|dnb frederik|screaming beans|kraftundlicht|zeemeeuw|het pakhuis|bombay|indian|roti|shalom|hoxton|kimpton|annies|alattin|tiofli|westweelde|dirck3|pacific|zanzi|papagayo|clocktower|barley mow|elgin|edinburger|matter of taste|foodhallen|mata hari|palmier|pistache|crazy horse|nobu|bulles|gourmet", None),
    # --- Vakantie
    ("vakantie", "party", r"klm|transavia|tuifly|ryanair|easyjet|porter airlines|air canada|airbnb|booking\.com|hotel|hostel|b&b|bed&bike|bed & bike|lapland|yllas|jan thiel|curacao|schiphol airport|schiphol nederland", None),
    # --- Kleding
    ("kleding", "party", r"^episode|mark.s store|uniqlo|suit ?supply|zara|h&m|pull & bear|c&a|zeeman|primark|levi|mango|zalando|van ?haren|ecco|dr ?martens|seasalt|tk maxx|winners|men's reality|decathlon|bever|mountain equipment|canam army|outdoor|the hut|thehutgroup|global e|intercoiffure", None),
    ("verzorging", "party", r"kruidvat|etos|douglas|rituals|kapper|barbier|time for hair|intercoiffure|haar|m\.r\.laundry|laundry", None),
    # --- Huis
    ("huis_inrichting", "party", r"solow|xenos|hema|action|jysk|ikea|praxis|gamma|hornbach|karwei|flying tiger|wibra|blokker|kwantum|leen bakker|meubel|bloem|bloemen|edb magnaplaza|lamor|riekerpolder|hoesjes|tritone|postnl|lockerbox|allekabels", None),
    ("online_shopping", "party", r"bol\.?com|bolcom|temu|amazon|amzn|aliexpress|wish\.com|shein|marktplaats", None),
    ("elektronica", "party", r"mediamarkt|^mm |coolblue|cameranu|thephonelab|apple store|samsung", None),
    # --- Kassasystemen zonder herkenbare naam: meestal horeca
    ("horeca", "party", r"^(ls |sq \*|zettle|sumup|sum up|sep\*|rap\*|pay\.nl\*)", None),
    ("terugbetaling", "desc", r"^refund", "in"),
]

# Tikkies en betaalverzoeken: de tegenpartij is een persoon, dus kijken we
# naar de omschrijving (waar ging het om?).
P2P = re.compile(r"tikkie|betaalverzoek", re.I)
P2P_R = [
    ("huur", "desc", r"\bhuur\b|\brent\b|\bborg\b", "out"),
    ("huurbijdrage", "desc", r"\bhuur\b|gas water licht", "in"),
    ("verkoop", "desc", r"overname|fiets|kast\b|bedframe|meubel|schaakspel|nachtlampje|lampje", "in"),
    ("gift_in", "desc", r"verjaardag|kado|cadeau", "in"),
    ("cadeaus", "desc", r"cadeau|kado|gift|bday|verjaardag|baby shower|bloemen", "out"),
    ("boodschappen", "desc", r"boodschappen|boters", "out"),
    ("sport", "desc", r"padel|boulder", "out"),
    ("terugbetaling", "party", r"tikkie|betaalverzoek", "in"),
    ("gedeeld", "party", r".", "out"),
]

RULES = [(c, f, re.compile(p, re.I), cond) for c, f, p, cond in R]
P2P_RULES = [(c, f, re.compile(p, re.I), cond) for c, f, p, cond in P2P_R]
# Merchant-regels ook op de omschrijving van een tikkie toepassen
P2P_MERCHANT = [(c, "desc", rx, cond) for c, f, rx, cond in RULES if f == "party" and c not in ("belasting",)]


def load_personal(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"own_ibans": [], "own_names": [], "rules": []}


def categorize(tx: dict, personal: dict) -> tuple[str, str]:
    """Geeft (categorie, reden) terug."""
    amt = tx["amount"]
    party = tx["party"] or ""
    desc = tx["desc"] or ""
    iban = (tx.get("iban") or "").replace(" ", "")

    # 1. Eigen rekeningen -> interne overboeking of sparen
    own = personal.get("own_ibans", {})
    if iban and iban in own:
        return own[iban], f"eigen rekening ({iban[-4:]})"

    # 2. Persoonlijke regels (eerst, want specifieker)
    for r in personal.get("rules", []):
        cond = r.get("when")
        if cond == "in" and amt <= 0 or cond == "out" and amt >= 0:
            continue
        if r.get("account") and r["account"] != tx["account"]:
            continue
        if r.get("before") and tx["date"] >= r["before"]:
            continue
        if r.get("after") and tx["date"] < r["after"]:
            continue
        hay = {"party": party, "desc": desc}.get(r.get("field", "any"), party + " " + desc)
        if re.search(r["match"], hay, re.I):
            return r["cat"], r.get("why", "persoonlijke regel")

    # 3. Algemene regels (tikkies: eerst op omschrijving)
    rules = RULES
    if P2P.search(party):
        rules = P2P_RULES[:-2] + P2P_MERCHANT + P2P_RULES[-2:]
    for cat, field, rx, cond in rules:
        if cond == "in" and amt <= 0 or cond == "out" and amt >= 0:
            continue
        hay = {"party": party, "desc": desc}.get(field, party + " " + desc)
        if rx.search(hay):
            return cat, f"regel: {rx.pattern[:40]}"

    # 4. Knab = zakelijke rekening: inkomende betalingen zijn omzet
    if amt > 0 and tx["account"] == "Knab zakelijk":
        return "omzet", "inkomend op zakelijke rekening"
    # 5. Terugbetalingen van een winkel tellen als min-uitgave
    if amt > 0 and tx["account"] == "Crypto.com kaart":
        return "terugbetaling", "kaart-refund"
    return "onbekend", "geen regel"
