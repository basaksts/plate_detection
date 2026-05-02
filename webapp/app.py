from flask import Flask, render_template, Response
from camera import VideoCamera
from detector import detect_plate

app = Flask(__name__)

camera = VideoCamera()

current_plate = "34AB1234"
current_status = "GİRİŞ İZNİ"
allowed = True

mock_logs = [
    {"time": "12:42:08", "plate": "34AB1234", "allowed": True},
    {"time": "12:39:11", "plate": "34AVEC01", "allowed": False},
    {"time": "12:36:44", "plate": "34MEF330", "allowed": True},
    {"time": "12:34:22", "plate": "35ABC123", "allowed": False},
    {"time": "12:31:05", "plate": "34AB1234", "allowed": True},
]

mock_vehicles = [
    {"plate": "34AB1234", "owner": "Başak Serttaş"},
    {"plate": "34MEF330", "owner": "Mehmet Aksoy"},
    {"plate": "35NMB129", "owner": "Samet Yılmaz"},
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
    return render_template(
        "index.html",
        plate=current_plate,
        status=current_status,
        status_class="authorized" if allowed else "unauthorized",
        logs=mock_logs,
        vehicles=mock_vehicles,
    )


@app.route("/video_feed")
def video_feed():
    return Response(
        gen(camera),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)