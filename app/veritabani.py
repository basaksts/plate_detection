import sqlite3

DB_NAME = "otopark.db"

def tablo_olustur():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS araclar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT UNIQUE NOT NULL,
            sahip TEXT,
            durum TEXT DEFAULT 'AKTIF'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giris_loglari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plaka TEXT,
            sahip TEXT,
            tarih TEXT,
            durum TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[BİLGİ] Veritabanı ve tablolar hazır.")

if __name__ == "__main__":
    tablo_olustur()
