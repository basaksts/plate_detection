import cv2

class VideoCamera:
    def __init__(self):
<<<<<<< Updated upstream
        self.video = cv2.VideoCapture("rtsp://192.168.x.x:554/...")
=======
        self.video = cv2.VideoCapture(0)
>>>>>>> Stashed changes

    def get_frame(self):
        success, image = self.video.read()

        if not success:
            return None

        _, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()