FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    xz-utils \
    ghostscript \
    libarchive-tools \
    p7zip-full \
    ca-certificates \
    libegl1 \
    libopengl0 \
    libxcb-cursor0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Установка Calibre
RUN wget -O calibre-installer.sh https://download.calibre-ebook.com/linux-installer.sh && \
    bash calibre-installer.sh && \
    rm calibre-installer.sh

ENV CONVERT_PATH="/opt/calibre/ebook-convert"
CMD ["python", "bot.py"]