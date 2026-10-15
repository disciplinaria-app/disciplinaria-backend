# Imagen oficial de Playwright con Chromium y sus dependencias del sistema.
FROM mcr.microsoft.com/playwright/python:v1.64.0-noble

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    CORPUS_DIR=/tmp/redactar2-corpus PLAYWRIGHT_HABILITADO=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "server.py"]
