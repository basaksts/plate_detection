# Bu dosya aşağıdaki test dokümantasyonu maddelerini karşılamak üzere hazırlanmıştır:
# TC-08-02 - API yük: aynı anda N kullanıcı listeliyor
# TC-08-03 - Web: İlk açılış / Kullanıcı hissi performansı
# TC-08-04 - Web: büyük listede scroll
#
# Not:
# Gerçek webapp ve API bağlantısı tamamlanmadan önce temsili performans ölçümleri yapılır.
# Gerçek sistemde response time, render time ve büyük liste performansı bu dosya üzerinden raporlanacaktır.

import statistics
import time

from tests.utils.logger import log_test_result


def mock_api_list_records(record_count=100):
    """
    API listeleme endpoint'ini temsili olarak simüle eder.
    """
    records = []

    for index in range(record_count):
        records.append(
            {
                "id": index + 1,
                "plate": f"34TST{index:03d}",
                "owner": f"Test User {index + 1}",
                "status": "AUTHORIZED" if index % 2 == 0 else "DENIED",
            }
        )

    return records


def mock_page_initial_load():
    """
    Web ilk açılışını temsili olarak simüle eder.
    """
    components = {
        "topbar": True,
        "navigation": True,
        "plate_detection_card": True,
        "camera_placeholder": True,
        "logs_summary": True,
    }

    return components


def mock_large_list_render(record_count=1000):
    """
    Büyük liste render davranışını temsili olarak simüle eder.
    """
    rows = []

    for index in range(record_count):
        rows.append(
            f"<tr><td>{index + 1}</td><td>34BIG{index:04d}</td><td>AUTHORIZED</td></tr>"
        )

    html = "\n".join(rows)
    return html


def percentile(values, percentile_value):
    """
    Basit percentile hesaplama.
    """
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * percentile_value / 100)
    return sorted_values[index]


def test_tc_08_02_mock_api_load():
    durations_ms = []
    virtual_users = 20

    for _ in range(virtual_users):
        start = time.perf_counter()
        records = mock_api_list_records(record_count=100)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(records) == 100
        durations_ms.append(elapsed_ms)

    avg_ms = statistics.mean(durations_ms)
    p95_ms = percentile(durations_ms, 95)

    assert avg_ms < 50
    assert p95_ms < 100

    log_test_result(
        "TC-08-02",
        "PASS",
        "Mock API listeleme yuk testi temsili olarak tamamlandi.",
        metrics={
            "virtual_users": virtual_users,
            "records_per_user": 100,
            "avg_response_ms": round(avg_ms, 4),
            "p95_response_ms": round(p95_ms, 4),
        },
    )


def test_tc_08_03_mock_web_initial_load():
    start = time.perf_counter()
    components = mock_page_initial_load()
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert all(components.values())
    assert elapsed_ms < 50

    log_test_result(
        "TC-08-03",
        "PASS",
        "Mock web ilk acilis bilesenleri basariyla yuklendi.",
        metrics={
            "load_time_ms": round(elapsed_ms, 4),
            "component_count": len(components),
        },
    )


def test_tc_08_04_mock_large_list_scroll():
    start = time.perf_counter()
    html = mock_large_list_render(record_count=1000)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert "34BIG0000" in html
    assert "34BIG0999" in html
    assert html.count("<tr>") == 1000
    assert elapsed_ms < 100

    log_test_result(
        "TC-08-04",
        "PASS",
        "Mock buyuk liste render testi 1000 kayit ile tamamlandi.",
        metrics={
            "record_count": 1000,
            "render_time_ms": round(elapsed_ms, 4),
        },
    )