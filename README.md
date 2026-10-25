# Oczko – Inteligentna Szafka na Listy i Dokumenty

Projekt autonomicznego systemu wbudowanego do automatycznego wykrywania, cyfrowego odczytu (OCR), klasyfikacji dokumentów oraz przygotowywania powiadomień e-mail. System przeznaczony jest do usprawnienia obiegu korespondencji (np. w dziekanacie lub biurze).

---

## 1. Opis projektu

**Oczko** to inteligentna skrytka na korespondencję. Użytkownik umieszcza dokument w strefie skanowania i naciska fizyczny przycisk aktywacji. Banana Pi wykonuje zdjęcie, optymalizuje obraz na urządzeniu brzegowym (*Edge Device*), a następnie przekazuje go do chmurowego modelu wizyjnego **Google Gemini API**. 

System odczytuje treść tekstu, identyfikuje adresata i klasyfikuje typ dokumentu. Na podstawie rozpoznanego odbiorcy system zapala odpowiednią **diodę LED** wskazującą właściwą skrytkę docelową oraz generuje gotowy projekt/szablon wiadomości e-mail. Wysłanie powiadomienia wymaga ręcznego zatwierdzenia przez operatora, co chroni przed błędną dystrybucją korespondencji w przypadku ewentualnych pomyłek modelu AI.

---

## 2. Cele projektu

- **Interaktywna weryfikacja:** Manualne wyzwalanie procesu skanowania przyciskiem i fizyczna sygnalizacja LED.
- **Rozpoznawanie i klasyfikacja AI:** Przetwarzanie dokumentów za pomocą multimodalnego modelu AI (wyznaczenie adresata i typu pisma).
- **Wsparcie operatora (Human-in-the-loop):** Generowanie gotowego szablonu e-mail do ręcznej weryfikacji i zatwierdzenia przed wysyłką.
- **Eliminacja błędów:** Ochrona przed automatycznym wysłaniem błędnych powiadomień.
- **Oszczędność czasu:** Automatyzacja czytania i przygotowywania treści korespondencji przy zachowaniu pełnej kontroli.

---

## 3. Architektura i Schemat Działania

System działa w architekturze **Edge Processing + AI Cloud Service**:

```
[ Umieszczenie dokumentu & Przycisk GPIO ]
                   │
                   ▼
[ Camera / OpenCV ] ──► Resizing (max 1600px) & Kompresja JPG (Banana Pi)
                   │
                   ▼
[ HTTPS Request ]   ──► Google Gemini API (gemini-3.1-flash-lite / 3.8-flash)
                   │
                   ▼
[ Wynik OCR & JSON ] ──► Identyfikacja adresata, typu i treści
                   │
                   ├───────────────────────────────┐
                   ▼                               ▼
[ GPIO Driver / Dioda LED ]        [ Generator Szablonu Maila ]
Zapala się dioda właściwej         Tworzy gotowy projekt wiadomości 
skrytki odbiorcy                   do ręcznego zatwierdzenia przez operatora
```

---

## 4. Wymagania i Sprzęt

### Sprzęt (Hardware)
- **Jednostka centralna:** Banana Pi M2 Zero (512 MB RAM)
- **Moduł optyczny:** Kamera USB / moduł kamery dedykowany
- **Akcesoria GPIO:**
  - Przycisk fizyczny (TACT Switch) – wyzwalanie skanowania
  - Diody LED (różne kolory / przypisane do skrytek adresatów)
  - Rezystory (220Ω / 330Ω) i przewody połączeniowe
- **Zasilanie i pamięć:** Zasilacz 5V, karta MicroSD (min. 16 GB), konwerter OTG USB

### Oprogramowanie (Software)
- Python 3.10+
- Pakiety z `requirements.txt`:
  * `google-genai`
  * `opencv-python`
  * `numpy`
  * `RPi.GPIO` / `WiringPi` (lub dedykowana biblioteka GPIO dla Banana Pi)

---

## 5. Instalacja i Konfiguracja

### 1. Klonowanie repozytorium
```bash
git clone https://github.com/TWOJA_NAZWA_UZYTKOWNIKA/Projekt_Systemy_AI.git
cd Projekt_Systemy_AI
```

### 2. Instalacja zależności
```bash
pip install -r requirements.txt
```

### 3. Konfiguracja klucza API i szablonu poczty (`KEY.json`)
Utwórz plik `KEY.json` w głównym katalogu projektu:

```json
{
  "api_key": "AIzaSy_TWÓJ_KLUCZ_GEMINI_API",
  "email_sender": "twoja_poczta@gmail.com",
  "default_receiver": "odbiorca_powiadomien@gmail.com"
}
```

> **Ważne:** Plik `KEY.json` znajduje się w `.gitignore` i **nie powinien** być nigdy wysyłany do publicznego repozytorium!

---

## 6. Uruchomienie

Aby uruchomić system w trybie ciągłego nasłuchu na przycisk GPIO:

```bash
python TEST.py
```

Wyjściowe pliki tekstowe, wygenerowane projekty e-mail (`.eml` / `.txt`) oraz przetworzone skany zostaną zapisane w katalogu `./Results`. Po rozpoznaniu dokumentu włączy się odpowiednia dioda LED, a przygotowany mail będzie czekał na zatwierdzenie przez operatora.

---

## 7. Wymagania Funkcjonalne i Niefunkcjonalne

### Funkcjonalne
- Obsługa przycisku fizycznego GPIO do wyzwalania zdjęcia z kamery.
- Wstępna obróbka i przeskalowanie obrazu do optymalnej rozdzielczości (1600px).
- Odczyt tekstu (OCR) i identyfikacja adresata przez model **Gemini Flash**.
- Sygnalizacja świetlna (LED) odpowiedniej skrytki docelowej na podstawie wyniku AI.
- Generowanie gotowego szkicu wiadomości e-mail do ręcznego zatwierdzenia/wysłania.
- Mechanizm automatycznego ponawiania prób (*retry 503 / fallback*) przy obciążeniu API.

### Niefunkcjonalne
- **Bezpieczeństwo procesu:** Brak automatycznej wysyłki zapobiega błędom w doręczeniu korespondencji.
- **Niska latencja:** Czas od naciśnięcia przycisku do zapalenia diody LED wynosi ok. 1-3 sekundy.
- **Lekkość:** Znikome zużycie RAM-u na Banana Pi (<100 MB).
- **Niezawodność:** Sprzętowa sygnalizacja informuje operatora o statusie i wybranej skrytce.

---

## 8. Technologie

- **Python 3** – Główna logika systemu.
- **GPIO (Banana Pi)** – Obsługa fizycznego przycisku i diod LED.
- **OpenCV** – Przetwarzanie obrazu z kamery.
- **Google Gemini API (`google-genai`)** – Multimodalny model AI do analizy i ekstrakcji adresata.
- **Git & GitHub** – Kontrola wersji.

---

## 9. Twórcy Projektu

- **Wiktor Matusik**
- **Damian Basta**
- **Mateusz Kowalczyk**
- **Serafym Bokii**

---

## 10. Licencja

Projekt realizowany w ramach celów akademickich. Licencja open-source (MIT).