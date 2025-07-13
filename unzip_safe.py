import os
import zipfile
from pathlib import Path

def unzip_safe(zip_path: str, extract_dir: str, max_uncompressed_size: int = 500 * 1024 * 1024):
    """
    Безопасно извлекает zip-архив в папку, предотвращая zip-бомбы и path traversal.
    :param zip_path: путь к zip-файлу
    :param extract_dir: путь для извлечения
    :param max_uncompressed_size: максимум общего размера извлечённых файлов (по умолчанию 500 MiB)
    """
    total_uncompressed_size = 0
    extract_dir = Path(extract_dir).resolve()

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            # Проверка на path traversal
            member_path = Path(extract_dir, member.filename).resolve()
            if not str(member_path).startswith(str(extract_dir)):
                raise Exception(f"Blocked path traversal in zip: {member.filename}")

            # Проверка на размер
            total_uncompressed_size += member.file_size
            if total_uncompressed_size > max_uncompressed_size:
                raise Exception("Aborted unzip: too much data (possible zip bomb)")

        zip_ref.extractall(path=extract_dir)