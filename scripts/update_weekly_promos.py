#!/usr/bin/env python3
"""
Cloud Automated Daily Promotion Updater & Expired Offer Pruner for NutriBatch S26 Ultra
Runs automatically EVERY DAY via GitHub Actions (and locally via Antigravity).
1. Checks every promotion URL in weekly_data.json (Aldi, Colruyt, Carrefour, Delhaize, Intermarché).
2. Inspects both HTTP status (must be 200 OK) AND page content for expired brochure/offer indicators
   or passed validity dates (validUntil < today).
3. For Essential Items: if a promo link is expired or broken, automatically replaces it with a live
   verified product from the official Aldi Belgium XML sitemap so the 50/25/25 recipes never break.
4. For Optional Promos (Autres Promotions): automatically REMOVES any expired or unavailable promotion
   from the application so the user only ever sees active, valid promotions!
5. Enforces strict exclusions (Zero Pork, Zero Alcohol) and <= 70 EUR budget cap.
"""
from __future__ import annotations
import datetime
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "weekly_data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16; SM-S948B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36"
}

FORBIDDEN_REGEX = re.compile(
    r"\b(porc|varkens|jambon|ham|lardon|spek|saucisse|worst|bière|bier|vin|wijn|alcool|alcohol|vodka|whisky|rhum|gin)\b",
    re.IGNORECASE,
)

EXPIRED_MARKERS = [
    "deze folder is niet meer geldig",
    "ce folder n'est plus valable",
    "cette offre a expiré",
    "offre expirée",
    "niet meer beschikbaar",
    "page introuvable",
    "404 not found"
]


def is_offer_live_and_valid(url: str, valid_until: str | None, today_iso: str) -> bool:
    if valid_until and valid_until < today_iso:
        return False
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:
            if resp.status != 200:
                return False
            final_url = resp.geturl().lower()
            # If redirected to generic store homepage without offer/product, treat as expired
            if "myshopi.com" in url and "offer=" in url and "offer=" not in final_url and "folder" not in final_url:
                return False
            body = resp.read(32768).decode("utf-8", errors="ignore").lower()
            if any(marker in body for marker in EXPIRED_MARKERS):
                return False
            return True
    except Exception:
        return False


def fetch_aldi_sitemap_urls() -> list[str]:
    sitemap_url = "https://www.aldi.be/fr/sitemaps/.aldi-nord-sitemap-products.xml"
    try:
        req = urllib.request.Request(sitemap_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
        return re.findall(r"<loc>(https://www\.aldi\.be/fr/product/[^<]+)</loc>", xml_text)
    except Exception:
        return []


def compute_week_label() -> str:
    months = [
        "", "Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin",
        "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."
    ]
    today = datetime.date.today()
    end = today + datetime.timedelta(days=6)
    return f"Semaine du {today.day} {months[today.month]} au {end.day} {months[end.month]} {end.year}"


def main():
    if not DATA_FILE.exists():
        print("weekly_data.json not found.")
        return

    today = datetime.date.today()
    today_iso = today.isoformat()
    default_valid_until = (today + datetime.timedelta(days=6)).isoformat()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    aldi_urls = fetch_aldi_sitemap_urls()
    print(f"[{today_iso}] Loaded {len(aldi_urls)} product URLs from Aldi Belgium sitemap.")

    # 1. Verify Essential Items (heal broken/expired links from Aldi sitemap or prune if unhealable)
    active_essentials = []
    for item in data.get("essentialItems", []):
        name_lower = item.get("name", "").lower()
        assert not FORBIDDEN_REGEX.search(name_lower), f"Forbidden keyword in {item['name']}"

        url = item.get("url", "")
        valid_until = item.get("validUntil")
        if is_offer_live_and_valid(url, valid_until, today_iso):
            item["lastVerified"] = today_iso
            if not item.get("validUntil"):
                item["validUntil"] = default_valid_until
            active_essentials.append(item)
        else:
            print(f"Essential item expired or unreachable: {item['name']} ({url})")
            healed = False
            if aldi_urls:
                slug_words = [w for w in re.split(r"\W+", name_lower) if len(w) > 3]
                for candidate in aldi_urls:
                    if any(w in candidate for w in slug_words):
                        if is_offer_live_and_valid(candidate, None, today_iso):
                            item["url"] = candidate
                            item["store"] = "ALDI"
                            item["lastVerified"] = today_iso
                            item["validUntil"] = default_valid_until
                            active_essentials.append(item)
                            healed = True
                            print(f" -> Healed with active Aldi product URL: {candidate}")
                            break
            if not healed:
                print(f" -> Removed expired essential item: {item['name']}")

    data["essentialItems"] = active_essentials

    # 2. Verify Optional Promos (STRICTLY REMOVE any expired or non-200 promo)
    active_extras = []
    removed_extras = 0
    for ex in data.get("extraPromos", []):
        title_lower = (ex.get("title", "") + " " + ex.get("desc", "")).lower()
        if FORBIDDEN_REGEX.search(title_lower):
            removed_extras += 1
            continue

        url = ex.get("url", "")
        valid_until = ex.get("validUntil")
        if is_offer_live_and_valid(url, valid_until, today_iso):
            ex["lastVerified"] = today_iso
            if not ex.get("validUntil"):
                ex["validUntil"] = default_valid_until
            active_extras.append(ex)
        else:
            removed_extras += 1
            print(f"Removed expired optional promo: {ex.get('title')} ({url})")

    data["extraPromos"] = active_extras

    total_budget = round(sum(float(x["basePrice"]) for x in data.get("essentialItems", [])), 2)
    assert total_budget <= 70.0, f"Budget cap exceeded: {total_budget} EUR > 70.00 EUR"

    data["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data["lastDailyCheck"] = today.strftime("%d/%m/%Y")
    data["weekLabel"] = compute_week_label()

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Daily check complete ({data['lastDailyCheck']}): "
        f"{len(active_essentials)} essential items ({total_budget:.2f} EUR), "
        f"{len(active_extras)} active optional promos ({removed_extras} expired removed)."
    )


if __name__ == "__main__":
    main()
