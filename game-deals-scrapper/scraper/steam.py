import re
from bs4 import BeautifulSoup

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

if __name__ == "__main__":
    import requests

    url = "https://store.steampowered.com/search/results/"
    params = {"specials": 1, "start": 0, "count": 5, "infinite": 1}
    headers = {"User-Agent": "GameDealsLearner/1.0 (educational project)"}

    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()

    data = response.json()
    games = parse_results(data["results_html"])

    print(f"Juegos encontrados: {len(games)}\n")

    for game in games:
        print(f"{game['title']}")
        print(f"  Descuento: {game['discount_pct']}%")
        print(f"  Precio: ${game['original_price']} → ${game['final_price']}")
        print(f"  URL: {game['url']}")
        print()