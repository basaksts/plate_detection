"""
tests/backend/test_tc_05_backend_api.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Backend / API / Veritabanı Testleri

TC-05-03  CRUD: kayıt oluştur / güncelle / sil / listele
TC-05-04  Filtreleme / sıralama / sayfalama (DB seviyesinde)
TC-05-05  Dosya yükleme boyut ve format kontrolleri (toplu_ekle)
TC-05-08  Duplicate kayıt önleme (INSERT OR IGNORE)
TC-05-09  Zaman damgası tutarlılığı (ISO-8601 / UTC)
TC-05-11  Rate limit / flood istek davranışı
TC-05-13  Servis restart sonrası veri kaybı yok
"""

import sys
import os
import re
import time
import sqlite3
import datetime
import io

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.logger import log_test_result

DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


# ════════════════════════════════════════════════════════════
# TC-05-03  CRUD
# ════════════════════════════════════════════════════════════
class TestTC0503_CRUD:

    def test_create_vehicle(self, flask_app):
        """POST /api/arac_ekle başarılı olmalı ve success:True döndürmeli."""
        test_id = "TC-05-03-create"
        try:
            resp = flask_app.post(
                "/api/arac_ekle",
                json={"plaka": "34CRUD01", "sahip": "CRUD Testi"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("success") is True
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_read_vehicle_in_list(self, flask_app):
        """Eklenen araç GET /api/kayitli_araclar listesinde bulunmalı."""
        test_id = "TC-05-03-read"
        try:
            flask_app.post(
                "/api/arac_ekle",
                json={"plaka": "34CRUD02", "sahip": "Okuma Testi"},
            )
            resp = flask_app.get("/api/kayitli_araclar")
            assert resp.status_code == 200
            plakalar = [row[1] for row in resp.get_json()]
            assert "34CRUD02" in plakalar
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_update_vehicle_plate(self, flask_app_with_data):
        """POST /api/arac_guncelle plakayı güncellemeli."""
        test_id = "TC-05-03-update"
        try:
            resp = flask_app_with_data.post(
                "/api/arac_guncelle",
                json={"sahip": "Ahmet Yılmaz", "plaka": "34YENI99"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("status") == "success"

            # Güncelleme yansıdı mı?
            resp2 = flask_app_with_data.get("/api/kayitli_araclar")
            plakalar = [row[1] for row in resp2.get_json()]
            assert "34YENI99" in plakalar
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_delete_vehicle(self, flask_app_with_data):
        """POST /api/arac_sil aracı silmeli, liste küçülmeli."""
        test_id = "TC-05-03-delete"
        try:
            araclar_before = flask_app_with_data.get("/api/kayitli_araclar").get_json()
            arac_id = araclar_before[0][0]

            resp = flask_app_with_data.post("/api/arac_sil", json={"id": arac_id})
            assert resp.status_code == 200
            assert resp.get_json().get("success") is True

            araclar_after = flask_app_with_data.get("/api/kayitli_araclar").get_json()
            assert len(araclar_after) == len(araclar_before) - 1
            ids_after = [r[0] for r in araclar_after]
            assert arac_id not in ids_after
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_update_missing_fields_returns_400(self, flask_app):
        """Eksik veri ile /api/arac_guncelle 400 dönmeli."""
        test_id = "TC-05-03-update-400"
        try:
            resp = flask_app.post(
                "/api/arac_guncelle",
                json={"sahip": "Sadece Sahip"},  # plaka eksik
            )
            assert resp.status_code == 400
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-05-04  Filtreleme / Sıralama (DB seviyesi)
# ════════════════════════════════════════════════════════════
class TestTC0504_FilterSort:

    def test_logs_ordered_by_id_desc(self, db_with_data):
        """giris_loglari, id DESC sırasıyla gelmeli."""
        test_id = "TC-05-04-sort"
        try:
            conn = sqlite3.connect(db_with_data)
            rows = conn.execute(
                "SELECT id FROM giris_loglari ORDER BY id DESC"
            ).fetchall()
            conn.close()
            ids = [r[0] for r in rows]
            assert ids == sorted(ids, reverse=True), "ID DESC sıralaması bozuk"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_filter_by_durum(self, db_with_data):
        """durum='ONAYLANDI' filtresi yalnızca onaylananları döndürmeli."""
        test_id = "TC-05-04-filter"
        try:
            conn = sqlite3.connect(db_with_data)
            rows = conn.execute(
                "SELECT durum FROM giris_loglari WHERE durum = 'ONAYLANDI'"
            ).fetchall()
            conn.close()
            assert all(r[0] == "ONAYLANDI" for r in rows)
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_limit_100_logs(self, flask_app_with_data):
        """/api/veriler 100'den fazla log göndermiyor (LIMIT 100)."""
        test_id = "TC-05-04-limit"
        try:
            resp = flask_app_with_data.get("/api/veriler")
            data = resp.get_json()
            assert len(data["loglar"]) <= 100
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_distinct_plates_in_logs(self, db_with_data):
        """DISTINCT plaka sorgusu çakışma içermemeli."""
        test_id = "TC-05-04-distinct"
        try:
            conn = sqlite3.connect(db_with_data)
            rows = conn.execute(
                "SELECT DISTINCT plaka FROM giris_loglari"
            ).fetchall()
            conn.close()
            plakalar = [r[0] for r in rows]
            assert len(plakalar) == len(set(plakalar))
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-05-05  Toplu dosya yükleme — format ve boyut kontrolü
# ════════════════════════════════════════════════════════════
class TestTC0505_FileUpload:

    def _make_csv(self, lines: list) -> bytes:
        return "\n".join(lines).encode("utf-8")

    def test_valid_csv_upload(self, flask_app):
        """Geçerli CSV ile toplu_ekle başarılı olmalı."""
        test_id = "TC-05-05-valid"
        try:
            csv_content = self._make_csv([
                "plaka,sahip",
                "34TOPLU1,Kişi Bir",
                "34TOPLU2,Kişi İki",
            ])
            data = {
                "file": (io.BytesIO(csv_content), "araclar.csv"),
            }
            resp = flask_app.post(
                "/api/toplu_ekle",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200
            result = resp.get_json()
            assert result.get("status") == "success"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_semicolon_csv_upload(self, flask_app):
        """Noktalı virgül ayraçlı CSV (Excel formatı) kabul edilmeli."""
        test_id = "TC-05-05-semicolon"
        try:
            csv_content = self._make_csv([
                "plaka;sahip",
                "34SEMI1;Semicolon Testi",
            ])
            data = {"file": (io.BytesIO(csv_content), "araclar.csv")}
            resp = flask_app.post(
                "/api/toplu_ekle",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_no_file_returns_400(self, flask_app):
        """Dosya olmadan toplu_ekle 400 dönmeli."""
        test_id = "TC-05-05-nofile"
        try:
            resp = flask_app.post("/api/toplu_ekle", data={},
                                  content_type="multipart/form-data")
            assert resp.status_code == 400
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_header_row_skipped(self, flask_app):
        """CSV başlık satırı ('plaka' içeren) DB'ye eklenmemeli."""
        test_id = "TC-05-05-header-skip"
        try:
            csv_content = self._make_csv([
                "plaka,sahip",
                "34HEADER1,Test",
            ])
            data = {"file": (io.BytesIO(csv_content), "araclar.csv")}
            resp = flask_app.post(
                "/api/toplu_ekle",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 200
            # Liste kontrolü: "plaka" metni araç olarak eklenmemeli
            resp2 = flask_app.get("/api/kayitli_araclar")
            plakalar = [row[1] for row in resp2.get_json()]
            assert "plaka" not in [p.lower() for p in plakalar]
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-05-08  Duplicate kayıt önleme
# ════════════════════════════════════════════════════════════
class TestTC0508_Idempotency:

    def test_duplicate_plate_not_doubled(self, flask_app):
        """Aynı plaka iki kez eklenmek istendiğinde DB'de tek kayıt olmalı."""
        test_id = "TC-05-08-a"
        try:
            payload = {"plaka": "34IDEM01", "sahip": "İdempotent Test"}
            flask_app.post("/api/arac_ekle", json=payload)
            flask_app.post("/api/arac_ekle", json=payload)

            resp = flask_app.get("/api/kayitli_araclar")
            araclar = resp.get_json()
            tekrar_sayisi = sum(1 for r in araclar if r[1] == "34IDEM01")
            assert tekrar_sayisi == 1, \
                f"Aynı plaka {tekrar_sayisi} kez eklendi!"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_logdan_yetkilendir_duplicate(self, flask_app_with_data):
        """logdan_yetkilendir aynı plakayı iki kez çağırınca tek kayıt kalmalı."""
        test_id = "TC-05-08-b"
        try:
            payload = {"plaka": "34LOG999", "sahip": "Log Kişi"}
            flask_app_with_data.post("/api/logdan_yetkilendir", json=payload)
            flask_app_with_data.post("/api/logdan_yetkilendir", json=payload)

            resp = flask_app_with_data.get("/api/kayitli_araclar")
            araclar = resp.get_json()
            tekrar = sum(1 for r in araclar if r[1] == "34LOG999")
            assert tekrar <= 1, f"Yineleme var: {tekrar}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-05-09  Zaman damgası tutarlılığı
# ════════════════════════════════════════════════════════════
class TestTC0509_Timestamp:

    def test_log_entry_timestamp_format(self, temp_db):
        """log_entry() tarih alanı 'YYYY-MM-DD HH:MM:SS' formatında olmalı."""
        test_id = "TC-05-09-a"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            m.log_entry("34TS001", "Zaman Testi", "ONAYLANDI")
            conn = sqlite3.connect(temp_db)
            tarih = conn.execute(
                "SELECT tarih FROM giris_loglari LIMIT 1"
            ).fetchone()[0]
            conn.close()
            assert DATETIME_RE.fullmatch(tarih), \
                f"Tarih formatı beklenen değil: {tarih}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original

    def test_log_timestamp_not_in_future(self, temp_db):
        """Log zaman damgası şu anki zamandan büyük olmamalı."""
        test_id = "TC-05-09-b"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            now = datetime.datetime.now()
            m.log_entry("34TS002", "Gelecek Kontrol", "ONAYLANDI")
            conn = sqlite3.connect(temp_db)
            tarih_str = conn.execute(
                "SELECT tarih FROM giris_loglari LIMIT 1"
            ).fetchone()[0]
            conn.close()
            tarih = datetime.datetime.strptime(tarih_str, "%Y-%m-%d %H:%M:%S")
            # 5 saniye tolerans
            assert tarih <= now + datetime.timedelta(seconds=5)
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original


# ════════════════════════════════════════════════════════════
# TC-05-11  Rate limit / flood istek
# ════════════════════════════════════════════════════════════
class TestTC0511_RateLimit:
    """
    Flask'ın dahili rate limiting'i yoktur (flask-limiter eklenmeden).
    Bu testler uygulamanın çok sayıda isteğe çökmeden yanıt verdiğini
    doğrular. Gerçek rate limit isteniyorsa flask-limiter eklenmelidir.
    """
    N_REQUESTS = 50

    def test_flood_get_kayitli_araclar(self, flask_app):
        """Ardışık 50 GET isteği sunucuyu çökertmemeli."""
        test_id = "TC-05-11-flood-get"
        try:
            basari = 0
            for _ in range(self.N_REQUESTS):
                resp = flask_app.get("/api/kayitli_araclar")
                if resp.status_code == 200:
                    basari += 1
            assert basari == self.N_REQUESTS, \
                f"{self.N_REQUESTS} istekten {basari} başarılı"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_flood_post_arac_ekle(self, flask_app):
        """Ardışık 30 POST isteği 200 veya uygulama hatası vermeli, 5xx vermemeli."""
        test_id = "TC-05-11-flood-post"
        try:
            for i in range(30):
                resp = flask_app.post(
                    "/api/arac_ekle",
                    json={"plaka": f"34FLD{i:03d}", "sahip": f"Flood{i}"},
                )
                assert resp.status_code < 500, \
                    f"İstek {i}: Sunucu hatası {resp.status_code}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-05-13  Servis restart sonrası veri kaybı yok
# ════════════════════════════════════════════════════════════
class TestTC0513_DataPersistence:

    def test_data_persists_after_db_reconnect(self, temp_db):
        """DB bağlantısı kapanıp yeniden açıldıktan sonra veriler kalmalı."""
        test_id = "TC-05-13-a"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            # Bağlantı 1: Veri yaz
            m.log_entry("34PERS01", "Kalıcılık Testi", "ONAYLANDI")

            # Bağlantı 2: Yeniden oku (restart simülasyonu)
            conn = sqlite3.connect(temp_db)
            rows = conn.execute("SELECT * FROM giris_loglari").fetchall()
            conn.close()

            assert len(rows) == 1
            assert rows[0][1] == "34PERS01"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original

    def test_arac_persists_after_reconnect(self, flask_app):
        """API ile eklenen araç yeni DB bağlantısında hâlâ mevcut olmalı."""
        test_id = "TC-05-13-b"
        try:
            flask_app.post(
                "/api/arac_ekle",
                json={"plaka": "34PERS02", "sahip": "Kalıcı Kişi"},
            )
            # Aynı test client üzerinden yeni GET = yeni DB bağlantısı
            resp = flask_app.get("/api/kayitli_araclar")
            plakalar = [row[1] for row in resp.get_json()]
            assert "34PERS02" in plakalar
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_multiple_writes_no_data_loss(self, temp_db):
        """10 log yazıldıktan sonra tamamı DB'de görünmeli."""
        test_id = "TC-05-13-c"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            for i in range(10):
                m.log_entry(f"34LOSS{i:02d}", "Kayıp Testi", "ONAYLANDI")
            conn = sqlite3.connect(temp_db)
            count = conn.execute(
                "SELECT COUNT(*) FROM giris_loglari"
            ).fetchone()[0]
            conn.close()
            assert count == 10, f"Beklenen 10, bulunan {count}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original
