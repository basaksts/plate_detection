
# Bu dosya test altyapısını doğrulamak için eklenmiştir.
# Resmi test dokümanındaki bir TC maddesini doğrudan karşılamaz.
# Ama aşağıdaki testlerin güvenilir şekilde koşabilmesi için altyapı kontrolü yapar:
# - Geçici SQLite test veritabanı oluşturma
# - Sentetik plaka görüntüsü üretme
# - Test sonuçlarını results.json dosyasına yazma


import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np

from tests.utils.logger import log_test_result


def test_tc_00_01_temp_db_created(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    conn.close()

    assert "araclar" in tables
    assert "giris_loglari" in tables

    log_test_result(
        "TC-00-01",
        "PASS",
        "Geçici SQLite veritabanı ve tablolar başarıyla oluşturuldu.",
    )


def test_tc_00_02_synthetic_plate_fixture(sample_plate_crop):
    assert isinstance(sample_plate_crop, np.ndarray)
    assert sample_plate_crop.size > 0

    success, encoded = cv2.imencode(".jpg", sample_plate_crop)

    assert success is True
    assert len(encoded.tobytes()) > 100

    log_test_result(
        "TC-00-02",
        "PASS",
        "Sentetik plaka görüntüsü başarıyla üretildi ve JPEG'e çevrildi.",
    )


def test_tc_00_03_logger_writes_json():
    record = log_test_result(
        "TC-00-03",
        "PASS",
        "Logger JSON dosyasına test sonucu yazabiliyor.",
        metrics={"example_accuracy": 1.0},
    )

    assert record["test_id"] == "TC-00-03"
    assert record["status"] == "PASS"

    results_file = Path("tests/test_results/results.json")
    assert results_file.exists()

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert any(item["test_id"] == "TC-00-03" for item in data)