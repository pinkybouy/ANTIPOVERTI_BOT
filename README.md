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

## 🚀 Jak uruchomić?

1.  **Dane**: Uruchom `Harvester/Uruchom.bat` aby zacząć zbierać dane.
2.  **Analiza**: Uruchom `Engine/ai_core/main.py` (lub skrypt startowy), aby aktywować silnik sygnałów.
3.  **Trading**: Załaduj `ANTIPOVERTI_BOT` w cTrader Automate i połącz się z lokalnym Engine (port 5555).

## 🛡 Bezpieczeństwo
System posiada wbudowane mechanizmy zabezpieczające kapitał (Circuit Breakers), które automatycznie przerywają handel po osiągnięciu limitów strat lub serii niepowodzeń.

---
*Projekt rozwijany pod kątem ultra-niskich opóźnień i precyzyjnej analizy Order Flow.*
