import json
from datetime import datetime
from pathlib import Path


RESULTS_DIR = Path(__file__).resolve().parents[1] / "test_results"
RESULTS_FILE = RESULTS_DIR / "results.json"


def log_test_result(test_id, status, details=None, metrics=None):
    """
    Test sonucunu JSON dosyasına ekler.
    status: PASS / FAIL / SKIP
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "test_id": test_id,
        "status": status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "details": details or "",
        "metrics": metrics or {},
    }

    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    else:
        data = []

    data.append(record)

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return record

