import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "test_results"
RESULTS_FILE = RESULTS_DIR / "test_results.json"


def log_test_result(test_id, status, details="", metrics=None):
    """
    Test sonuçlarını JSON dosyasına ekler.
    
    Parametreler:
    - test_id: TC-00-01 gibi test case numarası
    - status: PASS / FAIL / SKIP
    - details: test hakkında kısa açıklama
    - metrics: doğruluk, süre, kayıt sayısı gibi ek ölçümler
    """
    RESULTS_DIR.mkdir(exist_ok=True)

    if metrics is None:
        metrics = {}

    record = {
        "test_id": str(test_id),
        "status": str(status),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "details": str(details),
        "metrics": metrics,
    }

    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except json.JSONDecodeError:
            existing = []
    else:
        existing = []

    existing.append(record)

    RESULTS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return record