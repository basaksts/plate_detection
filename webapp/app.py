from flask import Flask, render_template, Response
from camera import VideoCamera
from detector import detect_plate

app = Flask(__name__)

camera = VideoCamera()

current_plate = "34AB1234"
current_status = "GİRİŞ İZNİ"
current_confidence = 94
current_time = "14:32:08"
allowed = True

mock_logs = [
    {"time": "14:32:08", "plate": "34AB1234", "allowed": True},
    {"time": "14:28:41", "plate": "34AVEC01", "allowed": False},
    {"time": "14:21:17", "plate": "34MEF330", "allowed": True},
    {"time": "14:13:52", "plate": "35ABC123", "allowed": False},
    {"time": "14:02:36", "plate": "34AB1234", "allowed": True},
    {"time": "13:54:22", "plate": "35NMB129", "allowed": True},
]

mock_vehicles = [
    {"plate": "34AB1234", "owner": "Başak Serttaş"},
    {"plate": "34MEF330", "owner": "Mehmet Aksoy"},
    {"plate": "35NMB129", "owner": "Samet Yılmaz"},
]

system_status = [
    {"name": "Camera", "value": "Connected", "state": "ok"},
    {"name": "OCR Engine", "value": "Demo Mode", "state": "warning"},
    {"name": "Database", "value": "Not Connected", "state": "warning"},
    {"name": "ESP32 Barrier", "value": "Not Connected", "state": "warning"},
    {"name": "Application Mode", "value": "DEMO", "state": "ok"},
]


def gen(camera):
    global current_plate, current_status, allowed

    while True:
        frame = camera.get_frame()

        if frame is None:
            continue

        plate, allowed_result = detect_plate(frame)

        if plate:
            current_plate = plate
            allowed = allowed_result
            current_status = "GİRİŞ İZNİ" if allowed else "YETKİSİZ"

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
        )


@app.route("/")
def index():
    total_logs = len(mock_logs)
    allowed_count = sum(1 for log in mock_logs if log["allowed"])
    denied_count = total_logs - allowed_count

    return render_template(
        "index.html",
        plate=current_plate,
        status=current_status,
        confidence=current_confidence,
        detection_time=current_time,
        status_class="authorized" if allowed else "unauthorized",
        logs=mock_logs,
        vehicles=mock_vehicles,
        system_status=system_status,
        total_logs=total_logs,
        allowed_count=allowed_count,
        denied_count=denied_count,
    )


@app.route("/video_feed")
def video_feed():
    return Response(
        gen(camera),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)