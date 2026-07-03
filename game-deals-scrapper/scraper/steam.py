import math
import re
import time
from typing import Callable
import requests
import json
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "deals_cache.json"
CACHE_MAX_AGE_SECONDS = 3600

url = "https://store.steampowered.com/search/results/"
headers = {"User-Agent": "GameDealsLearner/1.0 (educational project)"}
age_cookies = {"birthtime": "568022401", "lastagecheckage": "1-0-1988", "mature_content": "1"}

_scrape_progress = {
    "running": False,
    "percent": 0,
    "message": "",
    "error": None,
}

ProgressCallback = Callable[[int, str], None]

def get_scrape_progress() -> dict:
    return dict(_scrape_progress)

def _set_progress(percent: int, message: str) -> None:
    _scrape_progress["percent"] = percent
    _scrape_progress["message"] = message

def reset_scrape_progress() -> None:
    _scrape_progress.update({
        "running": False,
        "percent": 0,
        "message": "",
        "error": None,
    })

def _parse_price(element) -> float | None:
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
            "final_price": _parse_price(final_price_el),
            "original_price": _parse_price(original_price_el),
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

def fetch_deals(
    max_games: int = 100,
    on_progress: ProgressCallback | None = None,
) -> list[dict]:
    all_games = []
    start = 0
    page_size = 50
    pages_needed = max(1, math.ceil(max_games / page_size))
    page_num = 0

    if on_progress:
        on_progress(2, "Connecting to Steam...")

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
        page_num += 1
        start += page_size

        if on_progress:
            pct = min(40, int((page_num / pages_needed) * 40))
            on_progress(pct, f"Downloading deals ({len(all_games)} games)...")

        time.sleep(1)

    return all_games[:max_games]

def fetch_genres(app_id: str) -> list[str]:
    game_url = f"https://store.steampowered.com/app/{app_id}/"
    response = requests.get(
        game_url,
        headers=headers,
        cookies=age_cookies,
        timeout=15,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    official = [
        a.get_text(strip=True)
        for a in soup.select('div#genresAndManufacturer a[href*="/genre/"]')
    ]
    tags = [tag.get_text(strip=True) for tag in soup.select("a.app_tag")]

    combined = []
    seen = set()
    for label in official + tags:
        key = label.lower()
        if key not in seen:
            seen.add(key)
            combined.append(label)
        if len(combined) >= 8:
            break

    return combined

def enrich_with_genres(
    games: list[dict],
    limit: int = 50,
    on_progress: ProgressCallback | None = None,
) -> list[dict]:
    to_enrich = min(limit, len(games))

    for i, game in enumerate(games):
        if i >= limit:
            break
        if game.get("app_id"):
            game["genres"] = fetch_genres(game["app_id"])
            time.sleep(0.5)

            if on_progress and to_enrich > 0:
                pct = 40 + int(((i + 1) / to_enrich) * 55)
                on_progress(pct, f"Fetching genres ({i + 1}/{to_enrich})...")

    return games

def get_cached_games() -> list[dict] | None:
    if is_cache_valid():
        return load_cache()
    return None

def run_scrape(max_games: int = 50, enrich_limit: int = 50) -> None:
    if _scrape_progress["running"]:
        return

    _scrape_progress["running"] = True
    _scrape_progress["error"] = None

    try:
        games = fetch_deals(max_games=max_games, on_progress=_set_progress)
        games = enrich_with_genres(games, limit=enrich_limit, on_progress=_set_progress)
        _set_progress(98, "Saving data...")
        save_cache(games)
        _set_progress(100, "Done!")
    except Exception as exc:
        _scrape_progress["error"] = str(exc)
        _set_progress(0, f"Error: {exc}")
    finally:
        _scrape_progress["running"] = False

def get_games(max_games: int = 50, enrich_limit: int = 50) -> list[dict]:
    cached = get_cached_games()
    if cached is not None:
        print("Using cache")
        return cached

    print("Scraping Steam...")
    run_scrape(max_games=max_games, enrich_limit=enrich_limit)
    return load_cache()

if __name__ == "__main__":
    print("Downloading deals...")
    games = fetch_deals(max_games=100)
    print(f"Total: {len(games)} games\n")
    print("First 10 games:")

    for game in games[:10]:
        print(f"{game['title']} — {game['discount_pct']}% — {game['final_price']}€")