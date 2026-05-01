"""
conftest.py — Tüm testler için ortak fixture'lar
Plaka Tanıma Sistemi — YOLOv8 + Flask + SQLite
"""

import pytest
import sqlite3
import sys
import os
import numpy as np
import cv2
import json
import tempfile

# Ana uygulama dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────
# VERİTABANI FIXTURE'LARI
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    """Her test için temiz, izole SQLite DB döndürür."""
    db_path = str(tmp_path / "test_otopark.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS araclar (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT UNIQUE NOT NULL,
            sahip TEXT,
            durum TEXT DEFAULT 'AKTIF'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS giris_loglari (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT NOT NULL,
            sahip TEXT,
            tarih TEXT,
            durum TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def db_with_data(temp_db):
    """Örnek araç ve log verisi içeren DB döndürür."""
    conn = sqlite3.connect(temp_db)
    c = conn.cursor()
    c.executemany(
        "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
        [
            ("34ABC123", "Ahmet Yılmaz"),
            ("06XY4567", "Fatma Kara"),
            ("35DEF890", "Mehmet Demir"),
        ],
    )
    c.executemany(
        "INSERT INTO giris_loglari (plaka, sahip, tarih, durum) VALUES (?, ?, ?, ?)",
        [
            ("34ABC123", "Ahmet Yılmaz", "2024-01-01 08:00:00", "ONAYLANDI"),
            ("99ZZZ999", "Bilinmiyor",  "2024-01-01 08:05:00", "REDDEDİLDİ"),
            ("34ABC123", "Ahmet Yılmaz", "2024-01-01 09:00:00", "ONAYLANDI"),
        ],
    )
    conn.commit()
    conn.close()
    return temp_db


# ─────────────────────────────────────────────────────────────
# FLASK UYGULAMA FIXTURE'LARI
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def flask_app(temp_db):
    """
    Test modunda Flask uygulaması döndürür.
    main.py'deki DB_NAME'i geçici DB ile değiştirir.
    """
    import main as app_module
    original_db = app_module.DB_NAME
    app_module.DB_NAME = temp_db
    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        yield client

    app_module.DB_NAME = original_db


@pytest.fixture
def flask_app_with_data(db_with_data):
    """Örnek veri içeren DB ile Flask test client döndürür."""
    import main as app_module
    original_db = app_module.DB_NAME
    app_module.DB_NAME = db_with_data
    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        yield client

    app_module.DB_NAME = original_db


# ─────────────────────────────────────────────────────────────
# GÖRÜNTÜ FIXTURE'LARI
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def blank_frame():
    """640x480 siyah kare (kamera simülasyonu)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def white_frame():
    """640x480 tamamen beyaz kare (edge-case)."""
    return np.ones((480, 640, 3), dtype=np.uint8) * 255


@pytest.fixture
def sample_plate_crop():
    """
    Gerçek plaka görseli varsa döndürür, yoksa
    beyaz zemin üzerine siyah yazılı sahte crop döndürür.
    """
    real_path = os.path.join(
        os.path.dirname(__file__), "..", "testdata", "images", "plate2.jpeg"
    )
    if os.path.exists(real_path):
        img = cv2.imread(real_path)
        if img is not None:
            return img
    # Fallback: 200x60 beyaz görüntü
    img = np.ones((60, 200, 3), dtype=np.uint8) * 255
    cv2.putText(img, "34ABC123", (10, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
    return img


@pytest.fixture
def no_plate_image():
    """Plaka içermeyen örnek görüntü."""
    real_path = os.path.join(
        os.path.dirname(__file__), "..", "testdata", "images", "no_plate001.jpeg"
    )
    if os.path.exists(real_path):
        img = cv2.imread(real_path)
        if img is not None:
            return img
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def corrupt_image_bytes():
    """Bozuk JPEG byte dizisi — pipeline dayanıklılık testi için."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"CORRUPTED"
