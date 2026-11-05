# Audyt Projektu "Oczko"

### 1. PROBLEM I WARTOSCI

Projekt dobrze definiuje realny problem automatyzacji korespondencji, dostarczając jasną wartość użytkową w postaci skrócenia czasu przetwarzania dokumentów przy zachowaniu kontroli człowieka.

### 2. AI

Wykorzystanie multimodalnego modelu Google Gemini do zadania OCR i ekstrakcji danych jest trafne, a zastosowany fallback dla modeli zwiększa niezawodność interakcji z API.

### 3. KOD

Kod aplikacji w języku Python jest zwięzły i czytelny, jednak przechowywanie poświadczeń SMTP bezpośrednio w kodzie źródłowym stanowi poważne uchybienie w zakresie bezpieczeństwa.

### 4. JAKOSC WYNIKOW

Jakość ekstrakcji imion i nazwisk zależy bezpośrednio od czytelności zdjęć oraz precyzji promptu, co przy braku dodatkowej walidacji tekstowej może prowadzić do błędów dopasowania w bazie.

### 5. DANE

Struktura mapowania w pliku `baza.json` jest prosta i skrajnie podatna na błędy wynikające z literówek lub braku elastycznego dopasowywania (fuzzy matching) odczytanych personaliów.

### 6. UX I WIZUALIZACJA

Interfejs webowy Flask jest czysty i funkcjonalny dla operatora, lecz brakuje w nim podglądu skanowanego obrazu oraz dynamicznych powiadomień bez przeładowania strony (AJAX/WebSockets).

### 7. DOKUMENTACJA

Mimo przejrzystego schematu w opisie, instrukcja i sam proces uruchomienia są nieintuicyjne oraz generują błędy podczas próby odpalenia aplikacji (np. rozbieżności w nazwach plików startupowych i konfiguracji).

### 8. ETYKA I RYZYKA

Zastosowanie podejścia "Human-in-the-loop" skutecznie minimalizuje ryzyko pomyłkowej wysyłki e-maila, jednak przechowywanie kluczy API oraz haseł pocztowych w otwartym tekście rodzi ryzyko wycieku danych.


### CO ZAOBSERWOWALIŚMY
1. Błąd: Brak moliwości odpalenia aplikacji.
2. Co nalezy: Wyeksporotwać aplikację do pliku wykonywalnego.
3. Priorytet: Wysoki

