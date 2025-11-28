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

def search_item(query):
    df = fetch_inventory()
    size = extract_size(query)


    if size:
        # Filter inventory by size
        df_filtered = df[df['size'].astype(str) == size]
        if df_filtered.empty:
            return f"No items found for size {size}"
    else:
        df_filtered = df

    names = df_filtered["name"].astype(str).tolist()
    
    
    if not names:
        return None

    match, score, idx = process.extractOne(
        query,
        names,
        scorer=fuzz.token_set_ratio
    )


    if score < 40:
        return None

    row = df_filtered.iloc[idx]
    return (
        "yes po available \n" 
        + row["name"] + "\n" +  
        f"Size: {row['size']}\n" + 
        f"Price: {row['price']}\n" + 
        f"Actual Picture: {row['url']}\n"
    )
      
    
