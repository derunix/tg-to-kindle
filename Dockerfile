FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget xz-utils calibre && \
    rm -rf /var/lib/apt/lists/*

ENV CONVERT_PATH="/usr/bin/ebook-convert"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .

CMD ["python", "bot.py"]
