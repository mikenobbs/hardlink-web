FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    xattr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app.py /app/app.py
COPY templates /app/templates
COPY static /app/static

RUN pip install --no-cache-dir flask pyyaml

RUN python -c "import secrets; open('/app/.secret_key', 'w').write(secrets.token_hex(32))"

EXPOSE 8088

CMD ["python", "/app/app.py"]