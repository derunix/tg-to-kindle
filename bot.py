import os
import logging
import smtplib
from email.message import EmailMessage
from telegram import Update, Document
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import subprocess

# Загрузка конфигурации
KINDLE_EMAIL = os.getenv("KINDLE_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CONVERT_PATH = os.getenv("CONVERT_PATH", "/opt/ebook-convert")

logging.basicConfig(level=logging.INFO)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document
    if not doc.file_name.endswith(".fb2"):
        await update.message.reply_text("Принимаются только FB2 файлы.")
        return

    file = await doc.get_file()
    input_path = f"/tmp/{doc.file_unique_id}.fb2"
    output_path = input_path.replace(".fb2", ".epub")
    await file.download_to_drive(input_path)
    await update.message.reply_text("Конвертирую в EPUB...")

    try:
        subprocess.run([CONVERT_PATH, input_path, output_path], check=True)
    except subprocess.CalledProcessError:
        await update.message.reply_text("Ошибка при конвертации.")
        return

    await update.message.reply_text("Отправляю на Kindle...")

    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = SMTP_LOGIN
    msg["To"] = KINDLE_EMAIL
    msg.set_content("FB2 книга для Kindle")
    with open(output_path, "rb") as f:
        msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=os.path.basename(output_path))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        await update.message.reply_text(f"Ошибка отправки на почту: {e}")
        return

    await update.message.reply_text("Готово. Проверь Kindle.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
