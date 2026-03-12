import sys
import json
import urllib.request
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

class MiniDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000) # Co sekundę pobiera dane

    def initUI(self):
        # Konfiguracja okna (Always on top, bez ramki, przezroczyste tło)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(5)
        
        # Styl samego kafelka (Glassmorphism)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 210);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 12px;
                color: #f8fafc;
            }
        """)

        # Tytuł i status
        self.title = QLabel("📡 Harvester: Łączenie...")
        self.title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        
        self.btc_price = QLabel("$ ---")
        self.btc_price.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.btc_price.setStyleSheet("color: #34d399; border: none; background: transparent;")
        
        self.stats_info = QLabel("Zapisane: 0 | Bufor: 0")
        self.stats_info.setFont(QFont("Segoe UI", 9))
        self.stats_info.setStyleSheet("color: #cbd5e1; border: none; background: transparent;")

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.btc_price)
        self.layout.addWidget(self.stats_info)
        
        self.setLayout(self.layout)
        
        self.resize(220, 100)
        
        # Umiejscowienie w prawym dolnym rogu (dopasowanie do rozdzielczości)
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.width() - self.width() - 20
        y = screen_geometry.height() - self.height() - 20
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.dragPos)
            self.dragPos = event.globalPosition().toPoint()
            event.accept()

    def update_stats(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/stats")
            with urllib.request.urlopen(req, timeout=1) as response:
                data = json.loads(response.read().decode())
                
                status = data['harvester']['status']
                if status == 'Running':
                    self.title.setText("🟢 Zbieranie Aktywne")
                else:
                    self.title.setText("🔴 Wstrzymano")

                prices = data['harvester'].get('current_prices', {})
                btc = prices.get('BTCUSDT', '---')
                if btc != '---':
                    self.btc_price.setText(f"$ {float(btc):.2f}")

                saved = data['storage']['total_saved_count']
                buff_dict = data['storage']['buffer_sizes']
                queued = sum(buff_dict.values())
                
                self.stats_info.setText(f"Rekordów: {saved:,}\nW RAM: {queued}")
                
        except Exception:
            self.title.setText("⚪ Serwer Offline")
            self.btc_price.setText("---")
            self.stats_info.setText("Brak połączenia na porcie 8000")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MiniDashboard()
    ex.show()
    sys.exit(app.exec())
