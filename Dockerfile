FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: API (webapp). Bot: docker compose --profile telegram up -d
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
