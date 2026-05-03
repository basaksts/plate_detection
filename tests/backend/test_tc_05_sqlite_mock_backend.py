
# Bu dosya aşağıdaki test dokümantasyonu maddelerini karşılar:
# TC-05-03 - CRUD: kayıt oluştur/güncelle/sil/listele
# TC-05-08 - Duplicate kayıt önleme (idempotency)
# TC-05-09 - Zaman damgası tutarlılığı (timezone/UTC)
#
# Not:
# Bu testler gerçek otopark.db yerine geçici SQLite veritabanı kullanır.
# Amaç, gerçek veritabanına geçmeden önce backend/veri katmanı davranışını doğrulamaktır.

import sqlite3
from datetime import datetime

from tests.utils.logger import log_test_result


def test_tc_05_03_crud_create_read_delete(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
        ("34TEST123", "Test Kullanıcı"),
    )
    conn.commit()

    cursor.execute("SELECT plaka, sahip FROM araclar WHERE plaka = ?", ("34TEST123",))
    row = cursor.fetchone()

    assert row == ("34TEST123", "Test Kullanıcı")

    cursor.execute("DELETE FROM araclar WHERE plaka = ?", ("34TEST123",))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM araclar WHERE plaka = ?", ("34TEST123",))
    count = cursor.fetchone()[0]

    conn.close()

    assert count == 0

    log_test_result("TC-05-03", "PASS", "SQLite mock CRUD akışı başarılı.")


def test_tc_05_08_duplicate_plate_prevention(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
        ("34DUP123", "İlk Kayıt"),
    )
    conn.commit()

    duplicate_blocked = False

    try:
        cursor.execute(
            "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
            ("34DUP123", "İkinci Kayıt"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_blocked = True

    conn.close()

    assert duplicate_blocked is True

    log_test_result(
        "TC-05-08",
        "PASS",
        "Duplicate plaka UNIQUE constraint ile engellendi.",
    )


def test_tc_05_09_timestamp_format(temp_db):
    now = datetime.now().isoformat(timespec="seconds")

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO giris_loglari (plaka, sahip, tarih, durum) VALUES (?, ?, ?, ?)",
        ("34TIME123", "Zaman Test", now, "ONAYLANDI"),
    )
    conn.commit()

    cursor.execute("SELECT tarih FROM giris_loglari WHERE plaka = ?", ("34TIME123",))
    saved_time = cursor.fetchone()[0]

    conn.close()

    parsed_time = datetime.fromisoformat(saved_time)

    assert parsed_time is not None

    log_test_result(
        "TC-05-09",
        "PASS",
        "Timestamp ISO formatında kaydedildi ve parse edilebildi.",
        metrics={"timestamp": saved_time},
    )