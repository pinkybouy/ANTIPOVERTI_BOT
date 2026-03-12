# ANTIPOVERTI HFT Ecosystem (Bot & Engine)

System do analizy mikrostruktury rynku (HFT Engine) oraz zautomatyzowanego tradingu na platformie cTrader.

## 🏗 Struktura
Projekt integruje silnik analizy z egzekucją zleceń:

### 1. [Engine](./Engine/) (HFT Analysis Core)
*   **Core (Rust)**: Przetwarzanie Order Book, obliczanie OBI w czasie rzeczywistym.
*   **AI/Logic (Python)**: Analiza trendów, News Engine i logika decyzyjna.
*   **Dashboard**: UI (localhost:8080) wizualizujący sygnały i metryki rynkowe.

### 2. [ANTIPOVERTI_BOT](./ANTIPOVERTI_BOT/) (cTrader Robot)
*   **Egzekucja**: Robot C# odbierający sygnały z Engine przez TCP.
*   **Zabezpieczenia**: System Circuit Breaker i ochrona kapitału.

## 🚀 Uruchomienie
1. Skopiuj `.env.example` do `.env`.
2. Uzupełnij `GITHUB_TOKEN` i parametry Engine.
3. Uruchom `Engine/ai_core/main.py` oraz załaduj bota w cTrader Automate.

*Uwaga: Moduł do zbierania danych (Harvester) znajduje się w osobnym repozytorium.*
