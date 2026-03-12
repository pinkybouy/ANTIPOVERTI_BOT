from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import uvicorn
import asyncio
import os
import urllib.request
import xml.etree.ElementTree as ET
import subprocess

from storage import DataStorage
from harvester import BinanceHarvester
import config

app = FastAPI(title="Binance Ticket Harvester")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR

# Setup folderów do UI
static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Inicjalizacja komponentów
storage = DataStorage(base_dir=os.path.join(EXE_DIR, config.STORAGE_DIR))
# Konfigurujemy domyślne pary oraz strumienie zlecane przez usera
# trade: Ticki (pojedyncze transakcje z dokładnością do ms i wolumenem)
# diff.Depth@100ms: Zmiany arkusza (Order Book) co 100 milisekund
# bookTicker: Najlepsza oferta kupna/sprzedaży w czasie rzeczywistym
harvester = BinanceHarvester(storage, pairs=config.BINANCE_PAIRS, streams=config.BINANCE_STREAMS)

async def watcher_task():
    while True:
        await asyncio.sleep(60)
        # Check if it is NOT running
        if not getattr(harvester, "running", False):
            try:
                ps_script = """
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $template = "<toast><visual><binding template='ToastText02'><text id='1'>Binance Harvester</text><text id='2'>OSTRZEŻENIE: Zbieranie danych na żywo jest aktualnie WYŁĄCZONE!</text></binding></visual></toast>"
                $xml.LoadXml($template)
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('TickHarvester').Show($toast)
                """
                subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print(f"Powiadomienie fail: {e}")

@app.on_event("startup")
async def startup_event():
    print("Inicjalizacja systemu. Serwer gotowy.")
    storage.start()
    asyncio.create_task(watcher_task())
    harvester.start() # automatyczny start przy uruchomieniu programu

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(BASE_DIR, "static", "index.html"), "r", encoding="utf-8") as f:
         return f.read()

@app.get("/api/start")
async def start_harvester():
    harvester.start()
    return {"status": "started"}

@app.get("/api/stop")
async def stop_harvester():
    harvester.stop()
    return {"status": "stopped"}

@app.get("/api/stats")
async def get_stats():
    return {
        "harvester": harvester.get_stats(),
        "storage": storage.get_stats()
    }

@app.get("/api/news")
async def get_news(filter: str = "bullish"):
    url = "https://cryptopanic.com/news/rss/bitcoin/"
    
    if filter and filter not in ["all", "global-political"]:
         url += f"?filter={filter}"
         
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text if item.find('title') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ''
            
            if filter == "global-political":
                keywords = ["macro", "politic", "sec", "regulation", "government", "fed", "fomc", "rate", "war", "election", "biden", "trump", "powell"]
                if not any(k in title.lower() for k in keywords):
                    continue

            items.append({
                "title": title,
                "link": link,
                "pubDate": pubDate
            })
            if len(items) >= 15:
                break
        return {"items": items}
    except Exception as e:
        print(f"Błąd parsera RSS: {e}")
        return {"items": []}

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    is_frozen = getattr(sys, 'frozen', False)
    uvicorn.run("main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=not is_frozen)
