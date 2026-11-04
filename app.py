import os
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, flash
import cv2
import google.generativeai as genai

# ==========================================
# 1. KONFIGURACJA GEMINI API & SKŁADU PLIKÓW
# ==========================================
GEMINI_API_KEY = "TWÓJ_KLUCZ_GEMINI_API"  # Podmień na swój klucz API
genai.configure(api_key=GEMINI_API_KEY)

IMAGE_PATH = "/tmp/foto.jpg"

# Podręczna pamięć na ostatni wynik analizy
latest_result = {
    "text": "Brak wykonanego zdjęcia. Wciśnij przycisk na płytce.",
    "email": ""
}

# ==========================================
# 2. KONFIGURACJA SMTP (WYSYŁKA POCZTY)
# ==========================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "wiktor.matusik2000@gmail.com"        # Twój adres e-mail
SMTP_PASSWORD = "rqgf haak molr ozjp"   # 16-znakowe hasło aplikacji

def send_email(recipient_email, subject, body_text):
    """Wysyła wiadomość e-mail z analizą Gemini przez serwer SMTP"""
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
        print(f"[LOG SMTP ERROR] Błąd wysyłki e-mail: {e}")
        return False

# ==========================================
# 3. OBSŁUGA KAMERY I GEMINI AI
# ==========================================
def capture_image():
    """Robi zdjęcie kamerą USB przez OpenCV (odczyt z /dev/video1)"""
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    for _ in range(3):
        ret, frame = cap.read()

    cap.release()

    if ret:
        cv2.imwrite(IMAGE_PATH, frame)
        print(f"[LOG] Zdjęcie zapisane w {IMAGE_PATH}")
        return True
    else:
        print("[LOG ERROR] Błąd przechwytywania klatki z kamery!")
        return False

def analyze_with_gemini():
    """Wysyła zdjęcie do Gemini i wyciąga tekst oraz ew. adres email"""
    global latest_result
    if not os.path.exists(IMAGE_PATH):
        return

    print("[LOG] Wysyłanie zdjęcia do Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Wczytanie pliku obrazu
        with open(IMAGE_PATH, 'rb') as f:
            image_data = f.read()

        cookie_picture = {
            'mime_type': 'image/jpeg',
            'data': image_data
        }

        prompt = (
            "Przeanalizuj to zdjęcie (wizytówka lub dokument). Odczytaj cały tekst. "
            "Jeśli na zdjęciu znajduje się adres e-mail, wypisz go na samym końcu w osobnej linii w formacie: EMAIL: adres@email.com"
        )

        response = model.generate_content([prompt, cookie_picture])
        text_response = response.text
        print(f"[LOG Gemini]: {text_response}")

        # Wyciąganie adresu email z odpowiedzi
        extracted_email = ""
        for line in text_response.splitlines():
            if "EMAIL:" in line:
                extracted_email = line.split("EMAIL:")[1].strip()

        latest_result["text"] = text_response
        latest_result["email"] = extracted_email

    except Exception as e:
        print(f"[LOG ERROR Gemini]: {e}")
        latest_result["text"] = f"Błąd analizy Gemini: {e}"

# ==========================================
# 4. OBSŁUGA PRZYCISKU GPIO (gpiod v2)
# ==========================================
def listen_button():
    """Wątek tła nasłuchujący wciśnięcia przycisku GPIO 17"""
    try:
        import gpiod
        chip = gpiod.Chip('gpiochip1')  # Weryfikuj numer układu na Banana Pi
        line = chip.get_line(17)
        line.request(consumer="button_app", type=gpiod.LINE_REQ_EV_FALLING_EDGE)

        print("[LOG GPIO] Nasłuchiwanie przycisku aktywne...")
        while True:
            if line.event_wait(1):
                event = line.event_read()
                print("[LOG GPIO] Wykryto kliknięcie przycisku!")
                if capture_image():
                    analyze_with_gemini()
    except Exception as e:
        print(f"[LOG GPIO ERROR] Nie udało się zainicjować gpiod: {e}")

# Uruchomienie nasłuchu przycisku w osobnym wątku
threading.Thread(target=listen_button, daemon=True).start()

# ==========================================
# 5. APLIKACJA FLASK (SERWER WWW)
# ==========================================
app = Flask(__name__)
app.secret_key = "projekt_secret_key"

@app.route('/')
def index():
    return f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Panel AI - Banana Pi</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f4f4f9; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            textarea {{ width: 100%; height: 150px; margin-bottom: 10px; }}
            input[type="email"] {{ width: 300px; padding: 8px; }}
            button {{ padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Ostatnia analiza wizytówki / dokumentu</h2>
            <form action="/send-mail" method="POST">
                <label>Wynik z Gemini AI:</label><br>
                <textarea name="result_text">{latest_result['text']}</textarea><br><br>
                
                <label>Adres e-mail odbiorcy:</label><br>
                <input type="email" name="email" value="{latest_result['email']}" required placeholder="email@domena.com">
                <button type="submit">Wyślij E-mail</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/send-mail', methods=['POST'])
def handle_send_mail():
    email = request.form.get('email')
    result_text = request.form.get('result_text')
    
    if email and result_text:
        success = send_email(email, "Weryfikacja dokumentu / Wizytówki (Gemini AI)", result_text)
        if success:
            return "<h1>E-mail wysłany pomyślnie!</h1><br><a href='/'>Wróć do panelu</a>"
    return "<h1>Błąd wysyłki e-maila.</h1><br><a href='/'>Spróbuj ponownie</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
