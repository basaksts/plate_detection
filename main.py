import cv2
import numpy as np
import onnxruntime as ort
import pytesseract
import threading
import re
import time
import sqlite3
import datetime
import urllib.request
from flask import Flask, Response, render_template, jsonify, request
from collections import Counter
from difflib import SequenceMatcher

# --- AYARLAR ---
RTSP_URL = "rtsp://samet_yilmaz:1x1samet1x1@192.168.1.34:554/stream1" # KENDİ KAMERA LİNKİNİ YAZ
MODEL_PATH = "plaka_yolov8.onnx"
DB_NAME = "otopark.db"
CONF_THRES = 0.40 # Hatalı tespitleri (petek/dolap) engellemek için 0.40'a çıkarıldı
IOU_THRES = 0.45
SISTEM_MODU = "GECIS_KONTROL"  # İki değer alabilir: "GECIS_KONTROL" veya "SADECE_KAYIT"

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
TR_REGEX = re.compile(r'(0[1-9]|[1-7][0-9]|8[0-1])\s*[A-Z]{1,4}\s*[0-9]{2,4}')

# --- YENİ MİMARİ GLOBAL DEĞİŞKENLERİ ---
current_frame = None
boxes_to_draw = [] # Ekrana çizilecek kutular
lock = threading.Lock()
last_detected_plate = "---"
last_detected_status = "Sistem Hazır"
last_log_time = 0

app = Flask(__name__)

# --- VERİTABANI FONKSİYONLARI ---
def log_entry(plaka, sahip, durum):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO giris_loglari (plaka, sahip, tarih, durum) VALUES (?, ?, ?, ?)", 
                       (plaka, sahip, zaman, durum))
        conn.commit()
        conn.close()
    except:
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

def open_barrier():
    try:
        urllib.request.urlopen("http://192.168.1.94/ac", timeout=2)
        print("Bariyer acilma sinyali gonderildi!")
    except Exception as e:
        print(f"Bariyer sinyali basarisiz: {e}")

# --- GÖRÜNTÜ İŞLEME ---
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
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17) 
    text = pytesseract.image_to_string(gray, config='--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789').strip()
    match = TR_REGEX.search(text)
    if match: return match.group(0)
    return None

# --- 1. İŞÇİ: SADECE KAMERAYI OKUR (AKICILIK SAĞLAR) ---
def camera_thread():
    global current_frame
    cap = cv2.VideoCapture(RTSP_URL)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Eski görüntüleri çöpe at
    
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            cap = cv2.VideoCapture(RTSP_URL)
            continue
        with lock:
            current_frame = frame.copy()
        time.sleep(0.03) # Saniyede ~30 kare sınırı

# --- 2. İŞÇİ: SADECE YAPAY ZEKA VE PLAKA OKUMA (ISINMAYI ÖNLER) ---
def ai_thread():
    global current_frame, boxes_to_draw, last_detected_plate, last_detected_status, last_log_time
    try:
        session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
    except:
        return

    # --- YENİ EKLENEN HAVUZ DEĞİŞKENLERİ ---
    plaka_havuzu = []
    havuz_baslangic = time.time()
    son_islenen_plaka = ""
    son_islem_zamani = 0
    bekleme_suresi = 5

    while True:
        with lock:
            if current_frame is None:
                frame_ai = None
            else:
                frame_ai = current_frame.copy()
        
        if frame_ai is None:
            time.sleep(0.1)
            continue

        try:
            img_lb, r, (dw, dh) = letterbox(frame_ai)
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
            new_boxes = []
            
            if len(idxs) > 0:
                # Ekranda 10 tane nesne bulsa bile sadece en belirgin 1 tanesini al (İşlemciyi korur)
                i = idxs.flatten()[0] 
                box = boxes[i]
                x1 = max(0, int((box[0] - dw) / r)); y1 = max(0, int((box[1] - dh) / r))
                x2 = min(frame_ai.shape[1], int((box[0] + box[2] - dw) / r))
                y2 = min(frame_ai.shape[0], int((box[1] + box[3] - dh) / r))
                
                if x1 < x2 and y1 < y2:
                    crop = frame_ai[y1:y2, x1:x2]
                    if crop.size > 0:
                        ocr_result = ocr_process(crop)
                        if ocr_result:
                            # 1. Ham sonucu boşluklardan arındırıp büyült
                            temiz_plaka = ocr_result.replace(" ", "").upper()
                            
                            # 2. Çok kısa/hatalı okumaları havuza hiç alma
                            if len(temiz_plaka) >= 5:
                                plaka_havuzu.append(temiz_plaka)

                            # 3. Web sitesinde anlık göstermek için kutu ve yazıyı her karede güncelle
                            is_allowed_temp, _ = check_database(temiz_plaka)
                            color = (0, 255, 0) if is_allowed_temp else (0, 0, 255)
                            status = "GİRİŞ İZNİ" if is_allowed_temp else "YETKİSİZ"
                            
                            new_boxes.append((x1, y1, x2, y2, temiz_plaka, color))
                            last_detected_plate = temiz_plaka
                            last_detected_status = status

                            # ========================================================
                            # 4. HAVUZ KONTROLÜ (Asıl Karar Anı)
                            # Havuzda 10 okuma biriktiyse VEYA 1 saniye geçip havuzda veri varsa karar ver
                            if len(plaka_havuzu) >= 10 or (time.time() - havuz_baslangic > 1.0 and len(plaka_havuzu) > 0):
                                
                                # En çok tekrar eden (en güvenilir) plakayı seç
                                kesin_plaka = Counter(plaka_havuzu).most_common(1)[0][0]
                                
                                # Eğer aynı araç değilse VEYA üzerinden 10 saniye (spam süresi) geçtiyse işlem yap
                                # Plakalar arası benzerlik oranını hesapla (0.0 ile 1.0 arası)
                                benzerlik_orani = SequenceMatcher(None, kesin_plaka, son_islenen_plaka).ratio()
                                
                                # Eğer plaka bir öncekinden TAMAMEN farklıysa (benzerlik %70'in altındaysa) 
                                # VEYA aynı araç bile olsa üzerinden 10 saniye (spam süresi) geçtiyse işlem yap
                                if benzerlik_orani < 0.7 or (time.time() - son_islem_zamani > 10):
                                    
                                    is_allowed, owner = check_database(kesin_plaka)
                                    log_durum = "ONAYLANDI" if is_allowed else "REDDEDİLDİ"
                                    log_sahip = owner if is_allowed else "Bilinmiyor"
                                    
                                    # Veritabanına kaydet
                                    log_entry(kesin_plaka, log_sahip, log_durum)
                                    
                                    # Eğer izinliyse ve geçiş kontrol modundaysa bariyeri aç
                                    if is_allowed and SISTEM_MODU == "GECIS_KONTROL":
                                        threading.Thread(target=open_barrier).start()
                                        
                                    # Son işlenenleri güncelle
                                    son_islenen_plaka = kesin_plaka
                                    son_islem_zamani = time.time()
                                    
                                # Karar verdikten sonra havuzu boşalt ki sıradaki araca hazırlansın
                                plaka_havuzu = []
                                havuz_baslangic = time.time()
            with lock:
                boxes_to_draw = new_boxes
                
        except:
            pass
        
        # ÇOK ÖNEMLİ: İşlemcinin soğuması için her plaka aramasından sonra 0.2 saniye uyu
        time.sleep(0.2)

# --- 3. İŞÇİ (WEB): GÖRÜNTÜYÜ SİTEYE BASAR ---
def generate():
    global current_frame, boxes_to_draw, lock
    while True:
        with lock:
            if current_frame is None:
                frame_web = None
            else:
                frame_web = current_frame.copy()
                current_boxes = boxes_to_draw.copy()
        
        if frame_web is None:
            time.sleep(0.1)
            continue
            
        # Yapay Zekanın bulduğu kutuları akıcı videonun üstüne çiz
        for (x1, y1, x2, y2, text, color) in current_boxes:
            cv2.rectangle(frame_web, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame_web, text, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            
        flag, encodedImage = cv2.imencode(".jpg", frame_web)
        if not flag:
            continue
            
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
        time.sleep(0.05)

# --- FLASK YOLLARI (AYNI KALDI) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/kayitli_araclar", methods=['GET'])
def get_araclar():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM araclar ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    except:
        return jsonify([])

@app.route("/api/arac_ekle", methods=['POST'])
def arac_ekle():
    data = request.json
    plaka = data.get('plaka').upper().replace(" ", "")
    sahip = data.get('sahip')
    if not plaka: return jsonify({"success": False, "message": "Plaka boş olamaz!"})
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO araclar (plaka, sahip) VALUES (?, ?)", (plaka, sahip))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Araç Eklendi!"})
    except:
        return jsonify({"success": False, "message": "Hata veya plaka zaten var!"})

@app.route("/api/arac_sil", methods=['POST'])
def arac_sil():
    data = request.json
    arac_id = data.get('id')
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM araclar WHERE id = ?", (arac_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Araç Silindi!"})
    except:
        return jsonify({"success": False, "message": "Silinemedi!"})

@app.route("/api/arac_guncelle", methods=['POST'])
def arac_guncelle():
    data = request.json
    sahip_adi = data.get('sahip')
    yeni_plaka = data.get('plaka')
    
    if not sahip_adi or not yeni_plaka:
        return jsonify({"status": "error", "message": "Eksik veri gönderildi!"}), 400
        
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Sahip ismine göre plaka bilgisini güncelliyoruz
        cursor.execute("UPDATE araclar SET plaka = ? WHERE sahip = ?", (yeni_plaka, sahip_adi))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Plaka başarıyla güncellendi."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/toplu_ekle", methods=['POST'])
def toplu_ekle():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Dosya seçilmedi!"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Dosya seçilmedi!"}), 400
        
    try:
        # Dosya içeriğini okuyoruz
        lines = file.read().decode('utf-8').splitlines()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        eklenen_sayi = 0
        
        for line in lines:
            # Excel'den gelen başlık satırını atlıyoruz
            if "plaka" in line.lower() or "sahip" in line.lower():
                continue
                
            # Verileri virgül veya noktalı virgülden ayır (Excel ikisini de kullanabilir)
            if ';' in line:
                parcalar = line.split(';')
            else:
                parcalar = line.split(',')
                
            if len(parcalar) >= 2:
                plaka = parcalar[0].strip()
                sahip = parcalar[1].strip()
                
                # Veritabanına ekle (TABLO ADINI BURADA KENDİNKİYLE DEĞİŞTİR)
                cursor.execute("INSERT OR IGNORE INTO araclar (plaka, sahip) VALUES (?, ?)", (plaka, sahip))
                eklenen_sayi += 1
                
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"{eklenen_sayi} adet araç başarıyla eklendi!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/mod_degistir", methods=['POST'])
def mod_degistir():
    global SISTEM_MODU
    data = request.json
    yeni_mod = data.get('mod')
    
    if yeni_mod in ["GECIS_KONTROL", "SADECE_KAYIT"]:
        SISTEM_MODU = yeni_mod
        return jsonify({"status": "success", "message": f"Sistem modu {SISTEM_MODU} olarak güncellendi."})
    else:
        return jsonify({"status": "error", "message": "Geçersiz mod!"}), 400

# Mevcut modu web sitesine göndermek için (Bunu da ekleyelim ki sayfa yenilendiğinde buton doğru dursun)
@app.route("/api/mevcut_mod", methods=['GET'])
def mevcut_mod():
    return jsonify({"mod": SISTEM_MODU})

@app.route("/api/logdan_yetkilendir", methods=['POST'])
def logdan_yetkilendir():
    data = request.json
    plaka = data.get('plaka').replace(" ", "").upper() # Hem boşlukları siler hem büyük harf yapar
    sahip = data.get('sahip') # JavaScript'ten gelen ismi alır
    
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        # TABLO ADINI BURADA KENDİNKİYLE DEĞİŞTİR
        cursor.execute("INSERT OR IGNORE INTO araclar (plaka, sahip) VALUES (?, ?)", (plaka, sahip))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"{plaka} artık izinli!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/tarihe_gore_yetkilendir", methods=['POST'])
def tarihe_gore_yetkilendir():
    data = request.json
    baslangic = data.get('baslangic')
    bitis = data.get('bitis')
    
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cursor = conn.cursor()
        
        # 1. Belirtilen saatler arasındaki benzersiz plakaları loglardan çekiyoruz
        cursor.execute("SELECT DISTINCT plaka FROM giris_loglari WHERE tarih >= ? AND tarih <= ?", (baslangic, bitis))
        plakalar = cursor.fetchall()
        
        eklenen_sayi = 0
        for row in plakalar:
            plaka = row[0]
            
            # 2. Bu plaka zaten izinli listesinde var mı diye kontrol et (TABLO ADINI DEĞİŞTİR)
            cursor.execute("SELECT * FROM araclar WHERE plaka = ?", (plaka,))
            if not cursor.fetchone():
                # Eğer listede yoksa, yeni izinli araç olarak ekle
                cursor.execute("INSERT OR IGNORE INTO araclar (plaka, sahip) VALUES (?, ?)", (plaka, "Toplu Saat Onayı"))
                eklenen_sayi += 1
                
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"İşlem tamam! {eklenen_sayi} adet yeni araç başarıyla izinli listesine eklendi."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/veriler", methods=['GET'])
def get_veriler():
    global last_detected_plate, last_detected_status
    gecmis_girisler = []
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Arayüz tam olarak bu sırayı (id, plaka, sahip, tarih, durum) bekliyor
        cursor.execute("SELECT id, plaka, sahip, tarih, durum FROM giris_loglari ORDER BY id DESC LIMIT 100")
        gecmis_girisler = cursor.fetchall()
        conn.close()
            
    except Exception as e:
        print(f"Log okuma hatası: {e}")

    # "gecmis" yerine arayüzün beklediği "loglar" ismini kullanıyoruz
    return jsonify({
        "son_plaka": last_detected_plate,
        "durum": last_detected_status,
        "loglar": gecmis_girisler 
    })

if __name__ == '__main__':
    # İşçileri (Threadleri) Başlat
    t_cam = threading.Thread(target=camera_thread)
    t_cam.daemon = True
    t_cam.start()
    
    t_ai = threading.Thread(target=ai_thread)
    t_ai.daemon = True
    t_ai.start()
    
    # Web Sunucusunu Başlat
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
