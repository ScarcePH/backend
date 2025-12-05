import re

def extract_size(query):
    match = re.search(r'\d+(?:\.\d+)?', query)
    if match:
        return match.group(0)
    return None