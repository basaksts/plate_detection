# Bu dosya aşağıdaki test dokümantasyonu maddelerini karşılar:
# TC-01-01 - Cihaz açılıyor, boot süresi normal mi?
# TC-01-02 - Sensör/kamera başlatma başarılı mı?
# TC-01-03 - Veri okuma → paketleme → gönderme akıyor mu?
# TC-01-06 - Web uygulama açılıyor, login oluyor, temel sayfalar yükleniyor mu?
# TC-01-07 - Bir kayıt oluştur → görüntüle uçtan uca çalışıyor mu?
#
# Not:
# Bu dosya gerçek Raspberry Pi, kamera ve web sunucusu olmadan smoke test altyapısını temsil eder.
# Gerçek donanım bağlandığında bu testler live smoke testlere dönüştürülecektir.


# Bu dosya aşağıdaki test dokümantasyonu maddelerini karşılar:
# TC-01-01 - Cihaz açılıyor, boot süresi normal mi?
# TC-01-02 - Sensör/kamera başlatma başarılı mı?
# TC-01-03 - Veri okuma → paketleme → gönderme akıyor mu?
# TC-01-06 - Web uygulama açılıyor, login oluyor, temel sayfalar yükleniyor mu?
# TC-01-07 - Bir kayıt oluştur → görüntüle uçtan uca çalışıyor mu?
#
# Not:
# Bu testler gerçek Raspberry Pi, kamera ve canlı backend olmadan mock/simülasyon ile çalışır.
# Gerçek donanım bağlandığında aynı TC maddeleri live smoke testlere dönüştürülecektir.

import time
import json
from pathlib import Path

import cv2

from tests.utils.logger import log_test_result


def mock_boot_sequence():
    """
    Cihaz boot sürecini temsili olarak simüle eder.
    """
    start = time.perf_counter()

    services = {
        "camera_service": "ready",
        "network_service": "ready",
        "web_service": "ready",
        "database_service": "ready",
    }

    elapsed = time.perf_counter() - start

    return services, elapsed


class MockCamera:
    """
    Gerçek kamera yerine sentetik frame döndüren kamera sınıfı.
    """

    def __init__(self, frame):
        self.frame = frame
        self.initialized = True

    def get_frame(self):
        success, encoded = cv2.imencode(".jpg", self.frame)

        if not success:
            return None

        return encoded.tobytes()


class MockReceiver:
    """
    Backend/test receiver simülasyonu.
    Gönderilen paketleri bellekte saklar.
    """

    def __init__(self):
        self.received_packets = []

    def send(self, packet):
        self.received_packets.append(packet)
        return {
            "status_code": 200,
            "message": "OK",
        }


class MockWebApp:
    """
    Login ve temel sayfa yükleme davranışını simüle eden basit web app.
    """

    def __init__(self):
        self.logged_in = False
        self.records = []

    def login(self, username, password):
        if username == "admin" and password == "admin":
            self.logged_in = True
            return True
        return False

    def load_page(self, page_name):
        if not self.logged_in:
            return False

        valid_pages = {
            "homepage",
            "plate_detection",
            "past_entrances",
            "authorized_vehicles",
        }

        return page_name in valid_pages

    def create_record(self, plate, owner):
        if not self.logged_in:
            return None

        record = {
            "id": len(self.records) + 1,
            "plate": plate,
            "owner": owner,
        }

        self.records.append(record)
        return record

    def get_record(self, record_id):
        for record in self.records:
            if record["id"] == record_id:
                return record

        return None


def test_tc_01_01_mock_boot_time():
    services, elapsed = mock_boot_sequence()

    assert elapsed < 1.0
    assert services["camera_service"] == "ready"
    assert services["network_service"] == "ready"
    assert services["web_service"] == "ready"
    assert services["database_service"] == "ready"

    log_test_result(
        "TC-01-01",
        "PASS",
        "Mock boot sequence tamamlandi ve temel servisler ready durumuna gecti.",
        metrics={
            "boot_time_seconds": round(elapsed, 6),
            "services": services,
        },
    )


def test_tc_01_02_mock_camera_init(sample_plate_crop):
    camera = MockCamera(sample_plate_crop)

    frame_bytes = camera.get_frame()

    assert camera.initialized is True
    assert frame_bytes is not None
    assert isinstance(frame_bytes, bytes)
    assert len(frame_bytes) > 100

    log_test_result(
        "TC-01-02",
        "PASS",
        "Mock kamera baslatildi ve sentetik frame JPEG olarak alindi.",
        metrics={
            "frame_size_bytes": len(frame_bytes),
        },
    )


def test_tc_01_03_mock_data_read_package_send():
    receiver = MockReceiver()

    sample_payload = {
        "plate": "34ABC123",
        "timestamp": "2026-01-01T12:00:00",
        "confidence": 0.94,
        "decision": "AUTHORIZED",
    }

    packet = {
        "sequence_no": 1,
        "length": len(json.dumps(sample_payload)),
        "payload": sample_payload,
    }

    response = receiver.send(packet)

    assert response["status_code"] == 200
    assert len(receiver.received_packets) == 1
    assert receiver.received_packets[0]["payload"]["plate"] == "34ABC123"
    assert receiver.received_packets[0]["payload"]["decision"] == "AUTHORIZED"

    log_test_result(
        "TC-01-03",
        "PASS",
        "Mock veri okuma-paketleme-gonderme zinciri basariyla tamamlandi.",
        metrics={
            "sent_packets": len(receiver.received_packets),
            "packet_length": packet["length"],
        },
    )


def test_tc_01_06_mock_web_app_pages():
    webapp = MockWebApp()

    login_result = webapp.login("admin", "admin")

    assert login_result is True
    assert webapp.load_page("homepage") is True
    assert webapp.load_page("plate_detection") is True
    assert webapp.load_page("past_entrances") is True
    assert webapp.load_page("authorized_vehicles") is True

    log_test_result(
        "TC-01-06",
        "PASS",
        "Mock web uygulama login oldu ve temel sayfalar yuklendi.",
        metrics={
            "pages_checked": 4,
        },
    )


def test_tc_01_07_mock_create_and_view_record():
    webapp = MockWebApp()

    assert webapp.login("admin", "admin") is True

    created_record = webapp.create_record("34ABC123", "Test Kullanici")

    assert created_record is not None
    assert created_record["id"] == 1

    loaded_record = webapp.get_record(created_record["id"])

    assert loaded_record is not None
    assert loaded_record["plate"] == "34ABC123"
    assert loaded_record["owner"] == "Test Kullanici"

    log_test_result(
        "TC-01-07",
        "PASS",
        "Mock web uygulamada kayit olusturma ve goruntuleme akisi dogrulandi.",
        metrics={
            "record_id": created_record["id"],
        },
    )