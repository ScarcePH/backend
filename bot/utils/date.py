from datetime import datetime

def parse_date(date_str, end=False):
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    if end:
        return dt.replace(hour=23, minute=59, second=59)

    return dt.replace(hour=0, minute=0, second=0)