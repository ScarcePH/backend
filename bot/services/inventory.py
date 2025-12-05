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
    # if size:
    #     df = df[df["size"].astype(str) == str(size)]
    #     if df.empty:
    #         return {"found": False, "reason": "no_size"}

    # Fuzzy match product name
    names = df["name"].astype(str).str.lower().tolist()

    match = process.extractOne(
        item_name.lower(),
        names,
        scorer=fuzz.token_set_ratio
    )

    print("[MATCH]:", match)

    if not match or match[1] < 45:
        return {"found": False, "reason": "low_score"}

    matched_name, score, idx = match
    row = df.iloc[idx]
    print("ROW:", row.to_dict())

    if size and str(row["size"]) != str(size):
        return {"found": False, "reason": "size_mismatch", "name": row["name"]}
    return {
        "found": True,
        "name": row["name"],
        "size": str(row["size"])+"us",
        "price":str(row["price"]),
        "url": row["url"],
        "message": f"We have '{row['name']}' (Size: {row['size']}) \n  available for only ₱{row['price']}. \n You can check the details here: {row['url']}"
    }

def get_item_sizes(size,item):
    df = fetch_inventory()
    df_filtered = df[df["size"].astype(str) == str(size)]
    if df_filtered.empty:
        return []
    available_in_size = df_filtered["name"].astype(str).tolist()
    formatted_list = ", ".join(f"'{name}'" for name in available_in_size)
    return f"We don't have '{item}' in size {size}us. However, we do have the following items available in size {size}us: {formatted_list}."

