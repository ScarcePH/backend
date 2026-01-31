import io
import re
import datetime
import numpy as np
from PIL import Image
import pytesseract
import cv2

MAX_SIZE = 1 * 1024 * 1024  # 1MB
MAX_WIDTH = 1000

DATE_REGEX = r'(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},\s\d{4})'

TRANSACTION_KEYWORDS = r'(GCash|Maya|BPI|BDO|Bank|Send Money|Payment Successful|Paid to|You paid|Transfer|Transaction Successful|Transfer Successful|Transaction Receipt)'


def normalize_date(date_str: str):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None


def ocr_is_valid_payment_today(file_bytes: bytes):

    # --- Load image ---
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")

    # --- Resize ---
    w, h = img.size
    if w > MAX_WIDTH:
        ratio = MAX_WIDTH / float(w)
        img = img.resize((MAX_WIDTH, int(h * ratio)), Image.LANCZOS)

    # --- Compress to <=1MB ---
    quality = 85
    buffer = io.BytesIO()

    while True:
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)

        if buffer.tell() <= MAX_SIZE or quality <= 40:
            break
        quality -= 5

    # --- Preprocess with OpenCV ---
    np_img = np.frombuffer(buffer.getvalue(), np.uint8)
    cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 2
    )

    # --- OCR with Tesseract ---
    custom_config = r'--oem 3 --psm 6'
    full_text = pytesseract.image_to_string(thresh, config=custom_config)

    if not full_text:
        return {"is_valid": False}

    # --- Keyword check ---
    if not re.search(TRANSACTION_KEYWORDS, full_text, re.IGNORECASE):
        return {"is_valid": False}

    # --- Date check ---
    date_match = re.search(DATE_REGEX, full_text)
    if not date_match:
        return {"is_valid": False}

    extracted_date = normalize_date(date_match.group(0))
    if not extracted_date or extracted_date != datetime.date.today():
        return {"is_valid": False}

    return {"is_valid": True}
