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




def _build_flask_test_client(db_path, monkeypatch):
    """
    main.py içindeki Flask app nesnesini test client olarak döndürür.
    Test DB path'ini main.DB_NAME üzerine yönlendirir.
    """
    import main as m

    # Projede DB değişkeni DB_NAME olarak kullanıldığı için test DB'ye yönlendiriyoruz.
    monkeypatch.setattr(m, "DB_NAME", db_path, raising=False)

    app = getattr(m, "app", None)

    if app is None:
        pytest.skip("main.py içinde Flask app nesnesi bulunamadı. Fixture atlandı.")

    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False
    )

    return app.test_client()




@pytest.fixture
def flask_app(temp_db, monkeypatch):
    import main as m

    monkeypatch.setattr(m, "DB_NAME", temp_db, raising=False)

    m.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False
    )

    return m.app.test_client()


@pytest.fixture
def flask_app_with_data(db_with_data, monkeypatch):
    import main as m

    monkeypatch.setattr(m, "DB_NAME", db_with_data, raising=False)

    m.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False
    )

    return m.app.test_client()

# --- Local OCR mock for environments without Tesseract executable ---

import shutil
import pytesseract


def _tesseract_available_for_local_tests():
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return True

    return shutil.which("tesseract") is not None


@pytest.fixture(autouse=True)
def mock_tesseract_when_missing(monkeypatch):
    """
    Local Windows test ortamında Tesseract executable yoksa,
    pytesseract.image_to_string fonksiyonunu mock'lar.

    Bu sadece local automated testler içindir.
    Gerçek OCR başarısı saha testi ve Raspberry/Tesseract ortamında ölçülür.
    """
    if _tesseract_available_for_local_tests():
        return

    def fake_image_to_string(*args, **kwargs):
        return ""

    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        fake_image_to_string,
        raising=False
    )
    
    
    # --- Force mock OCR in local test environment without real Tesseract ---

@pytest.fixture(autouse=True)
def force_mock_ocr_when_tesseract_missing(monkeypatch):
    """
    Local Windows test ortamında gerçek Tesseract executable olmadığı için
    main.py içindeki OCR çağrısını mock'lar.

    Bu testler OCR doğruluğunu değil, pipeline'ın çökmeden çalışmasını doğrular.
    Gerçek OCR başarısı saha/kontrollü görüntü testleriyle ölçülür.
    """
    import os
    import shutil
    import pytesseract

    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
    ]

    tesseract_exists = any(os.path.exists(p) for p in possible_paths) or shutil.which("tesseract") is not None

    if tesseract_exists:
        return

    def fake_image_to_string(*args, **kwargs):
        return ""

    # Pytesseract paketindeki iki olası çağrı noktasını da mock'la
    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string, raising=False)
    monkeypatch.setattr(pytesseract.pytesseract, "image_to_string", fake_image_to_string, raising=False)

    # main.py import edildiyse/edilecekse onun kullandığı modül referansını da mock'la
    try:
        import main as m
        monkeypatch.setattr(m.pytesseract, "image_to_string", fake_image_to_string, raising=False)
        monkeypatch.setattr(m.pytesseract.pytesseract, "image_to_string", fake_image_to_string, raising=False)
    except Exception:
        pass