FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUTF8=1
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8545 8080 5000 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=3)"

CMD ["python", "main.py", "--config", "docker/node1.json"]
