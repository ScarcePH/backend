# inventory.py
import pandas as pd
import requests
import time
from io import StringIO
from rapidfuzz import fuzz, process


CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQjTnALFVTW7bt3BalkFrg_ZxrTl-hZuGPmBvbY4GgpI9evedpQJCpELAvx5MWdb9uAW3sKJq9QVYSi/pub?output=csv"

cached_df = None
last_fetched = 0
CACHE_TTL = 300  # 5 minutes

def fetch_inventory():
    global cached_df, last_fetched

    now = time.time()
    if cached_df is None or (now - last_fetched) > CACHE_TTL:
        resp = requests.get(CSV_URL)
        resp.raise_for_status()
        cached_df = pd.read_csv(StringIO(resp.text))
        last_fetched = now

    return cached_df


def search_item(query):
    df = fetch_inventory()
    names = df["name"].astype(str).tolist()

    match, score, idx = process.extractOne(
        query,
        names,
        scorer=fuzz.token_set_ratio
    )

    if score < 35:  # adjust threshold
        return "Item not found."

    row = df.iloc[idx]
    return {
        "name": row["name"],
        "size": int(row["size"]),
        "price": int(row["price"]),
        "score": score
    }
