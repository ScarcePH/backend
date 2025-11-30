# inventory.py
import pandas as pd
import requests
import time
from io import StringIO
from rapidfuzz import fuzz, process
import re


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
        cached_df = pd.read_csv(StringIO(resp.text), dtype={"size": str})
        last_fetched = now

    return cached_df



def extract_size(query):
    match = re.search(r'\b\d+(\.\d+)?\b', query)
    if match:
        return match.group(0)
    return None

def search_item(item_name, size=None):
    df = fetch_inventory()

    # Filter by size if provided
    if size:
        df = df[df["size"].astype(str) == str(size)]
        if df.empty:
            return {"found": False, "reason": "no_size"}

    # Fuzzy match product name
    names = df["name"].astype(str).tolist()

    match = process.extractOne(
        item_name,
        names,
        scorer=fuzz.token_set_ratio
    )

    if not match or match[1] < 40:
        return {"found": False, "reason": "low_score"}

    matched_name, score, idx = match
    row = df.iloc[idx]

    return {
        "found": True,
        "name": row["name"],
        "size": row["size"],
        "price": row["price"],
        "url": row["url"]
    }

