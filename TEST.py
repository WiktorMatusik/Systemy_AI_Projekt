import os
import cv2
import json
import time
import warnings
warnings.filterwarnings("ignore")

from google import genai
from google.genai import types

# 1. Wczytanie klucza API z pliku KEY.json
key_file_path = 'KEY.json'

if not os.path.exists(key_file_path):
    print(f"BŁĄD: Nie znaleziono pliku '{key_file_path}' w bieżącym folderze!")
    exit(1)

try:
    with open(key_file_path, 'r', encoding='utf-8') as f:
        key_data = json.load(f)
        API_KEY = key_data.get("api_key")

    if not API_KEY or API_KEY == "AIzaSyTwojPrawidlowyKluczTutaj...":
        print("BŁĄD: Plik 'KEY.json' nie zawiera poprawnego klucza API!")
        exit(1)
except Exception as e:
    print(f"BŁĄD podczas odczytywania pliku '{key_file_path}': {e}")
    exit(1)

# Inicjalizacja klienta z wczytanym kluczem
client = genai.Client(api_key=API_KEY)

# 2. Baza odbiorców (Słownik mapujący Osoba -> Adres E-mail)
EMAIL_DIRECTORY = {
    "JAN KOWALSKI": "jan.kowalski@example.com",
    "ANNA NOWAK": "anna.nowak@example.com",
    # Dodaj kolejne osoby według potrzeb
}

DEFAULT_EMAIL = "twoj_testowy_email@gmail.com"

# Ścieżka do folderu ze zdjęciami testowymi (DataSet1/test)
input_folder = './DataSet1/test'
output_folder = './Results'
report_file = os.path.join(output_folder, 'raport_api_gemini.txt')

os.makedirs(output_folder, exist_ok=True)

if not os.path.exists(input_folder):
    print(f"BŁĄD: Katalog '{input_folder}' nie istnieje!")
    exit(1)

pliki = [f for f in os.listdir(input_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]

# Twoje modele
MODELE = ['gemini-3.1-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash']

PROMPT_IMIE_NAZWISKO = (
    "Przeanalizuj to zdjęcie (wizytówkę lub dokument). Znajdź imię i nazwisko głównej osoby. "
    "Zwróć TYLKO imię i nazwisko wielkimi literami w jednej linii (np. JAN KOWALSKI). "
    "Nie dodawaj żadnych innych słów, znaków interpunkcyjnych ani dodatkowego formatowania."
)

def wywolaj_api_z_retry(image_bytes, prompt):
    for model_name in MODELE:
        for probo in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type='image/jpeg',
                        ),
                        prompt,
                    ]
                )
                return response.text.strip(), model_name
            except Exception as e:
                err_msg = str(e)
                if '503' in err_msg or 'UNAVAILABLE' in err_msg or '429' in err_msg:
                    print(f" (503/błąd na {model_name}, ponawiam za 2s...)", end="", flush=True)
                    time.sleep(2)
                else:
                    raise e
    raise Exception("Wszystkie próby i modele zawiodły.")

if not pliki:
    print(f"Brak plików w folderze '{input_folder}'!")
else:
    print(f"Pomyślnie wczytano klucz API z '{key_file_path}'.")
    print(f"Znaleziono {len(pliki)} plików w '{input_folder}'. Startuję wysyłkę...\n")

    with open(report_file, 'w', encoding='utf-8') as txt:
        txt.write("=== RAPORT GEMINI API & WYBÓR E-MAIL ===\n\n")

        for index, nazwa_pliku in enumerate(pliki, start=1):
            print(f"[{index}/{len(pliki)}] Przygotowuję: {nazwa_pliku}...", end="", flush=True)
            
            sciezka = os.path.join(input_folder, nazwa_pliku)
            img = cv2.imread(sciezka)
            if img is None:
                print(" -> Błąd wczytywania pliku!")
                continue

            h, w = img.shape[:2]
            if w > 1600:
                skala = 1600.0 / w
                img_small = cv2.resize(img, (1600, int(h * skala)), interpolation=cv2.INTER_AREA)
            else:
                img_small = img.copy()

            _, buffer = cv2.imencode('.jpg', img_small, [int(cv2.IMWRITE_JPEG_QUALITY), 85])

            print(" Wysyłam do API...", end="", flush=True)
            t0 = time.time()

            try:
                wynik_tekst, uzyty_model = wywolaj_api_z_retry(buffer.tobytes(), PROMPT_IMIE_NAZWISKO)
                czas = time.time() - t0

                # Czyszczenie tekstu zwracanego przez Gemini
                odczytana_osoba = wynik_tekst.upper().strip()

                # Dopasowanie e-maila z bazy EMAIL_DIRECTORY
                target_email = EMAIL_DIRECTORY.get(odczytana_osoba, DEFAULT_EMAIL)
                tresc_wiadomosci = f"Cześć {odczytana_osoba.title()}, w skrytce czeka Twój dokument."

                txt.write(f"Plik: {nazwa_pliku} (Czas: {czas:.2f}s | Model: {uzyty_model})\n")
                txt.write(f"  Odczytano: {odczytana_osoba}\n")
                txt.write(f"  Wybrany mail: {target_email}\n")
                txt.write(f"  Powiadomienie: {tresc_wiadomosci}\n")
                txt.write("-" * 60 + "\n")

                print(f" -> GOTOWE w {czas:.2f}s ({uzyty_model})! Match: {odczytana_osoba} -> {target_email}")

            except Exception as e:
                print(f" -> BŁĄD API: {e}")
                txt.write(f"Plik: {nazwa_pliku}\nBŁĄD: {e}\n" + "-" * 60 + "\n")

    print(f"\nKoniec! Wyniki analizy oraz dopasowane maile znajdziesz w: '{report_file}'")
