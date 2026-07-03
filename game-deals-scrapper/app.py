from flask import Flask, render_template, request
from scraper.steam import enrich_with_genres, fetch_deals

app = Flask(__name__)

def is_best_deal(game: dict) -> bool:
    return game["discount_pct"] >= 75 and game["final_price"] <= 15

@app.route("/")
def dashboard():
    max_price = request.args.get("max_price", type=float)
    min_discount = request.args.get("min_discount", type=int)

    games = fetch_deals(max_games=50)
    games = enrich_with_genres(games, limit=30)

    genre = request.args.get("genre", "")

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

    return render_template("dashboard.html", games=games, max_price=max_price, min_discount=min_discount, genre=genre,)

if __name__ == "__main__":
    app.run(debug=True, port=5000)