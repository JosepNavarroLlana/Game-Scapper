import math

from flask import Flask, render_template, request, redirect, url_for
from scraper.steam import get_games, clear_cache

app = Flask(__name__)

def is_best_deal(game: dict) -> bool:
    return game["discount_pct"] >= 75 and game["final_price"] <= 15

def _slider_limits(games: list[dict]) -> tuple[int, int]:
    prices = [g["final_price"] for g in games if g.get("final_price") is not None]
    discounts = [g["discount_pct"] for g in games if g.get("discount_pct") is not None]

    price_max = max(10, math.ceil(max(prices, default=45) / 5) * 5)
    discount_max = min(95, max(discounts, default=90))

    return price_max, discount_max

@app.route("/")
def dashboard():
    max_price = request.args.get("max_price", type=float)
    min_discount = request.args.get("min_discount", type=int)

    all_games = get_games(max_games=50, enrich_limit=50)
    price_slider_max, discount_slider_max = _slider_limits(all_games)

    genre = request.args.get("genre", "")
    games = all_games

    if max_price is not None:
        games = [game for game in games if game["final_price"] <= max_price]
    if min_discount is not None:
        games = [game for game in games if game["discount_pct"] >= min_discount]

    if genre:
        games = [
            game for game in games
            if any(genre.lower() in tag.lower() for tag in game["genres"])
        ]

    for game in games:
        game["is_best_deal"] = is_best_deal(game)

    return render_template(
        "dashboard.html",
        games=games,
        max_price=max_price,
        min_discount=min_discount,
        genre=genre,
        price_slider_max=price_slider_max,
        discount_slider_max=discount_slider_max,
    )
@app.route("/refresh")
def refresh():
    clear_cache()
    return redirect(url_for("dashboard"))
    
if __name__ == "__main__":
    app.run(debug=True, port=5000)