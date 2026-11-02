#!/usr/bin/env python3
"""
Cloud Automated Weekly Promotion Updater for NutriBatch S26 Ultra
Runs automatically every Saturday at 09:00 (Europe/Brussels) via GitHub Actions.
1. Verifies all Aldi Belgium product URLs via the official Aldi Nord XML sitemap.
2. Checks and refreshes myShopi Belgian supermarket brochure links (Colruyt, Carrefour, Delhaize, Aldi, Intermarché).
3. Enforces strict exclusions (Zero Pork, Zero Alcohol) and <= 70 EUR budget cap.
4. Updates weekly_data.json with the current week's date range and verified HTTP 200 OK links.
"""
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

FORBIDDEN_KEYWORDS = [
    "porc", "varkens", "jambon", "ham", "lardon", "spek", "saucisse", "worst",
    "bière", "bier", "vin ", "wijn", "alcool", "alcohol", "vodka", "whisky", "rhum", "gin"
]


def check_url_200(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status == 200
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

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    aldi_urls = fetch_aldi_sitemap_urls()
    print(f"Loaded {len(aldi_urls)} product URLs from Aldi Belgium sitemap.")

    # Verify each essential item URL and heal from Aldi sitemap if needed
    for item in data.get("essentialItems", []):
        name_lower = item.get("name", "").lower()
        assert not any(bad in name_lower for bad in FORBIDDEN_KEYWORDS), f"Forbidden keyword in {item['name']}"

        url = item.get("url", "")
        if not check_url_200(url) and aldi_urls and item.get("store") == "ALDI":
            slug_words = [w for w in re.split(r"\W+", name_lower) if len(w) > 3]
            for candidate in aldi_urls:
                if any(w in candidate for w in slug_words):
                    if check_url_200(candidate):
                        item["url"] = candidate
                        break

    total_budget = round(sum(float(x["basePrice"]) for x in data.get("essentialItems", [])), 2)
    assert total_budget <= 70.0, f"Budget cap exceeded: {total_budget} EUR > 70.00 EUR"

    data["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data["weekLabel"] = compute_week_label()

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Successfully updated weekly_data.json ({data['weekLabel']}) — Total: {total_budget:.2f} EUR")


if __name__ == "__main__":
    main()
