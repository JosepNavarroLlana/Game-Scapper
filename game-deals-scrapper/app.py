import math
import threading

from flask import Flask, jsonify, render_template, request, redirect, url_for

from scraper.steam import (
    clear_cache,
    get_cached_games,
    get_scrape_progress,
    is_cache_valid,
    reset_scrape_progress,
    run_scrape,
)

app = Flask(__name__)

_scrape_thread: threading.Thread | None = None
_scrape_lock = threading.Lock()

MAX_GAMES = 50
ENRICH_LIMIT = 50


def is_best_deal(game: dict) -> bool:
    return game["discount_pct"] >= 75 and game["final_price"] <= 15


def _slider_limits(games: list[dict]) -> tuple[int, int]:
    prices = [g["final_price"] for g in games if g.get("final_price") is not None]
    discounts = [g["discount_pct"] for g in games if g.get("discount_pct") is not None]

    price_max = max(10, math.ceil(max(prices, default=45) / 5) * 5)
    discount_max = min(95, max(discounts, default=90))

    return price_max, discount_max


def _start_scrape_thread() -> bool:
    global _scrape_thread

    with _scrape_lock:
        if is_cache_valid():
            return False

        progress = get_scrape_progress()
        if progress["running"]:
            return True

        if _scrape_thread and _scrape_thread.is_alive():
            return True

        reset_scrape_progress()
        _scrape_thread = threading.Thread(
            target=run_scrape,
            kwargs={"max_games": MAX_GAMES, "enrich_limit": ENRICH_LIMIT},
            daemon=True,
        )
        _scrape_thread.start()
        return True


def _filter_games(all_games: list[dict]) -> tuple[list[dict], dict]:
    max_price = request.args.get("max_price", type=float)
    min_discount = request.args.get("min_discount", type=int)
    genre = request.args.get("genre", "")

    games = all_games

    if max_price is not None:
        games = [g for g in games if g["final_price"] <= max_price]
    if min_discount is not None:
        games = [g for g in games if g["discount_pct"] >= min_discount]
    if genre:
        games = [
            g for g in games
            if any(genre.lower() in tag.lower() for tag in g["genres"])
        ]

    for game in games:
        game["is_best_deal"] = is_best_deal(game)

    filters = {
        "max_price": max_price,
        "min_discount": min_discount,
        "genre": genre,
    }
    return games, filters


@app.route("/")
def dashboard():
    needs_scrape = not is_cache_valid()
    cached = get_cached_games() or []
    price_slider_max, discount_slider_max = _slider_limits(cached)

    games, filters = _filter_games(cached) if cached else ([], {
        "max_price": request.args.get("max_price", type=float),
        "min_discount": request.args.get("min_discount", type=int),
        "genre": request.args.get("genre", ""),
    })

    return render_template(
        "dashboard.html",
        games=games,
        needs_scrape=needs_scrape,
        max_price=filters["max_price"],
        min_discount=filters["min_discount"],
        genre=filters["genre"],
        price_slider_max=price_slider_max,
        discount_slider_max=discount_slider_max,
    )


@app.route("/api/start-scrape", methods=["POST"])
def start_scrape():
    if is_cache_valid():
        return jsonify({"running": False, "percent": 100, "message": "Data ready", "done": True})

    started = _start_scrape_thread()
    progress = get_scrape_progress()
    return jsonify({**progress, "done": False, "started": started})


@app.route("/api/scrape-status")
def scrape_status():
    progress = get_scrape_progress()
    done = is_cache_valid() and not progress["running"]
    return jsonify({**progress, "done": done})


@app.route("/refresh")
def refresh():
    clear_cache()
    reset_scrape_progress()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
