# Kindle Telegram Bot

A simple Telegram bot written in Python that accepts `.fb2` ebook files, converts them to `.epub` using Calibre's `ebook-convert`, and sends them to your Kindle via email.

Runs inside Docker. Requires a Kindle email address and SMTP credentials.

## Features

- Accepts `.fb2` files via Telegram
- Converts them to `.epub` using Calibre
- Sends converted books to your Kindle email
- Easy deployment with Docker Compose

## Requirements

- Telegram Bot Token (create via @BotFather)
- Kindle email address (e.g. yourname@kindle.com)
- SMTP mail server (e.g. Gmail with app password)
- Docker and Docker Compose installed

## Quick Start

1. Clone the repository:

```bash
git clone https://github.com/yourusername/kindle-telegram-bot.git
cd kindle-telegram-bot
```

2. Create a `.env` file in the root directory:

```ini
TELEGRAM_TOKEN=your_telegram_bot_token
KINDLE_EMAIL=your_kindle_email@kindle.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_LOGIN=your@gmail.com
SMTP_PASSWORD=your_app_password
```

3. Start the bot using Docker Compose:

```bash
docker-compose up -d --build
```

## Project Structure

```
.
├── bot.py              # Bot logic
├── Dockerfile          # Docker image
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── docker-compose.yml  # Service definition
└── README.md           # This file
```

## Development (without Docker)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Notes

- Only `.fb2` files are accepted by the bot.
- Make sure Calibre is able to convert FB2 to EPUB (standard functionality).

## License

MIT License
