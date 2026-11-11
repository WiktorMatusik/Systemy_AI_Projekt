import os
import cv2
import json
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, session
from google import genai
from google.genai import types

# ==========================================
# 1. ŚCIEŻKI I WCZYTANIE KLUCZY / BAZY
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(BASE_DIR, 'KEY.json')
BAZA_FILE = os.path.join(BASE_DIR, 'baza.json')
TEST_DIR = os.path.join(BASE_DIR, 'DataSet1', 'test')
PENDING_FILE = os.path.join(BASE_DIR, 'pending.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'history.json')

# Wczytanie klucza API Gemini
API_KEY = None
if os.path.exists(KEY_FILE):
    try:
        with open(KEY_FILE, 'r', encoding='utf-8') as f:
            API_KEY = json.load(f).get("api_key")
    except Exception as e:
        print(f"[LOG ERROR] Błąd odczytu KEY.json: {e}")

client = genai.Client(api_key=API_KEY) if API_KEY else None

# Konfiguracja SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "projektai2137@gmail.com"
SMTP_PASSWORD = "dnvu rghj ihcl etpd"

# ==========================================
# FUNKCJE ZAPISU I ODCZYTU DANYCH (JSON)
# ==========================================
def load_json_file(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[LOG ERROR] Błąd odczytu {os.path.basename(file_path)}: {e}")
    return []

def save_json_file(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[LOG ERROR] Błąd zapisu {os.path.basename(file_path)}: {e}")

pending_emails = load_json_file(PENDING_FILE)
sent_history = load_json_file(HISTORY_FILE)

def load_baza_emails():
    if os.path.exists(BAZA_FILE):
        try:
            with open(BAZA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[LOG BAZA ERROR] Błąd odczytu baza.json: {e}")
    return {}

def save_baza_emails(baza_data):
    try:
        with open(BAZA_FILE, 'w', encoding='utf-8') as f:
            json.dump(baza_data, f, ensure_ascii=False, indent=4)
        print(f"[LOG BAZA] Zaktualizowano pomyślnie baza.json")
    except Exception as e:
        print(f"[LOG BAZA ERROR] Błąd zapisu baza.json: {e}")

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
    if not os.path.exists(TEST_DIR):
        return []
    
    files_info = []
    for f in os.listdir(TEST_DIR):
        if f.lower().endswith('.jpg'):
            path = os.path.join(TEST_DIR, f)
            mtime = os.path.getmtime(path)
            date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            files_info.append({
                "filename": f,
                "date": date_str,
                "timestamp": mtime
            })
    
    files_info.sort(key=lambda x: x["timestamp"], reverse=True)
    return files_info

def process_single_image(image_filename):
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
            break
        except Exception as e:
            err_msg = str(e)
            if '503' in err_msg or 'UNAVAILABLE' in err_msg or '429' in err_msg:
                time.sleep(2)

    raw_baza = load_baza_emails()
    baza_upper = {k.strip().upper(): v.strip() for k, v in raw_baza.items()}
    matched_email = baza_upper.get(odczytana_osoba, "brak_w_bazie@domena.com")
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
    save_json_file(PENDING_FILE, pending_emails)
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
                    process_single_image(files[0]["filename"])
    except Exception as e:
        print(f"[LOG GPIO WARNING] Nasłuch przycisku nieaktywny: {e}")

threading.Thread(target=listen_button, daemon=True).start()

# ==========================================
# 5. STRONA WWW (FLASK INTERFEJS)
# ==========================================
app = Flask(__name__)
app.secret_key = 'tajny_klucz_sesji_skrytka_2026'  # Wymagane do obsługi logowania przez session

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Logowanie - Panel Skrytki</title>
    <style>
        body { font-family: Arial, sans-serif; background: #eef2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); width: 320px; }
        h2 { color: #2c3e50; margin-top: 0; text-align: center; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 8px 0 20px 0; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        .btn-login { width: 100%; background: #007bff; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-login:hover { background: #0056b3; }
        .error { color: #dc3545; font-size: 13px; text-align: center; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>Logowanie</h2>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST" action="/login">
            <label><b>Login:</b></label>
            <input type="text" name="username" required autocomplete="off">

            <label><b>Hasło:</b></label>
            <input type="password" name="password" required>

            <button type="submit" class="btn-login">Zaloguj się</button>
        </form>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel Skrytki - Kolejka dokumentów</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #eef2f5; padding-top: 20px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
        
        .menu-btn {
            position: fixed;
            top: 15px;
            left: 15px;
            z-index: 1001;
            background: #2c3e50;
            color: white;
            border: none;
            padding: 10px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 18px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .menu-btn:hover { background: #34495e; }

        .sidebar {
            height: 100%;
            width: 0;
            position: fixed;
            z-index: 1000;
            top: 0;
            left: 0;
            background-color: #2c3e50;
            overflow-x: hidden;
            transition: 0.3s;
            padding-top: 60px;
            box-shadow: 3px 0 10px rgba(0,0,0,0.3);
        }
        .sidebar a {
            padding: 12px 20px;
            text-decoration: none;
            font-size: 16px;
            color: #b8c7ce;
            display: block;
            transition: 0.2s;
            border-bottom: 1px solid #34495e;
        }
        .sidebar a:hover {
            color: #ffffff;
            background-color: #1abc9c;
        }
        .sidebar .close-btn {
            position: absolute;
            top: 10px;
            right: 15px;
            font-size: 24px;
            margin-left: 50px;
            border: none;
            background: none;
            color: white;
            cursor: pointer;
        }

        .main-layout { display: flex; gap: 20px; align-items: flex-start; margin-top: 20px; }
        .left-column { flex: 1; min-width: 320px; }
        .right-column { flex: 2; min-width: 450px; }
        
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .control-panel { background: #ffffff; border-left: 5px solid #007bff; }
        h1, h2, h3 { color: #2c3e50; margin-top: 0; }
        select, input[type="text"], input[type="email"], textarea { width: 100%; padding: 8px; margin: 5px 0 15px 0; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        textarea { height: 80px; }
        
        .btn-send { background: #28a745; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-delete { background: #dc3545; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
        .btn-action { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-right: 10px; }
        .btn-all { background: #17a2b8; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-trash { background: #6c757d; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-refresh { background: #ffc107; color: #333; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .btn-clear-all { background: #dc3545; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px; }
        
        .status { font-weight: bold; color: #17a2b8; float: right; }
        .badge { background: #6c757d; color: white; padding: 3px 7px; border-radius: 3px; font-size: 12px; }
        
        .select-preview-container { display: flex; gap: 15px; align-items: center; margin-bottom: 15px; }
        .select-box { flex: 1; }
        .preview-box { width: 90px; height: 90px; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; background: #f8f9fa; display: flex; align-items: center; justify-content: center; }
        .preview-box img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.2s; display: block; }
        .preview-box img:hover { transform: scale(1.05); }
        .preview-placeholder { font-size: 11px; color: #999; text-align: center; padding: 5px; }

        .card-content { display: flex; gap: 15px; align-items: flex-start; }
        .image-preview { flex: 0 0 140px; text-align: center; }
        .image-preview img { width: 100%; max-height: 130px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd; cursor: pointer; transition: transform 0.2s; }
        .image-preview img:hover { transform: scale(1.03); }
        .form-fields { flex: 1; }
        
        .history-card { background: #fdfdfe; border-left: 4px solid #6c757d; font-size: 14px; }
        .history-meta { font-size: 12px; color: #666; margin-bottom: 8px; }
    </style>
    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "250px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; }

        function updatePreview(selectElement) {
            const selectedOption = selectElement.options[selectElement.selectedIndex];
            const filename = selectedOption.value;
            const previewLink = document.getElementById('preview-link');
            const imgElement = document.getElementById('selected-preview-img');
            const placeholder = document.getElementById('preview-placeholder');
            
            if (filename) {
                const imageUrl = "/test-images/" + filename;
                imgElement.src = imageUrl;
                previewLink.href = imageUrl;
                previewLink.style.display = "block";
                placeholder.style.display = "none";
            } else {
                previewLink.style.display = "none";
                placeholder.style.display = "block";
            }
        }

        function confirmDelete(formElement) {
            const selectElement = formElement.querySelector('select[name="selected_file"]');
            const filename = selectElement.value;
            if (!filename) {
                alert("Najpierw wybierz plik z listy, który chcesz usunąć!");
                return false;
            }
            return confirm("Czy na pewno chcesz trwale usunąć plik '" + filename + "' z folderu?");
        }

        function confirmClearHistory() {
            return confirm("Czy na pewno chcesz usunąć WSZYSTKIE wpisy z historii wysłanych e-maili?");
        }
    </script>
</head>
<body>

    <button class="menu-btn" onclick="openNav()">☰</button>

    <div id="mySidebar" class="sidebar">
        <button class="close-btn" onclick="closeNav()">×</button>
        <a href="{{ url_for('index') }}" style="font-weight: bold; color: #fff;">🏠 Strona Główna</a>
        <a href="{{ url_for('lista_osob') }}">👥 Lista osób</a>
        <a href="{{ url_for('ustawienia') }}">⚙️ Ustawienia</a>
        <a href="{{ url_for('logout') }}" style="color: #ff6b6b; margin-top: 20px;">🚪 Wyloguj się</a>
    </div>

    <div class="container">
        <h1 style="margin-left: 50px;">Panel Skrytki - Kolejka dokumentów</h1>
        
        <div class="card control-panel">
            <h3>Wybranie / skanowanie dokumentów z DataSet1/test</h3>
            <form id="scan-form" action="/scan" method="POST">
                <label><b>Wybierz plik z folderu (nazwa i data utworzenia):</b></label>
                
                <div class="select-preview-container">
                    <div class="select-box">
                        <select name="selected_file" onchange="updatePreview(this)" required>
                            <option value="" disabled selected>-- Wybierz zdjęcie z listy --</option>
                            {% for f in available_files %}
                                <option value="{{ f.filename }}">{{ f.filename }} (Dodano: {{ f.date }})</option>
                            {% endfor %}
                        </select>
                        <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                            <button type="submit" class="btn-action">⚡ Przetwórz wybrane zdjęcie</button>
                            <button type="submit" name="scan_all" value="true" class="btn-all">🔄 Przetwórz WSZYSTKIE pliki .JPG</button>
                            <button type="submit" formaction="/delete-file" formmethod="POST" onclick="return confirmDelete(document.getElementById('scan-form'));" class="btn-trash">🗑️ Usuń plik z dysku</button>
                            <button type="button" onclick="location.reload();" class="btn-refresh">🔄 Odśwież stronę</button>
                        </div>
                    </div>
                    
                    <div class="preview-box">
                        <span id="preview-placeholder" class="preview-placeholder">Brak podglądu</span>
                        <a id="preview-link" href="#" target="_blank" style="display: none;">
                            <img id="selected-preview-img" src="" alt="Podgląd">
                        </a>
                    </div>
                </div>
            </form>
        </div>

        <div class="main-layout">
            
            <div class="left-column">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h2 style="margin: 0;">Historia ({{ history|length }})</h2>
                    {% if history %}
                    <form action="/clear-history" method="POST" onsubmit="return confirmClearHistory();" style="margin: 0;">
                        <button type="submit" class="btn-clear-all">🗑️ Usuń wszystkie</button>
                    </form>
                    {% endif %}
                </div>
                
                {% if not history %}
                    <div class="card">
                        <p style="color: #666; font-size: 14px;">Brak wysłanych e-maili w historii.</p>
                    </div>
                {% endif %}

                {% for h_item in history %}
                <div class="card history-card">
                    <span class="badge" style="float: right;">Wysłano</span>
                    <div class="history-meta">📅 {{ h_item.sent_date }}</div>
                    <div style="margin-bottom: 8px;"><b>Odbiorca:</b> {{ h_item.email }}</div>
                    <div style="margin-bottom: 10px;"><b>Osoba:</b> {{ h_item.person }}</div>
                    
                    <div class="card-content">
                        <div class="image-preview" style="flex: 0 0 90px;">
                            <a href="{{ url_for('get_test_image', filename=h_item.filename) }}" target="_blank">
                                <img src="{{ url_for('get_test_image', filename=h_item.filename) }}" alt="Podgląd">
                            </a>
                        </div>
                        <div style="font-size: 12px; color: #444; background: #fff; padding: 6px; border-radius: 4px; border: 1px solid #ddd; flex: 1; max-height: 90px; overflow-y: auto;">
                            {{ h_item.body | replace('\\n', '<br>') | safe }}
                        </div>
                    </div>

                    <form action="/history-action" method="POST" style="margin-top: 12px; display: flex; gap: 8px;">
                        <input type="hidden" name="history_id" value="{{ h_item.id }}">
                        <button type="submit" name="action" value="resend" class="btn-action" style="padding: 6px 10px; font-size: 12px; margin: 0;">🔄 Wyślij ponownie</button>
                        <button type="submit" name="action" value="delete" class="btn-delete" style="padding: 6px 10px; font-size: 12px;">❌ Usuń</button>
                    </form>
                </div>
                {% endfor %}
            </div>

            <div class="right-column">
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
                    
                    <div class="card-content" style="margin-top: 15px;">
                        <div class="image-preview">
                            <a href="{{ url_for('get_test_image', filename=item.filename) }}" target="_blank">
                                <img src="{{ url_for('get_test_image', filename=item.filename) }}" alt="Podgląd {{ item.filename }}">
                            </a>
                            <small style="color: #666; display: block; margin-top: 5px;">Kliknij, aby powiększyć</small>
                        </div>

                        <div class="form-fields">
                            <form action="/action" method="POST">
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
                    </div>
                </div>
                {% endfor %}
            </div>

        </div>
    </div>
</body>
</html>
"""

# ==========================================
# TRASY FLASK (LOGOWANIE + OCHRONA)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Błędny login lub hasło!")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Zabezpieczenie wszystkich głównych tras za pomocą dekoratora lub sprawdzenia sesji
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    files = get_available_jpg_files()
    return render_template_string(HTML_TEMPLATE, emails=pending_emails, history=sent_history, available_files=files)

@app.route('/lista-osob')
def lista_osob():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    baza = load_baza_emails()
    template = """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Lista osób - Panel Skrytki</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 30px; background: #eef2f5; }
            .container { max-width: 900px; margin: 0 auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            h2, h3 { color: #2c3e50; margin-top: 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
            th { background-color: #007bff; color: white; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .btn-back { display: inline-block; background: #6c757d; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; margin-bottom: 20px; font-weight: bold; }
            .btn-back:hover { background: #5a6268; }
            .btn-save { background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-weight: bold; }
            .btn-delete { background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-weight: bold; }
            .btn-add { background: #007bff; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; }
            input[type="text"], input[type="email"] { width: 100%; padding: 6px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
            .add-box { background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #ddd; margin-top: 25px; }
            .form-row { display: flex; gap: 15px; margin-bottom: 10px; }
            .form-col { flex: 1; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="{{ url_for('index') }}" class="btn-back">← Powrót do panelu głównego</a>
            <h2>Zarządzanie bazą osób (baza.json)</h2>
            
            {% if not baza %}
                <p>Brak wpisów w pliku baza.json.</p>
            {% else %}
                <table>
                    <thead>
                        <tr>
                            <th>Imię i Nazwisko</th>
                            <th>Adres E-mail</th>
                            <th style="width: 160px; text-align: center;">Akcje</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for name, email in baza.items() %}
                        <tr>
                            <form action="/update-osoba" method="POST">
                                <input type="hidden" name="old_name" value="{{ name }}">
                                <td>
                                    <input type="text" name="new_name" value="{{ name }}" required>
                                </td>
                                <td>
                                    <input type="email" name="new_email" value="{{ email }}" required>
                                </td>
                                <td style="text-align: center; white-space: nowrap;">
                                    <button type="submit" name="action" value="save" class="btn-save">Zapisz</button>
                                    <button type="submit" name="action" value="delete" class="btn-delete" onclick="return confirm('Czy na pewno chcesz usunąć {{ name }}?');">Usuń</button>
                                </td>
                            </form>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            {% endif %}

            <div class="add-box">
                <h3>Dodaj nową osobę do bazy</h3>
                <form action="/add-osoba" method="POST">
                    <div class="form-row">
                        <div class="form-col">
                            <label><b>Imię i Nazwisko:</b></label>
                            <input type="text" name="name" placeholder="np. JAN KOWALSKI" required>
                        </div>
                        <div class="form-col">
                            <label><b>Adres E-mail:</b></label>
                            <input type="email" name="email" placeholder="np. jan@domena.com" required>
                        </div>
                    </div>
                    <button type="submit" class="btn-add">➕ Dodaj osobę</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(template, baza=baza)

@app.route('/update-osoba', methods=['POST'])
def update_osoba():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name').strip().upper()
    new_email = request.form.get('new_email').strip()
    action = request.form.get('action')

    baza = load_baza_emails()

    if action == 'delete':
        if old_name in baza:
            del baza[old_name]
    elif action == 'save':
        if old_name in baza and old_name != new_name:
            del baza[old_name]
        baza[new_name] = new_email

    save_baza_emails(baza)
    return redirect(url_for('lista_osob'))

@app.route('/add-osoba', methods=['POST'])
def add_osoba():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    name = request.form.get('name').strip().upper()
    email = request.form.get('email').strip()

    if name and email:
        baza = load_baza_emails()
        baza[name] = email
        save_baza_emails(baza)

    return redirect(url_for('lista_osob'))

@app.route('/ustawienia')
def ustawienia():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    template = """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Ustawienia - Panel Skrytki</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 30px; background: #eef2f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            h2 { color: #2c3e50; margin-top: 0; }
            .btn-back { display: inline-block; background: #6c757d; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; margin-bottom: 20px; font-weight: bold; }
            .btn-back:hover { background: #5a6268; }
            .setting-item { margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; border: 1px solid #ddd; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="{{ url_for('index') }}" class="btn-back">← Powrót do panelu głównego</a>
            <h2>Ustawienia systemu</h2>
            <div class="setting-item">
                <p><b>Serwer SMTP:</b> smtp.gmail.com (Port: 587)</p>
                <p><b>Konto wysyłki:</b> projektai2137@gmail.com</p>
                <p><b>Katalog testowy zdjęć:</b> DataSet1/test</p>
            </div>
            <p style="color: #666; font-size: 14px;">Wszystkie główne ustawienia mapowania oraz kluczy API są wczytywane bezpośrednio z plików konfiguracyjnych na serwerze (`baza.json`, `KEY.json`).</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(template)

@app.route('/scan', methods=['POST'])
def scan_files():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    scan_all = request.form.get('scan_all')
    selected_file = request.form.get('selected_file')

    if scan_all == 'true':
        for f in get_available_jpg_files():
            process_single_image(f['filename'])
    elif selected_file:
        process_single_image(selected_file)

    return redirect(url_for('index'))

@app.route('/delete-file', methods=['POST'])
def delete_file():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    selected_file = request.form.get('selected_file')
    if selected_file:
        safe_filename = os.path.basename(selected_file)
        file_path = os.path.join(TEST_DIR, safe_filename)
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                os.remove(file_path)
                print(f"[LOG FILE] Usunięto plik z dysku: {safe_filename}")
            except Exception as e:
                print(f"[LOG FILE ERROR] Nie udało się usunąć pliku {safe_filename}: {e}")
                
    return redirect(url_for('index'))

@app.route('/action', methods=['POST'])
def handle_action():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    item_id = int(request.form.get('item_id'))
    action = request.form.get('btn_action')
    email = request.form.get('email')
    body = request.form.get('body')

    for item in pending_emails:
        if item['id'] == item_id:
            if action == 'send':
                success = send_email(email, "Wiadomość ze skrytki - Twój dokument", body)
                if success:
                    sent_item = item.copy()
                    sent_item['sent_date'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                    sent_history.insert(0, sent_item)
                    pending_emails.remove(item)
                    
                    save_json_file(PENDING_FILE, pending_emails)
                    save_json_file(HISTORY_FILE, sent_history)
            elif action == 'delete':
                pending_emails.remove(item)
                save_json_file(PENDING_FILE, pending_emails)
            break

    return redirect(url_for('index'))

@app.route('/history-action', methods=['POST'])
def handle_history_action():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    history_id = int(request.form.get('history_id'))
    action = request.form.get('action')

    for h_item in sent_history:
        if h_item['id'] == history_id:
            if action == 'resend':
                success = send_email(h_item['email'], "Wiadomość ze skrytki - Twój dokument (Ponownie)", h_item['body'])
                if success:
                    h_item['sent_date'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                    save_json_file(HISTORY_FILE, sent_history)
            elif action == 'delete':
                sent_history.remove(h_item)
                save_json_file(HISTORY_FILE, sent_history)
            break

    return redirect(url_for('index'))

@app.route('/clear-history', methods=['POST'])
def clear_history():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    global sent_history
    sent_history.clear()
    save_json_file(HISTORY_FILE, sent_history)
    print("[LOG HISTORY] Wyczyszczono całą historię wysłanych e-maili.")
    return redirect(url_for('index'))

@app.route('/test-images/<path:filename>')
def get_test_image(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return send_from_directory(TEST_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)