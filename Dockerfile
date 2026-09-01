FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 5088

CMD ["sh","-c","[ -f data/physics_reality.db ] || python init_db.py; exec gunicorn --workers 1 --bind 0.0.0.0:5088 --timeout 120 app:app"]
