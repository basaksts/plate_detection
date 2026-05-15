"""
conftest.py
Tüm testler için ortak fixture'lar.
Gerçek görüntü ve gerçek veritabanı olmadan test altyapısını çalıştırmak için hazırlanmıştır.
"""

import os
import sys
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_db(tmp_path):
    """
    Her test için temiz, izole SQLite DB döndürür.
    Gerçek otopark.db dosyasını kirletmez.
    """
    db_path = tmp_path / "test_otopark.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS araclar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT UNIQUE NOT NULL,
            sahip TEXT,
            durum TEXT DEFAULT 'AKTIF'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS giris_loglari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT NOT NULL,
            sahip TEXT,
            tarih TEXT,
            durum TEXT
        )
    """)

    conn.commit()
    conn.close()

    return str(db_path)


@pytest.fixture
def db_with_data(temp_db):
    """
    Örnek araç ve log verisi içeren test DB döndürür.
    """
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.executemany(
        "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
        [
            ("34ABC123", "Ahmet Yılmaz"),
            ("06XY4567", "Fatma Kara"),
            ("35DEF890", "Mehmet Demir"),
        ],
    )

    cursor.executemany(
        "INSERT INTO giris_loglari (plaka, sahip, tarih, durum) VALUES (?, ?, ?, ?)",
        [
            ("34ABC123", "Ahmet Yılmaz", "2026-01-01 08:00:00", "ONAYLANDI"),
            ("99ZZZ999", "Bilinmiyor", "2026-01-01 08:05:00", "REDDEDILDI"),
            ("34ABC123", "Ahmet Yılmaz", "2026-01-01 09:00:00", "ONAYLANDI"),
        ],
    )

    conn.commit()
    conn.close()

    return temp_db


@pytest.fixture
def blank_frame():
    """
    640x480 siyah görüntü.
    Plaka bulunamadı / boş frame testleri için.
    """
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def white_frame():
    """
    640x480 beyaz görüntü.
    Threshold/preprocess edge-case testleri için.
    """
    return np.ones((480, 640, 3), dtype=np.uint8) * 255


@pytest.fixture
def sample_plate_crop():
    """
    Gerçek plaka görüntüsü yoksa sentetik plaka crop'u üretir.
    Bu, gerçek istatistik yerine test altyapısı doğrulama amaçlıdır.
    """
    img = np.ones((90, 300, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (8, 8), (292, 82), (0, 0, 0), 2)
    cv2.putText(
        img,
        "34ABC123",
        (25, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.25,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return img


@pytest.fixture
def no_plate_image():
    """
    Plaka içermeyen sahte görüntü.
    """
    img = np.ones((480, 640, 3), dtype=np.uint8) * 230
    cv2.circle(img, (320, 240), 80, (120, 120, 120), -1)
    return img


@pytest.fixture
def corrupt_image_bytes():
    """
    Bozuk JPEG byte dizisi.
    """
    return b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"CORRUPTED"