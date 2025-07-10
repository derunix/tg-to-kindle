import os
import logging
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path
from telegram import Update, Document
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Поддерживаемые Kindle форматы
SUPPORTED_KINDLE_EXTENSIONS = {
    ".epub", ".pdf", ".doc", ".docx", ".rtf", ".txt",
    ".html", ".htm", ".azw", ".azw3", ".azw4",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif"
}

# Переменные окружения
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CONVERT_PATH = os.getenv("CONVERT_PATH", "/usr/bin/ebook-convert")
METADATA_TOOL = os.getenv("METADATA_TOOL", "/usr/bin/ebook-meta")
DEFAULT_COVER = os.getenv("DEFAULT_COVER", "/app/default_cover.jpg")

def extract_metadata(epub_path: str) -> dict:
    """Чтение метаданных из EPUB через ebook-meta"""
    try:
        result = subprocess.run(
            [METADATA_TOOL, epub_path],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.splitlines()
        meta = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"title", "author(s)", "authors"}:
                meta[key] = value
        return meta
    except Exception as e:
        logger.warning(f"Metadata read failed: {e}")
        return {}

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document

    # Получаем расширение
    file_name = doc.file_name if doc.file_name else f"{doc.file_unique_id}"
    ext = Path(file_name).suffix.lower()
    if not ext:
        await update.message.reply_text("❌ Cannot determine file extension.")
        return

    # Пути
    raw_input_path = f"/tmp/{doc.file_unique_id}{ext}"
    await doc.get_file().download_to_drive(raw_input_path)
    logger.info(f"Downloaded: {raw_input_path}")

    input_path = raw_input_path
    output_path = input_path

    if ext not in SUPPORTED_KINDLE_EXTENSIONS:
        output_path = str(Path(input_path).with_suffix(".epub"))
        await update.message.reply_text(f"⚙️ Converting {ext} to EPUB...")

        try:
            cmd = [CONVERT_PATH, input_path, output_path]
            # если PDF — добавляем обложку
            if ext == ".pdf" and os.path.exists(DEFAULT_COVER):
                cmd += ["--cover", DEFAULT_COVER]

            subprocess.run(cmd, check=True)
            logger.info(f"Converted: {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Conversion failed: {e}")
            await update.message.reply_text("❌ Conversion failed.")
            return

        # Переименование на основе метаданных
        meta = extract_metadata(output_path)
        title = meta.get("title", "").strip()
        author = meta.get("author(s)", meta.get("authors", "")).strip()

        if title or author:
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
            safe_author = "".join(c for c in author if c.isalnum() or c in " _-").strip()
            final_name = f"{safe_author} - {safe_title}".strip(" -") + ".epub"
        else:
            original_stem = Path(file_name).stem
            final_name = original_stem + ".epub"

        final_output_path = f"/tmp/{final_name}"
        os.rename(output_path, final_output_path)
        output_path = final_output_path
        logger.info(f"Final filename: {output_path}")
    else:
        # даже для поддерживаемых файлов переименуем, если имя отсутствует
        if not doc.file_name:
            output_path = f"/tmp/{doc.file_unique_id}{ext}"
            os.rename(input_path, output_path)
            logger.info(f"Renamed to readable name: {output_path}")

    await update.message.reply_text("📤 Sending to Kindle...")

    # Email
    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = SMTP_LOGIN
    msg["To"] = KINDLE_EMAIL
    msg.set_content("Document for Kindle")

    with open(output_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="octet-stream",
            filename=Path(output_path).name
        )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Sent to {KINDLE_EMAIL}: {output_path}")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        await update.message.reply_text(f"❌ Failed to send email: {e}")
        return

    await update.message.reply_text("✅ Done. Check your Kindle.")

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