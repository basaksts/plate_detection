
# Bu dosya aşağıdaki test dokümantasyonu maddesini karşılamak için hazırlanmıştır:
# TC-01-05 - OCR pipeline “1 örnek görüntü” üzerinde sonuç üretiyor mu?
#
# Not:
# Gerçek OCR doğruluğu yerine şu aşamada pipeline'ın örnek/sentetik görüntüyle çalışması kontrol edilir.

from utils.logger import log_test_result
import subprocess
import json
import os

def test_ocr_pipeline():
    test_id = "TC-01-05"

    try:
        image_path = "sample.jpg"
        output_path = "output.json"

        # pipeline çalıştır (repo'na göre değiştirirsin)
        result = subprocess.run(
            ["python", "detect.py", "--source", image_path, "--save-json"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception("Pipeline çalışmadı")

        if not os.path.exists(output_path):
            raise Exception("Output dosyası yok")

        with open(output_path) as f:
            data = json.load(f)

        if "plate" not in data:
            raise Exception("Plate sonucu yok")

        log_test_result(test_id, "PASS")

    except Exception as e:

        log_test_result(test_id, "FAIL", str(e))

