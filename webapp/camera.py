import cv2


class VideoCamera:
    def __init__(self):
        # Şimdilik bilgisayar kamerasını kullanıyoruz.
        # IP kamera bağlanınca burası RTSP URL ile değiştirilecek.
        self.video = cv2.VideoCapture(0)

    def get_frame(self):
        success, image = self.video.read()

        if not success:
            return None

        _, jpeg = cv2.imencode(".jpg", image)
        return jpeg.tobytes()