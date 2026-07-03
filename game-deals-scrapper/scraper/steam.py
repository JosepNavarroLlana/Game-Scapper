import re
import time
from typing import Any
import requests
import json
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "deals_cache.json"
CACHE_MAX_AGE_SECONDS = 3600

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

def save_cache(games: list[dict]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "games": games,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_cache_valid() -> bool:
    if not CACHE_FILE.exists():
        return False

    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data["cached_at"])
        age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
        return age_seconds < CACHE_MAX_AGE_SECONDS
    except (json.JSONDecodeError, KeyError, ValueError):
        return False

def load_cache() -> list[dict]:
    with open(CACHE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["games"]

def clear_cache() -> None:
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()

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

def fetch_genres(app_id: str) -> list[str]:
    game_url = f"https://store.steampowered.com/app/{app_id}/"
    response = requests.get(game_url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    tags = soup.select("a.app_tag")

    return [tag.get_text(strip=True) for tag in tags[:5]]

def enrich_with_genres(games: list[dict], limit: int = 50) -> list[dict]:
    for i, game in enumerate(games):
        if i >= limit:
            break
        if game.get("app_id"):
            game["genres"] = fetch_genres(game["app_id"])
            time.sleep(0.5)
    return games

def get_games(max_games: int = 50, enrich_limit: int = 50) -> list[dict]:
    if is_cache_valid():
        print("Usando caché")
        return load_cache()

    print("Scrapeando Steam...")
    games = fetch_deals(max_games=max_games)
    games = enrich_with_genres(games, limit=enrich_limit)
    save_cache(games)
    return games
    
if __name__ == "__main__":
    print("Descargando ofertas...")
    games = fetch_deals(max_games=100)
    print(f"Total: {len(games)} juegos\n")
    print("Primeros 10 juegos:")

    for game in games[:10]:
        print(f"{game['title']} — {game['discount_pct']}% — ${game['final_price']}")