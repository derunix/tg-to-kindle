# Kindle Telegram Bot

A simple Telegram bot written in Python that accepts `.fb2` ebook files, converts them to `.epub` using Calibre's `ebook-convert`, and sends them to your Kindle via email.

Runs inside Docker. Requires a Kindle email address and SMTP credentials.

## Features

- Accepts `.fb2` files via Telegram
- Converts them to `.epub` using Calibre
- Sends converted books to your Kindle email
- Easy deployment with Docker Compose
- Accepts manga and comic book archives in `.zip`, `.cbz`, or `.cbr` formats

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

2. Create a `.env` file.  in the root directory:

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
- ZIP, CBZ, and CBR files are treated as comic books and sent as-is without conversion.

## License

MIT License

# Telegram Kindle Bot

A Telegram bot that accepts `.fb2` and `.cbr` books, automatically converts them to `.epub` and emails them to your Kindle.

## Features

- Accepts `.fb2` and `.cbr` files via Telegram
- Converts to `.epub` using Calibre
- Adds ISBN or ASIN when possible
- Sends to user's Kindle email address
- Each user can register their own Kindle address
- Admin receives logs of all uploads

## Usage

- Send the bot an `.fb2` or `.cbr` file
- It will convert and send the result to your Kindle
- Use `/email` to set or update your Kindle address
- Use `/help` for usage info

## Format Support

- Input: `.fb2`, `.zip` (with `.fb2`), `.cbr`
- Output: `.epub` with embedded metadata

## License

MIT