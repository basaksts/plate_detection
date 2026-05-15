# Bu dosya aşağıdaki test dokümantasyonu maddelerini karşılar:
# TC-02-01 - CRC/Checksum hesaplama doğruluğu
# TC-02-03 - State machine geçişleri (idle→capture→send→retry vb.)
# TC-02-04 - Timeout/retry/backoff algoritması
# TC-02-05 - Ring buffer / queue taşma durumları
# TC-02-06 - Parametre okuma/yazma (EEPROM/Flash config)
#
# Not:
# Bu testler gerçek ESP32 firmware kodu yerine temsili unit test mantığı kullanır.
# Amaç, gömülü sistem tarafındaki temel yazılım davranışlarını donanım olmadan test etmektir.

import json
from pathlib import Path

from tests.utils.logger import log_test_result


def calculate_checksum(payload: bytes) -> int:
    """
    Basit checksum: byte toplamının 256'ya göre modu.
    Gerçek firmware protokolü gelince burası gerçek CRC algoritmasıyla değiştirilebilir.
    """
    return sum(payload) % 256


class SimpleStateMachine:
    """
    Cihaz davranışını temsil eden basit state machine.
    idle -> capture -> send -> idle
    send hatasında retry -> send veya error
    """

    def __init__(self, max_retry=3):
        self.state = "idle"
        self.retry_count = 0
        self.max_retry = max_retry

    def handle(self, event):
        if self.state == "idle" and event == "capture_trigger":
            self.state = "capture"

        elif self.state == "capture" and event == "frame_ready":
            self.state = "send"

        elif self.state == "send" and event == "send_success":
            self.state = "idle"
            self.retry_count = 0

        elif self.state == "send" and event == "send_fail":
            self.retry_count += 1
            if self.retry_count <= self.max_retry:
                self.state = "retry"
            else:
                self.state = "error"

        elif self.state == "retry" and event == "retry_tick":
            self.state = "send"

        elif event == "reset":
            self.state = "idle"
            self.retry_count = 0

        return self.state


def retry_backoff_delay(attempt, base_delay_ms=100, max_delay_ms=2000):
    """
    Exponential backoff.
    1. deneme: 100 ms
    2. deneme: 200 ms
    3. deneme: 400 ms ...
    """
    delay = base_delay_ms * (2 ** max(0, attempt - 1))
    return min(delay, max_delay_ms)


class RingBuffer:
    """
    Sabit kapasiteli basit ring buffer.
    Taşma durumunda yeni veri reddedilir.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.items = []

    def push(self, item):
        if len(self.items) >= self.capacity:
            return False

        self.items.append(item)
        return True

    def pop(self):
        if not self.items:
            return None

        return self.items.pop(0)

    def size(self):
        return len(self.items)


def test_tc_02_01_checksum_calculation():
    payload = b"34ABC123"

    expected = sum(payload) % 256
    actual = calculate_checksum(payload)

    assert actual == expected

    assert calculate_checksum(b"") == 0
    assert calculate_checksum(bytes([255, 1])) == 0

    log_test_result(
        "TC-02-01",
        "PASS",
        "Checksum hesaplama bilinen test vektorleriyle dogrulandi.",
        metrics={
            "payload": payload.decode("utf-8"),
            "checksum": actual,
        },
    )


def test_tc_02_03_state_machine_transitions():
    sm = SimpleStateMachine(max_retry=2)

    assert sm.state == "idle"

    assert sm.handle("capture_trigger") == "capture"
    assert sm.handle("frame_ready") == "send"
    assert sm.handle("send_success") == "idle"

    assert sm.handle("capture_trigger") == "capture"
    assert sm.handle("frame_ready") == "send"

    assert sm.handle("send_fail") == "retry"
    assert sm.handle("retry_tick") == "send"
    assert sm.handle("send_fail") == "retry"
    assert sm.handle("retry_tick") == "send"
    assert sm.handle("send_fail") == "error"

    assert sm.handle("reset") == "idle"

    log_test_result(
        "TC-02-03",
        "PASS",
        "State machine idle-capture-send-retry-error-reset gecisleri dogrulandi.",
    )


def test_tc_02_04_timeout_retry_backoff():
    delays = [
        retry_backoff_delay(1),
        retry_backoff_delay(2),
        retry_backoff_delay(3),
        retry_backoff_delay(4),
        retry_backoff_delay(10),
    ]

    assert delays[0] == 100
    assert delays[1] == 200
    assert delays[2] == 400
    assert delays[3] == 800
    assert delays[4] == 2000

    assert all(delay <= 2000 for delay in delays)

    log_test_result(
        "TC-02-04",
        "PASS",
        "Timeout/retry/backoff algoritmasi beklenen gecikmeleri uretti.",
        metrics={
            "delays_ms": delays,
        },
    )


def test_tc_02_05_ring_buffer_overflow():
    buffer = RingBuffer(capacity=3)

    assert buffer.push("packet-1") is True
    assert buffer.push("packet-2") is True
    assert buffer.push("packet-3") is True

    assert buffer.size() == 3

    overflow_result = buffer.push("packet-4")

    assert overflow_result is False
    assert buffer.size() == 3

    assert buffer.pop() == "packet-1"
    assert buffer.pop() == "packet-2"
    assert buffer.pop() == "packet-3"
    assert buffer.pop() is None

    log_test_result(
        "TC-02-05",
        "PASS",
        "Ring buffer kapasite dolunca overflow kontrollu sekilde reddedildi.",
        metrics={
            "capacity": 3,
            "overflow_blocked": True,
        },
    )


def test_tc_02_06_parameter_read_write(tmp_path):
    config_path = tmp_path / "device_config.json"

    config = {
        "device_id": "RPI-PLATE-001",
        "camera_source": "demo",
        "mode": "DEMO",
        "retry_limit": 3,
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    with open(config_path, "r", encoding="utf-8") as f:
        loaded_config = json.load(f)

    assert loaded_config["device_id"] == "RPI-PLATE-001"
    assert loaded_config["camera_source"] == "demo"
    assert loaded_config["mode"] == "DEMO"
    assert loaded_config["retry_limit"] == 3

    log_test_result(
        "TC-02-06",
        "PASS",
        "Parametre okuma/yazma islemi gecici config dosyasi uzerinde dogrulandi.",
        metrics={
            "config_path": str(config_path),
            "device_id": loaded_config["device_id"],
        },
    )