# ANTIPOVERTI HFT Ecosystem

Kompleksowy system do zbierania danych (Tick Harvesting), analizy mikrostruktury rynku (HFT Engine) oraz zautomatyzowanego tradingu na platformie cTrader.

## 🏗 Struktura Projektu

Projekt podzielony jest na trzy główne moduły, które współpracują ze sobą w czasie rzeczywistym:

### 1. [Harvester](./Harvester/) (Binance Tick Scraper)
*   **Cel**: Wysokowydajne gromadzenie danych tickowych (transakcje, arkusz zleceń, bookTicker) z giełdy Binance.
*   **Technologia**: Python (FastAPI, WebSockets, aiofiles).
*   **Kluczowe funkcje**:
    *   Buforowanie zapisu do plików JSONL (oszczędność dysku/CPU).
    *   Lokalny UI (Dashboard) do monitorowania prędkości zapisu i stanu buforów.
    *   System logowania błędów i automatycznego restartu.

### 2. [Engine](./Engine/) (HFT Analysis Core)
*   **Cel**: Przetwarzanie danych rynkowych i generowanie sygnałów transakcyjnych w milisekundach.
*   **Architektura Hybrydowa**:
    *   **Core (Rust)**: Krytyczna wydajność (przetwarzanie Order Book, obliczanie OBI).
    *   **AI/Logic (Python)**: Analiza trendów, News Engine (RSS), Decision Logic.
*   **Dashboard**: Zaawansowany UI (localhost:8080) wizualizujący OBI, ściany zleceń (Walls), oraz sugerowane sygnały AI.

### 3. [ANTIPOVERTI_BOT](./ANTIPOVERTI_BOT/) (cTrader Robot)
*   **Cel**: Egzekucja zleceń na giełdzie/u brokera.
*   **Technologia**: C# (.NET).
*   **Kluczowe funkcje**:
    *   Łączność TCP z Engine w celu odbierania sygnałów.
    *   Wbudowany system Capital Protection (Daily Loss Limit, Max Drawdown).
    *   Panel kontrolny na wykresie z przyciskami **ON/OFF** dla bota i silnika analizy.

---

## 🚀 Uruchomienie i Konfiguracja

### 1. Konfiguracja Środowiska
System używa zmiennych środowiskowych do zarządzania danymi wrażliwymi (np. tokeny API) i ustawieniami portów.
1.  Skopiuj plik `.env.example` do nowego pliku `.env`.
2.  Uzupełnij `GITHUB_TOKEN` oraz inne parametry według potrzeb.
3.  Plik `.env` jest automatycznie ignorowany przez Git dla Twojego bezpieczeństwa.

### 2. Szybki Start
W głównym katalogu znajduje się skrypt `START_PROJECT.bat`, który automatycznie uruchamia wszystkie moduły Python w osobnych oknach terminala.

1.  Uruchom `START_PROJECT.bat`.
2.  Załaduj bota `ANTIPOVERTI_BOT` w cTrader.

## 🛡 Bezpieczeństwo
System posiada wbudowane mechanizmy zabezpieczające kapitał (Circuit Breakers), które automatycznie przerywają handel po osiągnięciu limitów strat lub serii niepowodzeń. Wszystkie klucze API powinny znajdować się wyłącznie w pliku `.env`.

---
*Projekt rozwijany pod kątem ultra-niskich opóźnień i precyzyjnej analizy Order Flow.*
