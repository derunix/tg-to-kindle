import os
import logging
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path
from telegram import Update, Document
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список поддерживаемых форматов, которые можно отправлять на Kindle без конвертации
SUPPORTED_KINDLE_EXTENSIONS = {
    ".epub", ".pdf", ".doc", ".docx", ".rtf", ".txt",
    ".html", ".htm", ".azw", ".azw3", ".azw4",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif"
}

# Загрузка переменных окружения
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CONVERT_PATH = os.getenv("CONVERT_PATH", "/usr/bin/ebook-convert")

# Основная логика обработки документа
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document
    ext = Path(doc.file_name).suffix.lower()

    if not ext:
        await update.message.reply_text("❌ Cannot determine file type.")
        return

    file = await doc.get_file()
    input_path = f"/tmp/{doc.file_unique_id}{ext}"
    output_path = input_path

    await file.download_to_drive(input_path)
    logger.info(f"Downloaded: {input_path}")

    # Если формат не поддерживается — конвертируем в EPUB
    if ext not in SUPPORTED_KINDLE_EXTENSIONS:
        output_path = str(Path(input_path).with_suffix(".epub"))
        await update.message.reply_text(f"⚙️ Converting {ext} to EPUB...")

        try:
            subprocess.run([CONVERT_PATH, input_path, output_path], check=True)
            logger.info(f"Converted: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e}")
            await update.message.reply_text("❌ Conversion failed.")
            return

    await update.message.reply_text("📤 Sending to Kindle...")

    # Подготовка и отправка письма
    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = SMTP_LOGIN
    msg["To"] = KINDLE_EMAIL
    msg.set_content("Document for Kindle")

    with open(output_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=Path(output_path).name)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Sent: {output_path} to {KINDLE_EMAIL}")
    except Exception as e:
        logger.error(f"Email error: {e}")
        await update.message.reply_text(f"❌ Email send failed: {e}")
        return

    await update.message.reply_text("✅ Done. Check your Kindle.")

# Запуск бота
def main():
    if not TELEGRAM_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN in environment")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    logger.info("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()