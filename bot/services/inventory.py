# inventory.py
import pandas as pd
import requests
import time
from io import StringIO
from rapidfuzz import fuzz, process
import re
from db.repository.inventory import get_all_inventory





def extract_size(query):
    match = re.search(r'\b\d+(\.\d+)?\b', query)
    if match:
        return match.group(0)
    return None

def search_item(item_name, size=None):
    items = get_all_inventory()
    names = [item["name"].lower() for item in items]

    match = process.extractOne(
        item_name.lower(),
        names,
        scorer=fuzz.token_set_ratio
    )

    print("[MATCH]:", match)

    if not match or match[1] < 45:
        return {"found": False, "reason": "low_score"}

    matched_name, score, idx = match
    row = items[idx]
    print("ROW:", row)

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
    items = get_all_inventory()

    filtered = [
        x["name"] for x in items
        if str(x["size"]) == str(size)
    ]

    if not filtered:
        return []

    formatted_list = ", ".join(f"'{name}'" for name in filtered)

    return (
        f"We don't have '{item}' in size {size}us. "
        f"However, these are available in size {size}us: {formatted_list}."
    )

