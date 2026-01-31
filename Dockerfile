FROM python:3.9-slim

# Install system dependencies (tesseract + OpenCV runtime deps)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Render uses 10000 by default)
EXPOSE 10000

# Start Flask app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
