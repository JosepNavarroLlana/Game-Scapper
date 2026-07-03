import requests

steam_url = "https://store.steampowered.com/search/results/"

params = {
    "specials": 1,
    "start": 0,
    "count": 5,
    "infinite": 1,
}

headers = {
    "User-Agent": "GameDealsLearner/1.0 (educational project)"
}

response = requests.get(steam_url, params=params, headers=headers, timeout=15)

response.raise_for_status()

data = response.json()

print("¿Exito?", data.get("success"))
print("Total de resultados:", data.get("total_count"))
print()
print("Primeros 300 caracteres del HTML embebido:")
print(data.get("results_html", "")[:300])