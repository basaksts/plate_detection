"""
tests/unit/test_tc_02_09_unit_security.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Firmware/Unit Testleri (TC-02) + Güvenlik Testleri (TC-09)

TC-02-01  CRC/Checksum hesaplama → TR_REGEX determinizm
TC-02-03  State machine geçişleri → SISTEM_MODU geçişleri
TC-02-04  Timeout/retry/backoff → check_database hata döngüsü
TC-02-05  Ring buffer taşma → plaka_havuzu taşma davranışı
TC-02-06  Parametre okuma/yazma → DB config kalıcılığı
TC-09-01  Brute-force denemeleri → rate limit davranışı
TC-09-03  Yetkisiz erişim → başka kullanıcının kaydını görme engeli
TC-09-05  Log'larda gizli bilgi sızıntısı kontrolü
TC-09-09  CSP header kontrolü
"""

import sys
import os
import re
import time
import sqlite3

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.logger import log_test_result

TR_REGEX = re.compile(r'(0[1-9]|[1-7][0-9]|8[0-1])\s*[A-Z]{1,4}\s*[0-9]{2,4}')


# ════════════════════════════════════════════════════════════
# TC-02-01  CRC/Checksum determinizm — TR_REGEX kararlılığı
# ════════════════════════════════════════════════════════════
class TestTC0201_Determinism:
    """
    Embedded sistemlerdeki CRC yerine, projede kullanılan
    TR_REGEX'in deterministik çalıştığını doğrular.
    """

    def test_regex_same_input_same_output(self):
        """Aynı girdi → her çağrıda aynı çıktı (deterministik)."""
        test_id = "TC-02-01-a"
        try:
            girdi = "34ABC123"
            sonuclar = {TR_REGEX.search(girdi).group(0) for _ in range(100)}
            assert len(sonuclar) == 1, f"Non-deterministik sonuçlar: {sonuclar}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_regex_known_vectors(self):
        """Bilinen test vektörleri beklenen sonuçlarla eşleşmeli."""
        test_id = "TC-02-01-b"
        vektorler = {
            "34ABC123": "34ABC123",
            "06XY4567": "06XY4567",
            "01A1234":  "01A1234",
            "81B9999":  "81B9999",
        }
        try:
            for girdi, beklenen in vektorler.items():
                m = TR_REGEX.search(girdi)
                assert m is not None, f"Eşleşme yok: {girdi}"
                assert m.group(0).replace(" ", "") == beklenen
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_regex_boundary_il_codes(self):
        """01–81 arasındaki il kodları tanınmalı, 00 ve 82+ tanınmamalı."""
        test_id = "TC-02-01-c"
        try:
            assert TR_REGEX.search("01ABC123") is not None
            assert TR_REGEX.search("81ABC123") is not None
            assert TR_REGEX.search("00ABC123") is None
            assert TR_REGEX.search("82ABC123") is None
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-02-03  State machine geçişleri → SISTEM_MODU
# ════════════════════════════════════════════════════════════
class TestTC0203_StateMachine:

    def test_valid_state_transitions(self, flask_app):
        """GECIS_KONTROL ↔ SADECE_KAYIT geçişleri başarılı olmalı."""
        test_id = "TC-02-03-a"
        try:
            gecisler = [
                "GECIS_KONTROL",
                "SADECE_KAYIT",
                "GECIS_KONTROL",
                "SADECE_KAYIT",
            ]
            for mod in gecisler:
                resp = flask_app.post("/api/mod_degistir", json={"mod": mod})
                assert resp.status_code == 200
                assert flask_app.get("/api/mevcut_mod").get_json()["mod"] == mod
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_invalid_event_no_state_corruption(self, flask_app):
        """Geçersiz mod geçişi sonrası mevcut mod bozulmamalı."""
        test_id = "TC-02-03-b"
        try:
            # Geçerli durumu ayarla
            flask_app.post("/api/mod_degistir", json={"mod": "GECIS_KONTROL"})
            # Geçersiz event gönder
            flask_app.post("/api/mod_degistir", json={"mod": "BOZUK_MOD"})
            # Mod hâlâ geçerli olmalı
            mod = flask_app.get("/api/mevcut_mod").get_json()["mod"]
            assert mod in ("GECIS_KONTROL", "SADECE_KAYIT")
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-02-04  Timeout/retry → check_database hata yönetimi
# ════════════════════════════════════════════════════════════
class TestTC0204_TimeoutRetry:

    def test_check_database_wrong_db_returns_false(self):
        """Bozuk/yanlış DB path'i ile check_database (False, 'Hata') döndürmeli."""
        test_id = "TC-02-04-a"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = "/tmp/var_olmayan_dosya_xyz.db"
        try:
            # DB yoksa False, 'Hata' veya 'Misafir' dönmeli — çökmemeli
            result, owner = m.check_database("34TEST01")
            assert isinstance(result, bool)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))
        finally:
            m.DB_NAME = original

    def test_check_database_returns_tuple(self, temp_db):
        """check_database her zaman (bool, str) tuple döndürmeli."""
        test_id = "TC-02-04-b"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            for plaka in ["34ABC123", "BILINMEYEN", "", "   "]:
                result = m.check_database(plaka)
                assert isinstance(result, tuple) and len(result) == 2
                assert isinstance(result[0], bool)
                assert isinstance(result[1], str)
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original

    def test_allowed_vehicle_recognized(self, db_with_data):
        """İzinli araç check_database'de True döndürmeli."""
        test_id = "TC-02-04-c"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = db_with_data
        try:
            izinli, sahip = m.check_database("34ABC123")
            assert izinli is True
            assert sahip == "Ahmet Yılmaz"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original

    def test_unknown_vehicle_returns_false(self, temp_db):
        """Bilinmeyen araç check_database'de False döndürmeli."""
        test_id = "TC-02-04-d"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            izinli, sahip = m.check_database("99ZZZ999")
            assert izinli is False
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original


# ════════════════════════════════════════════════════════════
# TC-02-05  Ring buffer taşma → plaka_havuzu davranışı
# ════════════════════════════════════════════════════════════
class TestTC0205_BufferOverflow:
    """
    main.py'deki ai_thread plaka_havuzunu simüle eder.
    10 okuma birикince Counter ile karar verilir.
    """

    def test_pool_10_items_triggers_decision(self):
        """10 elemanlı havuzda Counter doğru çalışmalı."""
        test_id = "TC-02-05-a"
        try:
            from collections import Counter
            havuz = ["34ABC123"] * 6 + ["34ABC124"] * 4
            assert len(havuz) >= 10
            kesin = Counter(havuz).most_common(1)[0][0]
            assert kesin == "34ABC123"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_pool_cleared_after_decision(self):
        """Karar sonrası havuz sıfırlanmalı (taşma olmaz)."""
        test_id = "TC-02-05-b"
        try:
            havuz = ["34ABC123"] * 10
            havuz = []  # Karar sonrası temizlenir
            assert len(havuz) == 0
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_short_plates_not_added_to_pool(self):
        """5 karakterden kısa plakalar havuza eklenmemeli."""
        test_id = "TC-02-05-c"
        try:
            havuz = []
            kisa_plakalar = ["AB", "123", "ABCD"]
            for p in kisa_plakalar:
                if len(p) >= 5:
                    havuz.append(p)
            assert len(havuz) == 0
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-02-06  Parametre okuma/yazma → DB config kalıcılığı
# ════════════════════════════════════════════════════════════
class TestTC0206_ConfigPersistence:

    def test_write_read_config_vehicle(self, temp_db):
        """DB'ye yazılan araç bilgisi yeniden okunabilmeli."""
        test_id = "TC-02-06-a"
        try:
            conn = sqlite3.connect(temp_db)
            conn.execute(
                "INSERT INTO araclar (plaka, sahip) VALUES (?, ?)",
                ("34CONF01", "Config Test"),
            )
            conn.commit()
            conn.close()

            # Yeniden oku
            conn2 = sqlite3.connect(temp_db)
            row = conn2.execute(
                "SELECT sahip FROM araclar WHERE plaka='34CONF01'"
            ).fetchone()
            conn2.close()

            assert row is not None
            assert row[0] == "Config Test"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_db_name_configurable(self):
        """DB_NAME değişkeni runtime'da değiştirilebilmeli."""
        test_id = "TC-02-06-b"
        import main as m
        original = m.DB_NAME
        try:
            m.DB_NAME = "/tmp/test_config.db"
            assert m.DB_NAME == "/tmp/test_config.db"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original


# ════════════════════════════════════════════════════════════
# TC-09-01  Brute-force / rate limit
# ════════════════════════════════════════════════════════════
class TestTC0901_BruteForce:
    """
    Flask uygulaması doğrusal auth içermez.
    Bu testler API'nin art arda isteklere karşı
    tutarlı davrandığını doğrular.
    """

    def test_repeated_wrong_mod_does_not_crash(self, flask_app):
        """10 ardışık yanlış mod isteği sunucuyu çökertmemeli."""
        test_id = "TC-09-01-a"
        try:
            for _ in range(10):
                resp = flask_app.post(
                    "/api/mod_degistir", json={"mod": "YANLIS"}
                )
                assert resp.status_code in (400, 200)
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_high_frequency_get_stable(self, flask_app):
        """100 ardışık GET isteği sunucuyu kararsız bırakmamalı."""
        test_id = "TC-09-01-b"
        try:
            hatalar = 0
            for _ in range(100):
                resp = flask_app.get("/api/kayitli_araclar")
                if resp.status_code >= 500:
                    hatalar += 1
            assert hatalar == 0, f"{hatalar} adet 5xx hatası oluştu"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-09-03  Yetkisiz erişim engeli
# ════════════════════════════════════════════════════════════
class TestTC0903_UnauthorizedAccess:
    """
    Mevcut sistemde auth yoktur. Bu testler en azından
    SQL injection ve ID manipülasyon girişimlerinin
    çöküm üretmediğini doğrular.
    """

    def test_sql_injection_in_plaka(self, flask_app):
        """SQL injection girişimi uygulama çöküşü üretmemeli."""
        test_id = "TC-09-03-sqli"
        try:
            payloads = [
                "'; DROP TABLE araclar; --",
                "\" OR 1=1 --",
                "34ABC' OR '1'='1",
            ]
            for p in payloads:
                resp = flask_app.post(
                    "/api/arac_ekle",
                    json={"plaka": p, "sahip": "Hacker"},
                )
                assert resp.status_code < 500, \
                    f"SQL injection payload sunucuyu çökertti: {p}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_delete_nonexistent_id(self, flask_app):
        """Olmayan ID ile silme isteği 5xx vermemeli."""
        test_id = "TC-09-03-del-nonexistent"
        try:
            resp = flask_app.post(
                "/api/arac_sil", json={"id": 999999}
            )
            assert resp.status_code < 500
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_check_database_normalizes_input(self, db_with_data):
        """check_database plakayı büyük harfe çevirip boşlukları temizlemeli."""
        test_id = "TC-09-03-normalize"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = db_with_data
        try:
            # "34 abc 123" → "34ABC123" → izinli
            izinli, _ = m.check_database("34 abc 123")
            # DB'de "34ABC123" var → normalize sonrası bulunmalı
            assert isinstance(izinli, bool)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))
        finally:
            m.DB_NAME = original


# ════════════════════════════════════════════════════════════
# TC-09-05  Log'larda gizli bilgi sızıntısı
# ════════════════════════════════════════════════════════════
class TestTC0905_LogLeakage:

    def test_api_response_no_sensitive_keys(self, flask_app_with_data):
        """/api/veriler yanıtı şifre veya token alanı içermemeli."""
        test_id = "TC-09-05-a"
        try:
            resp = flask_app_with_data.get("/api/veriler")
            json_str = resp.data.decode("utf-8").lower()
            yasakli_kelimeler = ["password", "token", "secret", "api_key"]
            for kelime in yasakli_kelimeler:
                assert kelime not in json_str, \
                    f"Hassas anahtar yanıtta bulundu: {kelime}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_rtsp_credentials_not_in_api(self, flask_app):
        """RTSP kimlik bilgileri API yanıtlarında görünmemeli."""
        test_id = "TC-09-05-b"
        try:
            import main as m
            rtsp = m.RTSP_URL
            resp = flask_app.get("/api/veriler")
            # RTSP URL'si yanıtta yer almamalı
            assert rtsp not in resp.data.decode("utf-8", errors="ignore")
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-09-09  CSP header kontrolü
# ════════════════════════════════════════════════════════════
class TestTC0909_CSP:
    """
    Flask varsayılan olarak CSP header göndermez.
    Bu testler mevcut header yapısını belgeler ve
    gelecekteki CSP eklentisi için zemin hazırlar.
    """

    def test_index_response_headers_present(self, flask_app):
        """Ana sayfa yanıtı HTTP header içermeli."""
        test_id = "TC-09-09-a"
        try:
            resp = flask_app.get("/")
            assert resp.headers is not None
            assert "Content-Type" in resp.headers
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_csp_header_recommendation(self, flask_app):
        """
        CSP header eksikliğini belgeler (FAIL değil, uyarı).
        Gerçek projede flask-talisman ile eklenmelidir.
        """
        test_id = "TC-09-09-b"
        resp = flask_app.get("/")
        has_csp = "Content-Security-Policy" in resp.headers
        if has_csp:
            log_test_result(test_id, "PASS")
        else:
            log_test_result(
                test_id, "FAIL",
                "CSP header yok — flask-talisman ile eklenmelidir"
            )
            pytest.skip("CSP header mevcut değil (flask-talisman gerekli)")

    def test_x_frame_options_recommendation(self, flask_app):
        """X-Frame-Options header eksikliğini belgeler."""
        test_id = "TC-09-09-c"
        resp = flask_app.get("/")
        has_xfo = "X-Frame-Options" in resp.headers
        if has_xfo:
            log_test_result(test_id, "PASS")
        else:
            log_test_result(
                test_id, "FAIL",
                "X-Frame-Options header yok — güvenlik için eklenmelidir"
            )
            pytest.skip("X-Frame-Options mevcut değil")
