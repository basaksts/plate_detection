import cv2
import numpy as np
import onnxruntime as ort
import pytesseract
import threading
import re
import time
import sqlite3
import datetime
import os 
app = Flask(__name__, template_folder="templates", static_folder="static")
from flask import Flask, Response, render_template, jsonify, request


# --- AYARLAR ---
RTSP_URL = "rtsp://admin:12345@192.168.1.XX:554/stream1" # Test için kendi kameranızı yazın
MODEL_PATH = "plaka_yolov8.onnx"
DB_NAME = "otopark.db"
CONF_THRES = 0.25
IOU_THRES = 0.45


# Tesseract Yolu
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TR_REGEX = re.compile(r'(0[1-9]|[1-7][0-9]|8[0-1])\s*[A-Z]{1,4}\s*[0-9]{2,4}')

output_frame = None
lock = threading.Lock()
last_detected_plate = "---"
last_detected_status = "Sistem Hazır"
last_log_time = 0

app = Flask(__name__)

# --- VERİTABANI FONKSİYONLARI ---
# (Veritabanı işlemleri log_entry, get_last_logs, check_database vb. burada çalışır)
def log_entry(plaka, sahip, durum):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO giris_loglari (plaka, sahip, tarih, durum) VALUES (?, ?, ?, ?)", 
                       (plaka, sahip, zaman, durum))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def check_database(plaka):
    clean_search = plaka.upper().replace(" ", "")
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT sahip FROM araclar WHERE plaka = ?", (clean_search,))
        result = cursor.fetchone()
        conn.close()
        if result: return True, result[0]
        return False, "Misafir"
    except:
        return False, "Hata"

# --- GÖRÜNTÜ İŞLEME VE OCR FONKSİYONLARI ---
def letterbox(im, new_shape=(640, 640), color=(114, 114, 114)):
    shape = im.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2; dh /= 2
    im_resized = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im_padded = cv2.copyMakeBorder(im_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im_padded, r, (dw, dh)

def ocr_process(crop):
    """Kırpılan plaka bölgesinden Tesseract ile yazı okur ve Regex ile doğrular."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17) 
    text = pytesseract.image_to_string(gray, config='--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').strip()
    match = TR_REGEX.search(text)
    if match: return match.group(0)
    return None

# --- YOLOv8 ANA İŞLEM THREAD'İ ---
def processing_thread():
    global output_frame, last_detected_plate, last_detected_status, last_log_time
    cap = cv2.VideoCapture(RTSP_URL)
    session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            cap = cv2.VideoCapture(RTSP_URL)
            continue

        img_lb, r, (dw, dh) = letterbox(frame)
        img_input = np.transpose(img_lb, (2, 0, 1))[None].astype(np.float32) / 255.0
        out = session.run(None, {session.get_inputs()[0].name: img_input})[0]
        
        det = out[0].transpose(1, 0)
        boxes, scores = [], []
        for row in det:
            if row[4] < CONF_THRES: continue
            x, y, w, h = row[:4]
            boxes.append([x - w/2, y - h/2, w, h])
            scores.append(float(row[4]))
        
        idxs = cv2.dnn.NMSBoxes(boxes, scores, 0.0, IOU_THRES)

        detected_text = "..."
        status_color = (0, 255, 255)

        if len(idxs) > 0:
            for i in idxs.flatten():
                box = boxes[i]
                x1 = max(0, int((box[0] - dw) / r)); y1 = max(0, int((box[1] - dh) / r))
                x2 = min(frame.shape[1], int((box[0] + box[2] - dw) / r))
                y2 = min(frame.shape[0], int((box[1] + box[3] - dh) / r))
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                crop = frame[y1:y2, x1:x2]
                ocr_result = ocr_process(crop)
                
                if ocr_result:
                    detected_text = ocr_result
                    is_allowed, owner = check_database(detected_text)
                    
                    if is_allowed:
                        status_color = (0, 255, 0)
                        last_detected_status = "GİRİŞ İZNİ"
                        if time.time() - last_log_time > 10:
                            log_entry(detected_text, owner, "ONAYLANDI")
                            last_log_time = time.time()
                    else:
                        status_color = (0, 0, 255)
                        last_detected_status = "YETKİSİZ"
                        if time.time() - last_log_time > 10:
                            log_entry(detected_text, "Bilinmiyor", "REDDEDİLDİ")
                            last_log_time = time.time()

                    last_detected_plate = detected_text
                    cv2.putText(frame, detected_text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

        with lock:
            output_frame = frame.copy()

if __name__ == '__main__':
    t = threading.Thread(target=processing_thread)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
