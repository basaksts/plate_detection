from flask import Flask, render_template, Response
from camera import VideoCamera
from detector import detect_plate

app = Flask(__name__)

camera = VideoCamera()
current_plate = "-"
current_status = "Bekleniyor"
allowed = False


def gen(camera):
    global current_plate, current_status, allowed

    while True:
        frame = camera.get_frame()

        if frame is None:
            continue

        plate, allowed = detect_plate(frame)

        if plate:
            current_plate = plate
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
        logs=[],
    )


@app.route("/video_feed")
def video_feed():
    return Response(
        gen(camera),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)