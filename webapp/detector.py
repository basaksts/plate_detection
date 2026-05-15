import random

def detect_plate(frame_bytes):
    plates = ["34ABC123", "35XYZ987", None]

    plate = random.choice(plates)

    allowed_list = ["34ABC123"]

    if plate:
        return plate, plate in allowed_list

    return None, False