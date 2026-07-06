# BizQuery v0 — immagine dell'app FastAPI (step 6 del piano).
# Il Postgres NON sta qui: e' un servizio separato in docker-compose.

FROM python:3.12-slim

# Non generare .pyc e log non bufferizzati (log visibili subito in docker logs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# requirements prima del codice: se cambia solo il codice, questo layer (e il
# pip install) resta in cache e il build e' molto piu' veloce.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY eval ./eval

# Utente non-root: buona pratica, l'app web non deve girare come root.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
