from telegram.request import HTTPXRequest
from httpx import Timeout
import os
import logging
import smtplib
import sqlite3
import subprocess
from email.message import EmailMessage
from pathlib import Path
import rarfile
import re
import requests
from unzip_safe import unzip_safe

def compress_pdf(input_path: str, output_path: str) -> bool:
    try:
        subprocess.run([
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook",
            "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={output_path}",
            input_path
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Ghostscript compression failed: {e}")
        return False

def guess_author_title_from_filename(name: str) -> tuple[str, str]:
    name = Path(name).stem
    if " - " in name:
        parts = name.split(" - ", 1)
        author = parts[0].strip()
        title = parts[1].strip()
        return author, title
    return "", name.strip()

# --- Поиск ISBN по названию и автору ---
def find_isbn_by_title_author(title: str, author: str) -> str | None:
    query = f"{title} {author}".strip()
    try:
        resp = requests.get("https://www.googleapis.com/books/v1/volumes", params={"q": query})
        if resp.ok:
            data = resp.json()
            for item in data.get("items", []):
                industry_ids = item.get("volumeInfo", {}).get("industryIdentifiers", [])
                for id_entry in industry_ids:
                    if id_entry["type"] in {"ISBN_10", "ISBN_13"}:
                        return id_entry["identifier"]
    except Exception as e:
        logger.warning(f"Failed to fetch ISBN: {e}")
    return None


# --- Поиск ASIN по названию и автору ---
def find_asin_by_title_author(title: str, author: str) -> str | None:
    query = f"{title} {author}".strip()
    # Try to use ISBN as ASIN directly if available
    isbn = find_isbn_by_title_author(title, author)
    if isbn:
        logger.info(f"Using ISBN as ASIN directly: {isbn}")
        return f"amazon:{isbn}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    logger.info(f"Searching ASIN for: {query}")
    try:
        resp = requests.get("https://www.amazon.com/s", params={"k": query}, headers=headers, timeout=10)
        if resp.ok:
            matches = re.findall(r"/dp/([A-Z0-9]{10})", resp.text)
            logger.info(f"ASIN raw matches: {matches}")
            if matches:
                logger.info(f"Using ASIN: {matches[0]}")
                return matches[0]
            else:
                logger.info("No ASIN found in page.")
        else:
            logger.warning(f"Amazon search failed: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to fetch ASIN: {e}")
    return None

from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Конфигурация ---
DB_PATH = os.getenv("DB_PATH", "/data/users.db")
DEFAULT_COVER = os.getenv("DEFAULT_COVER", "/app/default_cover.jpg")
CONVERT_PATH = os.getenv("CONVERT_PATH", "/usr/bin/ebook-convert")
METADATA_TOOL = os.getenv("METADATA_TOOL", "/usr/bin/ebook-meta")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

SUPPORTED_KINDLE_EXTENSIONS = {
    ".epub", ".pdf", ".doc", ".docx", ".rtf", ".txt",
    ".html", ".htm", ".azw", ".azw3", ".azw4",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif",
    ".zip", ".cbz", ".cbr"  # Manga/Comic archives
}

# --- Логгирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Инициализация базы ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
    conn.commit()
    conn.close()

def set_email(user_id: int, email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("REPLACE INTO users (user_id, email) VALUES (?, ?)", (user_id, email))
    conn.commit()
    conn.close()

def get_email(user_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT email FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# --- Метаданные из EPUB ---
def extract_metadata(epub_path: str) -> dict:
    try:
        result = subprocess.run([METADATA_TOOL, epub_path], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        meta = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                if key in {"title", "author(s)", "authors"}:
                    meta[key] = value
        return meta
    except Exception as e:
        logger.warning(f"Metadata read failed: {e}")
        return {}

# --- Команды Telegram ---
async def cmd_setemail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /setemail your_kindle_email@kindle.com")
        return
    email = context.args[0]
    set_email(update.effective_user.id, email)
    await update.message.reply_text(f"✅ Kindle email set to: {email}")

async def cmd_getemail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = get_email(update.effective_user.id)
    if email:
        await update.message.reply_text(f"📬 Your Kindle email: {email}")
    else:
        await update.message.reply_text("ℹ️ You have not set a Kindle email yet. Use /setemail to configure.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>📚 Kindle Bot Help</b>\n\n"
        "This bot converts and sends files to your Kindle.\n\n"
        "<b>Commands:</b>\n"
        "/setemail your_email@kindle.com — set or change your Kindle email\n"
        "/getemail — show current email\n"
        "/help — show this help\n\n"
        "Just send a book file (FB2, PDF, DOCX, etc) — it will be converted and sent to your Kindle.\n"
        "✅ Supports metadata and auto renaming.\n"
        "<i>Note: Make sure your Kindle email allows delivery from this bot's email.</i>",
        parse_mode="HTML"
    )


# --- Основная логика получения файла ---
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.username or update.effective_user.full_name or f"id:{user_id}"
    kindle_email = get_email(user_id)
    if ADMIN_USER_ID and str(user_id) != str(ADMIN_USER_ID):
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"👤 User @{user_name} uploaded file: {update.message.document.file_name or update.message.document.file_unique_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin: {e}")
    if not kindle_email:
        await update.message.reply_text("⚠️ Please set your Kindle email first using /setemail.")
        return

    doc: Document = update.message.document
    file_name = doc.file_name or f"{doc.file_unique_id}"
    ext = Path(file_name).suffix.lower()

    if not ext:
        await update.message.reply_text("❌ Cannot determine file extension.")
        return

    raw_input_path = f"/tmp/{doc.file_unique_id}{ext}"

    # Check file size before downloading
    if doc.file_size and doc.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ File too large. Telegram bots can only download files up to 50 MB.")
        return

    telegram_file = await doc.get_file()
    await telegram_file.download_to_drive(raw_input_path)
    logger.info(f"Downloaded: {raw_input_path}")

    # Сжимаем PDF при необходимости
    if ext == ".pdf":
        compressed_path = raw_input_path.replace(".pdf", "_compressed.pdf")
        if compress_pdf(raw_input_path, compressed_path):
            raw_input_path = compressed_path
            logger.info(f"PDF compressed to {raw_input_path}")
    elif ext in [".zip", ".cbz"]:
        import tempfile
        from unzip_safe import unzip_safe

        extract_dir = tempfile.mkdtemp()
        try:
            unzip_safe(raw_input_path, extract_dir)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to extract archive: {e}")
            return

        fb2_files = sorted(Path(extract_dir).rglob("*.fb2"))
        if fb2_files:
            raw_input_path = str(fb2_files[0])
            ext = ".fb2"
        else:
            # Проверка изображений как манга/комикс
            image_files = sorted([
                str(p) for p in Path(extract_dir).rglob("*")
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ])
            if not image_files:
                await update.message.reply_text("❌ ZIP does not contain FB2 or supported images.")
                return

            # Конвертация изображений в EPUB (аналогично как было до этого)
            author, title = guess_author_title_from_filename(file_name)
            title = title or "Untitled Manga"
            author = author or "Unknown"

            safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
            safe_author = "".join(c for c in author if c.isalnum() or c in " _-").strip()
            base_name = f"{safe_author} - {safe_title}".strip(" -")

            epub_output = f"/tmp/{base_name}.epub"
            input_html = os.path.join(extract_dir, f"{base_name}.html")
            cover_image_path = image_files[0]

            with open(input_html, "w") as f:
                f.write('<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<meta charset="utf-8"/>\n')
                f.write(f"<title>{title}</title></head>\n<body>\n")
                for img_path in image_files:
                    rel_path = os.path.relpath(img_path, extract_dir)
                    f.write(f'<div><img src="{rel_path}" style="width:100%;"/></div>\n')
                f.write("</body>\n</html>\n")

            try:
                subprocess.run([CONVERT_PATH, input_html, epub_output, "--cover", cover_image_path, "--page-breaks-before", "/"], check=True)
                raw_input_path = epub_output
                ext = ".epub"
            except subprocess.CalledProcessError as e:
                await update.message.reply_text("❌ Failed to convert manga archive.")
                return
    elif ext == ".cbr":
        import tempfile
        import rarfile
        import shutil

        with rarfile.RarFile(raw_input_path) as rar:
            extract_dir = tempfile.mkdtemp()
            rar.extractall(extract_dir)
            logger.info(f"Extracted CBR to {extract_dir}")

        author, title = guess_author_title_from_filename(file_name)
        title = title or "Untitled Manga"
        author = author or "Unknown"

        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
        safe_author = "".join(c for c in author if c.isalnum() or c in " _-").strip()
        base_name = f"{safe_author} - {safe_title}".strip(" -")

        epub_output = f"/tmp/{base_name}.epub"

        image_files = sorted([
            str(p) for p in Path(extract_dir).rglob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ])

        if not image_files:
            await update.message.reply_text("❌ CBR does not contain supported images.")
            return

        cover_image_path = image_files[0]
        input_html = os.path.join(extract_dir, f"{base_name}.html")

        with open(input_html, "w") as f:
            f.write('<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<meta charset="utf-8"/>\n')
            f.write(f"<title>{title}</title>")
            f.write("</head>\n")
            f.write("<body>\n")
            for img_path in image_files:
                rel_path = os.path.relpath(img_path, extract_dir)
                f.write(f'<div><img src="{rel_path}" style="width:100%;"/></div>\n')
            f.write("</body>\n</html>\n")

        # await update.message.reply_document(document=open(input_html, "rb"), filename=Path(input_html).name)

        # --- EPUB conversion with input_html/epub_output collision check ---
        if os.path.abspath(input_html) == os.path.abspath(epub_output):
            epub_output = epub_output.replace(".epub", "_converted.epub")
            pass
        cmd = [CONVERT_PATH, input_html, epub_output, "--cover", cover_image_path, "--page-breaks-before", "/"]
        try:
            subprocess.run(cmd, check=True)
            logger.info(f"Converted CBR to EPUB: {epub_output}")
            # Make sure input_path/output_path refer to the actual output
            input_path = epub_output
            output_path = epub_output
            # Avoid further accidental re-conversion
            ext = ".epub"
            try:
                meta_cmd = [METADATA_TOOL, epub_output, "--title", title]
                if author:
                    meta_cmd += ["--authors", author]
                subprocess.run(meta_cmd, check=True)
                logger.info(f"Set EPUB metadata for CBR: title='{title}' author='{author}'")
            except subprocess.CalledProcessError as e:
                pass
            # --- Установка ISBN для EPUB ---
            isbn = find_isbn_by_title_author(title, author)
            if isbn:
                logger.info(f"Found ISBN: {isbn}")
                try:
                    subprocess.run([METADATA_TOOL, epub_output, "--isbn", isbn], check=True)
                    logger.info(f"Set ISBN for EPUB: {isbn}")
                except subprocess.CalledProcessError as e:
                    pass
            # --- Установка ASIN для EPUB ---
            asin = find_asin_by_title_author(title, author)
            if asin:
                logger.info(f"Found ASIN: {asin}")
                try:
                    subprocess.run([METADATA_TOOL, epub_output, "--identifier", f"BookId:amazon:{asin}"], check=True)
                    logger.info(f"ASIN metadata set using scheme 'BookId:amazon': {asin}")
                except subprocess.CalledProcessError as e:
                    pass
            # Отправка EPUB с полной метаинформацией в Telegram (после ISBN и ASIN)
            # await update.message.reply_document(document=open(output_path, "rb"), filename=Path(output_path).name, caption="📎 EPUB with full metadata")
        except subprocess.CalledProcessError as e:
            pass
            await update.message.reply_text("❌ Failed to convert CBR archive.")
            return
    # input_path = raw_input_path
    # output_path = input_path

    # Ensure input_path is defined for conversion block below
    input_path = raw_input_path

    if ext not in SUPPORTED_KINDLE_EXTENSIONS or Path(output_path).suffix.lower() != ".epub":
        output_path = str(Path(input_path).with_suffix(".epub"))
        await update.message.reply_text(f"⚙️ Converting {ext} to EPUB...")

        try:
            cmd = [CONVERT_PATH, input_path, output_path]
            if ext == ".pdf" and os.path.exists(DEFAULT_COVER):
                cmd += ["--cover", DEFAULT_COVER]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            pass
            await update.message.reply_text("❌ Conversion failed.")
            return

        meta = extract_metadata(output_path)
        title = meta.get("title", "").strip()
        author = meta.get("author(s)", meta.get("authors", "")).strip()

        if title or author:
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
            safe_author = "".join(c for c in author if c.isalnum() or c in " _-").strip()
            final_name = f"{safe_author} - {safe_title}".strip(" -") + ".epub"
        else:
            final_name = Path(file_name).stem + ".epub"

        final_output_path = f"/tmp/{final_name}"
        os.rename(output_path, final_output_path)
        output_path = final_output_path
        # --- Установка ISBN для EPUB ---
        isbn = find_isbn_by_title_author(title, author)
        if isbn:
            logger.info(f"Found ISBN: {isbn}")
            try:
                subprocess.run([METADATA_TOOL, output_path, "--isbn", isbn], check=True)
                logger.info(f"Set ISBN for EPUB: {isbn}")
            except subprocess.CalledProcessError as e:
                pass
        # --- Установка ASIN для EPUB ---
        asin = find_asin_by_title_author(title, author)
        if asin:
            logger.info(f"Found ASIN: {asin}")
            try:
                subprocess.run([METADATA_TOOL, output_path, "--identifier", f"BookId:amazon:{asin}"], check=True)
                logger.info(f"ASIN metadata set using scheme 'BookId:amazon': {asin}")
            except subprocess.CalledProcessError as e:
                pass
        # Отправка EPUB с полной метаинформацией в Telegram (после ISBN и ASIN)
        # await update.message.reply_document(document=open(output_path, "rb"), filename=Path(output_path).name, caption="📎 EPUB with full metadata")
    else:
        if not doc.file_name:
            final_name = f"{doc.file_unique_id}{ext}"
            final_output_path = f"/tmp/{final_name}"
            os.rename(input_path, final_output_path)
            output_path = final_output_path
        elif ext == ".pdf":
            author, title = guess_author_title_from_filename(file_name)
            if title:
                try:
                    cmd = [METADATA_TOOL, input_path, "--title", title]
                    if author:
                        cmd += ["--authors", author]
                    subprocess.run(cmd, check=True)
                    logger.info(f"Updated PDF metadata: title='{title}' author='{author}'")
                except subprocess.CalledProcessError as e:
                    pass

            if author or title:
                safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()
                safe_author = "".join(c for c in author if c.isalnum() or c in " _-").strip()
                new_name = f"{safe_author} - {safe_title}".strip(" -") + ".pdf"
                new_path = f"/tmp/{new_name}"
                os.rename(input_path, new_path)
                input_path = new_path
                output_path = new_path

    await update.message.reply_text("📤 Sending to Kindle...")

    msg = EmailMessage()
    msg["Subject"] = ""
    msg["From"] = SMTP_LOGIN
    msg["To"] = kindle_email
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
        logger.info(f"Sent to {kindle_email}: {output_path}")
    except Exception as e:
        pass
        await update.message.reply_text(f"❌ Failed to send email: {e}")
        return
    try:
        await update.message.reply_text("✅ Done. Check your Kindle.")
    except Exception as e:
        pass

# --- Запуск приложения ---
def main():
    if not TELEGRAM_TOKEN:
        pass
        return

    init_db()

    request = HTTPXRequest()
    app = Application.builder().token(TELEGRAM_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("setemail", cmd_setemail))
    app.add_handler(CommandHandler("getemail", cmd_getemail))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        pass

    app.add_error_handler(error_handler)

    logger.info("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()