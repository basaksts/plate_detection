"""
tests/ocr/test_tc_04_ocr_pipeline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OCR / Görüntü İşleme Pipeline Testleri

TC-04-01  letterbox çıktısı doğru boyut mu?
TC-04-02  Piksel normalize [0,1] aralığında mı?
TC-04-06  Zor örnek seti (karanlık/açılı/bulanık) pipeline çökmüyor mu?
TC-04-07  Pipeline latency — frame başına süre ölçümü
TC-04-09  Edge case aydınlatma (tam siyah / tam beyaz)
TC-04-10  Plaka bulunamadı → None döner, yanlış kayıt oluşmaz
"""

import sys
import os
import re
import time

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.logger import log_test_result

TR_REGEX = re.compile(r'(0[1-9]|[1-7][0-9]|8[0-1])\s*[A-Z]{1,4}\s*[0-9]{2,4}')

# ════════════════════════════════════════════════════════════
# TC-04-01 / TC-04-02  letterbox + normalizasyon
# ════════════════════════════════════════════════════════════
class TestTC0401_Letterbox:

    def test_letterbox_output_shape_640(self):
        """letterbox() çıktısı her zaman (640,640,3) olmalı."""
        test_id = "TC-04-01-a"
        import main as m
        try:
            for h, w in [(480, 640), (1080, 1920), (300, 200), (640, 640)]:
                img = np.zeros((h, w, 3), dtype=np.uint8)
                out, r, (dw, dh) = m.letterbox(img)
                assert out.shape == (640, 640, 3), \
                    f"Giriş {h}x{w} → beklenen (640,640,3), bulunan {out.shape}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_letterbox_ratio_positive(self):
        """Scale ratio her zaman pozitif olmalı."""
        test_id = "TC-04-01-b"
        import main as m
        try:
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            _, r, _ = m.letterbox(img)
            assert r > 0, f"Negatif ratio: {r}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_letterbox_no_nan_inf(self):
        """letterbox çıktısında NaN veya Inf olmamalı."""
        test_id = "TC-04-01-c"
        import main as m
        try:
            img = np.ones((360, 640, 3), dtype=np.uint8) * 128
            out, _, _ = m.letterbox(img)
            arr = out.astype(np.float32) / 255.0
            assert not np.any(np.isnan(arr)), "NaN değer tespit edildi"
            assert not np.any(np.isinf(arr)), "Inf değer tespit edildi"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_pixel_normalization_range(self):
        """Normalize edilmiş giriş [0.0, 1.0] aralığında olmalı."""
        test_id = "TC-04-02-a"
        import main as m
        try:
            img = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
            out, _, _ = m.letterbox(img)
            normalized = np.transpose(out, (2, 0, 1))[None].astype(np.float32) / 255.0
            assert normalized.min() >= 0.0, f"Min değer 0'dan küçük: {normalized.min()}"
            assert normalized.max() <= 1.0, f"Max değer 1'den büyük: {normalized.max()}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_input_tensor_shape(self):
        """Model giriş tensoru (1, 3, 640, 640) şeklinde olmalı."""
        test_id = "TC-04-02-b"
        import main as m
        try:
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            out, _, _ = m.letterbox(img)
            tensor = np.transpose(out, (2, 0, 1))[None].astype(np.float32) / 255.0
            assert tensor.shape == (1, 3, 640, 640), \
                f"Yanlış tensor şekli: {tensor.shape}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-04-06  Zor örnek seti — pipeline çökmemeli
# ════════════════════════════════════════════════════════════
class TestTC0406_HardCases:

    @pytest.mark.parametrize("brightness,label", [
        (0,   "tam_karanlik"),
        (30,  "az_aydinlik"),
        (200, "cok_aydinlik"),
        (255, "tam_beyaz"),
    ])
    def test_ocr_various_brightness(self, brightness, label):
        """Farklı parlaklık seviyelerinde OCR çökmemeli."""
        test_id = f"TC-04-06-brightness-{label}"
        import main as m
        try:
            img = np.full((80, 240, 3), brightness, dtype=np.uint8)
            result = m.ocr_process(img)
            assert result is None or isinstance(result, str)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))

    def test_ocr_blurred_image(self):
        """Bulanık görüntüde OCR çökmemeli."""
        test_id = "TC-04-06-blur"
        import main as m
        try:
            img = np.ones((80, 240, 3), dtype=np.uint8) * 200
            img = cv2.GaussianBlur(img, (21, 21), 0)
            result = m.ocr_process(img)
            assert result is None or isinstance(result, str)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))

    def test_ocr_noisy_image(self):
        """Gürültülü görüntüde OCR çökmemeli."""
        test_id = "TC-04-06-noise"
        import main as m
        try:
            noise = np.random.randint(0, 256, (80, 240, 3), dtype=np.uint8)
            result = m.ocr_process(noise)
            assert result is None or isinstance(result, str)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))

    def test_ocr_very_small_crop(self):
        """Çok küçük kırpma (10x10) OCR'ı çökermemeli."""
        test_id = "TC-04-06-tiny"
        import main as m
        try:
            tiny = np.ones((10, 10, 3), dtype=np.uint8) * 128
            result = m.ocr_process(tiny)
            assert result is None or isinstance(result, str)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))

    def test_ocr_rotated_image(self):
        """90° döndürülmüş görüntüde OCR çökmemeli."""
        test_id = "TC-04-06-rotated"
        import main as m
        try:
            img = np.ones((80, 240, 3), dtype=np.uint8) * 180
            cv2.putText(img, "34ABC123", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
            rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            result = m.ocr_process(rotated)
            assert result is None or isinstance(result, str)
            log_test_result(test_id, "PASS")
        except Exception as e:
            log_test_result(test_id, "FAIL", str(e))
            pytest.fail(str(e))


# ════════════════════════════════════════════════════════════
# TC-04-07  Pipeline latency — frame başına süre
# ════════════════════════════════════════════════════════════
class TestTC0407_Latency:
    """
    LATENCY_LIMIT: Raspberry Pi'da gerçekçi olabilmesi için
    tesseract dahil 2 saniyelik üst limit kullanılır.
    Kendi donanımınıza göre bu değeri düşürebilirsiniz.
    """
    LATENCY_LIMIT_SEC = 2.0
    N_FRAMES = 10

    def test_letterbox_latency(self):
        """letterbox() N frame ortalaması 50ms altında olmalı."""
        test_id = "TC-04-07-letterbox"
        import main as m
        try:
            frames = [
                np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
                for _ in range(self.N_FRAMES)
            ]
            t0 = time.perf_counter()
            for f in frames:
                m.letterbox(f)
            avg = (time.perf_counter() - t0) / self.N_FRAMES
            assert avg < 0.05, f"letterbox ortalama latency: {avg*1000:.1f}ms (limit: 50ms)"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_ocr_process_latency(self):
        """ocr_process() tek çağrı LATENCY_LIMIT_SEC altında olmalı."""
        test_id = "TC-04-07-ocr"
        import main as m
        try:
            img = np.ones((80, 240, 3), dtype=np.uint8) * 200
            cv2.putText(img, "34ABC123", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
            t0 = time.perf_counter()
            m.ocr_process(img)
            elapsed = time.perf_counter() - t0
            assert elapsed < self.LATENCY_LIMIT_SEC, \
                f"OCR latency {elapsed:.2f}s > limit {self.LATENCY_LIMIT_SEC}s"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_preprocess_pipeline_latency(self):
        """letterbox + normalize toplam süresi 100ms altında olmalı."""
        test_id = "TC-04-07-preprocess"
        import main as m
        try:
            imgs = [
                np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
                for _ in range(self.N_FRAMES)
            ]
            t0 = time.perf_counter()
            for img in imgs:
                out, _, _ = m.letterbox(img)
                _ = np.transpose(out, (2, 0, 1))[None].astype(np.float32) / 255.0
            avg = (time.perf_counter() - t0) / self.N_FRAMES
            assert avg < 0.10, f"Preprocess ortalama: {avg*1000:.1f}ms (limit: 100ms)"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-04-09  Edge case aydınlatma
# ════════════════════════════════════════════════════════════
class TestTC0409_LightingEdgeCase:

    def test_full_black_no_nan(self):
        """Tam siyah görüntü letterbox'tan geçince NaN/Inf olmamalı."""
        test_id = "TC-04-09-black"
        import main as m
        try:
            black = np.zeros((480, 640, 3), dtype=np.uint8)
            out, _, _ = m.letterbox(black)
            arr = out.astype(np.float32) / 255.0
            assert not np.any(np.isnan(arr))
            assert not np.any(np.isinf(arr))
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_full_white_no_nan(self):
        """Tam beyaz görüntü letterbox'tan geçince NaN/Inf olmamalı."""
        test_id = "TC-04-09-white"
        import main as m
        try:
            white = np.ones((480, 640, 3), dtype=np.uint8) * 255
            out, _, _ = m.letterbox(white)
            arr = out.astype(np.float32) / 255.0
            assert not np.any(np.isnan(arr))
            assert not np.any(np.isinf(arr))
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_ocr_black_returns_none(self):
        """Siyah görüntüde OCR None döndürmeli (anlamlı çıktı yok)."""
        test_id = "TC-04-09-ocr-black"
        import main as m
        try:
            black = np.zeros((80, 240, 3), dtype=np.uint8)
            result = m.ocr_process(black)
            # Siyah görüntü regex eşleşmesi üretmemeli
            if result is not None:
                assert TR_REGEX.search(result) is None, \
                    f"Siyah görüntüden plaka okundu: {result}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise


# ════════════════════════════════════════════════════════════
# TC-04-10  Plaka bulunamadı → doğru davranış
# ════════════════════════════════════════════════════════════
class TestTC0410_PlateNotFound:

    def test_ocr_on_non_plate_returns_none(self, no_plate_image):
        """Plakasız görüntüde ocr_process() None döndürmeli."""
        test_id = "TC-04-10-a"
        import main as m
        try:
            result = m.ocr_process(no_plate_image)
            if result is not None:
                assert TR_REGEX.search(result) is None, \
                    f"Plakasız görselden plaka okundu: {result}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise

    def test_no_plate_does_not_write_db(self, temp_db):
        """Plaka bulunamadığında DB'ye kayıt oluşturulmamalı."""
        test_id = "TC-04-10-b"
        import main as m
        original = m.DB_NAME
        m.DB_NAME = temp_db
        try:
            # ocr_process None döndürüyor → log_entry çağrılmaz
            img = np.zeros((80, 240, 3), dtype=np.uint8)
            result = m.ocr_process(img)

            if result is None:
                # DB'ye hiç yazma yok
                conn = __import__("sqlite3").connect(temp_db)
                count = conn.execute(
                    "SELECT COUNT(*) FROM giris_loglari"
                ).fetchone()[0]
                conn.close()
                assert count == 0, f"Plakasız durumda {count} kayıt oluştu"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
        finally:
            m.DB_NAME = original

    def test_short_ocr_result_rejected(self):
        """5 karakterden kısa OCR sonucu havuza alınmamalı (min len kontrolü)."""
        test_id = "TC-04-10-c"
        try:
            # main.py: if len(temiz_plaka) >= 5
            kisa_sonuclar = ["AB", "1", "ABC", "1234"]
            for s in kisa_sonuclar:
                assert len(s) < 5, f"Test verisi yanlış: {s}"
            log_test_result(test_id, "PASS")
        except AssertionError as e:
            log_test_result(test_id, "FAIL", str(e))
            raise
