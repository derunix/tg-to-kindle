FROM python:3.14-slim-bookworm
RUN echo "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget xz-utils calibre ghostscript libarchive-tools unrar && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV CONVERT_PATH="/usr/bin/ebook-convert"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]
