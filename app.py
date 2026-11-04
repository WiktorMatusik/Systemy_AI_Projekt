import os
import cv2
import json
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template_string, request, redirect, url_for
from google import genai
from google.genai import types

# ==========================================
# 1. ŚCIEŻKI I WCZYTANIE KLUCZY / BAZY
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(BASE_DIR, 'KEY.json')
BAZA_FILE = os.path.join(BASE_DIR, 'baza.json')
TEST_DIR = os.path.join(BASE_DIR, 'DataSet1', 'test')

# Wczytanie klucza API Gemini
API_KEY = None
if os.path.exists(KEY_FILE):
    try:
        with open(KEY_FILE, 'r', encoding='utf-8') as f:
            API_KEY = json.load(f).get("api_key")
    except Exception as e:
        print(f"[LOG ERROR] Błąd odczytu KEY.json: {e}")

client = genai.Client(api_key=API_KEY) if API_KEY else None

# Kolejka oczekujących wiadomości e-mail (lista słowników)
pending_emails = []

# Konfiguracja SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "projektai2137@gmail.com"
SMTP_PASSWORD = "dnvu rghj ihcl etpd"

def load_baza_emails():
    """Wczytuje mapowanie z baza.json i konwertuje klucze na wielkie litery"""
    if os.path.exists(BAZA_FILE):
        try:
            with open(BAZA_FILE, 'r', encoding='utf-8') as f:
                raw_baza = json.load(f)
                return {k.strip().upper(): v.strip() for k, v in raw_baza.items()}
        except Exception as e:
            print(f"[LOG BAZA ERROR] Błąd odczytu baza.json: {e}")
    return {}

# ==========================================
# 2. WYSYŁKA SMTP
# ==========================================
def send_email(recipient_email, subject, body_text):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.close()
        print(f"[LOG SMTP] E-mail wysłany pomyślnie do {recipient_email}")
        return True
    except Exception as e:
        print(f"[LOG SMTP ERROR] Błąd wysyłki: {e}")
        return False

# ==========================================
# 3. OBSŁUGA ZDJĘĆ Z DATASET1/TEST I GEMINI
# ==========================================
MODELE = ['gemini-3.1-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash']

def get_available_jpg_files():
    """Zwraca listę wszystkich plików .jpg z folderu DataSet1/test"""
    if not os.path.exists(TEST_DIR):
        return []
    return [f for f in os.listdir(TEST_DIR) if f.lower().endswith('.jpg')]

def process_single_image(image_filename):
    """Przetwarza wybrany plik JPG z DataSet1/test i dodaje go do kolejki"""
    image_path = os.path.join(TEST_DIR, image_filename)
    if not os.path.exists(image_path) or not client:
        return

    print(f"[LOG Gemini] Analizuję plik: {image_filename}...")
    img = cv2.imread(image_path)
    if img is None:
        return

    h, w = img.shape[:2]
    if w > 1600:
        skala = 1600.0 / w
        img_small = cv2.resize(img, (1600, int(h * skala)), interpolation=cv2.INTER_AREA)
    else:
        img_small = img.copy()

    _, buffer = cv2.imencode('.jpg', img_small, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

    prompt = (
        "Przeanalizuj to zdjęcie. Znajdź imię i nazwisko głównej osoby. "
        "Zwróć TYLKO imię i nazwisko wielkimi literami w jednej linii (np. JAN KOWALSKI). "
        "Nie dodawaj żadnych innych słów ani znaków."
    )

    odczytana_osoba = "NIEZNANA OSOBA"
    uzyty_model = "Brak"

    for model_name in MODELE:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=buffer.tobytes(), mime_type='image/jpeg'),
                    prompt
                ]
            )
            odczytana_osoba = response.text.strip().upper()
            uzyty_model = model_name
            break
        except Exception as e:
            err_msg = str(e)
            if '503' in err_msg or 'UNAVAILABLE' in err_msg or '429' in err_msg:
                time.sleep(2)

    # Wyszukiwanie maila z baza.json
    baza = load_baza_emails()
    matched_email = baza.get(odczytana_osoba, "brak_w_bazie@domena.com")
    tresc = f"Cześć {odczytana_osoba.title()},\n\nW skrytce czeka Twój dokument."

    new_item = {
        "id": int(time.time() * 1000),
        "filename": image_filename,
        "person": odczytana_osoba,
        "email": matched_email,
        "body": tresc,
        "status": "Oczekuje na wysłanie"
    }
    pending_emails.insert(0, new_item)
    print(f"[LOG KOLEJKA] Dodano [{image_filename}]: {odczytana_osoba} -> {matched_email}")

# ==========================================
# 4. OBSŁUGA PRZYCISKU GPIO (gpiod v2)
# ==========================================
def listen_button():
    try:
        import gpiod
        chip = gpiod.Chip('gpiochip1')
        line = chip.get_line(17)
        line.request(consumer="button_app", type=gpiod.LINE_REQ_EV_FALLING_EDGE)
        while True:
            if line.event_wait(1):
                line.event_read()
                print("[LOG GPIO] Wykryto kliknięcie przycisku!")
                files = get_available_jpg_files()
                if files:
                    process_single_image(files[0])
    except Exception as e:
        print(f"[LOG GPIO WARNING] Nasłuch przycisku nieaktywny: {e}")

threading.Thread(target=listen_button, daemon=True).start()

# ==========================================
# 5. STRONA WWW (FLASK INTERFEJS)
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel Skrytki - Kolejka dokumentów</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background: #eef2f5; }
        .container { max-width: 900px; margin: 0 auto; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .control-panel { background: #ffffff; border-left: 5px solid #007bff; }
        h1, h3 { color: #2c3e50; margin-top: 0; }
        select, input[type="text"], input[type="email"], textarea { width: 100%; padding: 8px; margin: 5px 0 15px 0; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        textarea { height: 80px; }
        .btn-send { background: #28a745; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-delete { background: #dc3545; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
        .btn-action { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-right: 10px; }
        .btn-all { background: #17a2b8; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .status { font-weight: bold; color: #17a2b8; float: right; }
        .badge { background: #6c757d; color: white; padding: 3px 7px; border-radius: 3px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Panel Skrytki - Kolejka dokumentów</h1>
        
        <div class="card control-panel">
            <h3>Wybranie / skanowanie dokumentów z DataSet1/test</h3>
            <form action="/scan" method="POST" style="margin-bottom: 10px;">
                <label><b>Wybierz plik z folderu do przetworzenia:</b></label>
                <select name="selected_file">
                    {% for f in available_files %}
                        <option value="{{ f }}">{{ f }}</option>
                    {% endfor %}
                </select>
                <button type="submit" class="btn-action">⚡ Przetwórz wybrane zdjęcie</button>
                <button type="submit" name="scan_all" value="true" class="btn-all">🔄 Przetwórz WSZYSTKIE pliki .JPG</button>
            </form>
        </div>

        <h2>Oczekujące powiadomienia ({{ emails|length }})</h2>

        {% if not emails %}
            <div class="card">
                <p>Brak wiadomości w kolejce. Wybierz plik z listy rozwijanej powyżej i kliknij <b>"Przetwórz wybrane zdjęcie"</b>.</p>
            </div>
        {% endif %}

        {% for item in emails %}
        <div class="card">
            <span class="status">Status: {{ item.status }}</span>
            <span class="badge">Plik: {{ item.filename }}</span>
            <form action="/action" method="POST" style="margin-top: 15px;">
                <input type="hidden" name="item_id" value="{{ item.id }}">
                
                <label>Odczytana osoba (Gemini API):</label>
                <input type="text" value="{{ item.person }}" readonly style="background: #e9ecef;">

                <label>Adres E-mail odbiorcy (z baza.json / do edycji):</label>
                <input type="email" name="email" value="{{ item.email }}" required>

                <label>Treść wiadomości:</label>
                <textarea name="body">{{ item.body }}</textarea>

                <button type="submit" name="btn_action" value="send" class="btn-send">Wyślij E-mail</button>
                <button type="submit" name="btn_action" value="delete" class="btn-delete">Usuń z listy</button>
            </form>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    files = get_available_jpg_files()
    return render_template_string(HTML_TEMPLATE, emails=pending_emails, available_files=files)

@app.route('/scan', methods=['POST'])
def scan_files():
    scan_all = request.form.get('scan_all')
    selected_file = request.form.get('selected_file')

    if scan_all == 'true':
        for f in get_available_jpg_files():
            process_single_image(f)
    elif selected_file:
        process_single_image(selected_file)

    return redirect(url_for('index'))

@app.route('/action', methods=['POST'])
def handle_action():
    item_id = int(request.form.get('item_id'))
    action = request.form.get('btn_action')
    email = request.form.get('email')
    body = request.form.get('body')

    for item in pending_emails:
        if item['id'] == item_id:
            if action == 'send':
                success = send_email(email, "Wiadomość ze skrytki - Twój dokument", body)
                if success:
                    pending_emails.remove(item)
            elif action == 'delete':
                pending_emails.remove(item)
            break

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
