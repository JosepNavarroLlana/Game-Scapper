import re
import time
import requests
from bs4 import BeautifulSoup

url = "https://store.steampowered.com/search/results/"
headers = {"User-Agent": "GameDealsLearner/1.0 (educational project)"}

def _parse_precio(element) -> float | None:
    if element is None:
        return None
    text = element.get_text(strip=True)
    text = text.replace(",", ".")
    cleaned = re.sub(r'[^\d.]', '', text)
    return float(cleaned) if cleaned else None

def parse_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    games = []
    for row in soup.select("a.search_result_row"):
        title_el = row.select_one("span.title")
        discount_el = row.select_one("div.discount_pct")
        final_price_el = row.select_one("div.discount_final_price")
        original_price_el = row.select_one("div.discount_original_price")

        discount_text = discount_el.get_text(strip=True) if discount_el else ""
        discount_pct = int(re.sub(r'[^\d]', '', discount_text) or 0)

        games.append({
            "app_id": row.get("data-ds-appid"),
            "title": title_el.get_text(strip=True) if title_el else "",
            "url": row.get("href").split("?")[0],
            "discount_pct": discount_pct,
            "final_price": _parse_precio(final_price_el),
            "original_price": _parse_precio(original_price_el),
            "genres": [],
        })

    return games

def fetch_deals(max_games: int = 100) -> list[dict]:
    all_games = []
    start = 0
    page_size = 50

    while len(all_games) < max_games:
        params = {
            "specials": 1,
            "start": start,
            "count": page_size,
            "infinite": 1,
        }
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            break

        batch = parse_results(data["results_html"])
        if not batch:
            break

        all_games.extend(batch)
        start += page_size
        time.sleep(1)

    return all_games[:max_games]

if __name__ == "__main__":
    print("Descargando ofertas...")
    games = fetch_deals(max_games=100)
    print(f"Total: {len(games)} juegos\n")
    print("Primeros 10 juegos:")

    for game in games[:10]:
        print(f"{game['title']} — {game['discount_pct']}% — ${game['final_price']}")