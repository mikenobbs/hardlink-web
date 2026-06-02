FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    xattr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
COPY static ./static
COPY config/config.yml ./config.yml
COPY entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8088

CMD ["/app/entrypoint.sh"]
