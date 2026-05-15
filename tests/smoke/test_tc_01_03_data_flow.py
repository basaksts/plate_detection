
# Bu dosya aşağıdaki test dokümantasyonu maddesini karşılamak için hazırlanmıştır:
# TC-01-03 - Veri okuma → paketleme → gönderme akıyor mu?
#
# Not:
# Gerçek backend endpointleri tamamlanana kadar mock/temsili veri akışıyla çalıştırılmalıdır.

from utils.logger import log_test_result
import requests

def test_data_flow():
    test_id = "TC-01-03"

    try:
        url = "http://localhost:5000/test-endpoint"

        payload = {"test": "data"}
        response = requests.post(url, json=payload)

        if response.status_code != 200:
            raise Exception("Backend veri almadı")

        log_test_result(test_id, "PASS")

    except Exception as e:
        log_test_result(test_id, "FAIL", str(e))