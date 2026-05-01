"""
utils/logger.py — Test sonuçlarını JSON dosyasına kaydeden loglayıcı
TC-01-03 ve diğer testlerde kullanılır.
"""

import json
import os
import datetime

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "..", "test_results", "results.json")


def log_test_result(test_id: str, status: str, hata: str = None):
    """
    Test sonucunu results.json'a ekler.

    Args:
        test_id : TC-01-03 gibi test kimliği
        status  : "PASS" veya "FAIL"
        hata    : FAIL durumunda hata mesajı (opsiyonel)
    """
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)

    kayit = {
        "test_id": test_id,
        "status":  status,
        "tarih":   datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if hata:
        kayit["hata"] = hata

    # Mevcut kayıtları oku
    veriler = []
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                veriler = json.load(f)
        except (json.JSONDecodeError, IOError):
            veriler = []

    veriler.append(kayit)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(veriler, f, ensure_ascii=False, indent=2)

    # Konsola da yaz
    renk = "\033[92m" if status == "PASS" else "\033[91m"
    reset = "\033[0m"
    print(f"{renk}[{status}]{reset} {test_id}" + (f" — {hata}" if hata else ""))
