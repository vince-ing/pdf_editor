FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required by sounddevice, soundfile, and OCR
RUN apt-get update && apt-get install -y \
    libportaudio2 \
    libsndfile1 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the engine directory into the container
COPY engine/ ./engine/

EXPOSE 7860

# Ensure Python can find the 'engine' module
ENV PYTHONPATH=/app

# Start the FastAPI server
CMD ["uvicorn", "engine.src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]