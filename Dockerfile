FROM python:3.11-slim

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
    libxkbcommon0 \
    libgl1 \
    libglib2.0-0 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libqt5gui5 \
    imagemagick \
    libqt5widgets5 \
    && rm -rf /var/lib/apt/lists/*
# Разрешаем обработку PDF в ImageMagick
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/' /etc/ImageMagick*/policy.xml
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .
COPY unzip_safe.py /app/unzip_safe.py
# Установка Calibre
RUN wget -O calibre-installer.sh https://download.calibre-ebook.com/linux-installer.sh && \
    bash calibre-installer.sh && \
    rm calibre-installer.sh

ENV CONVERT_PATH="/opt/calibre/ebook-convert"
CMD ["python", "bot.py"]