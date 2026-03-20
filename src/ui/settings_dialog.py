"""
SettingsDialog - Diálogo de configurações do Ross PDF Editor.
Permite configurar o scanner preferido e outras opções.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QSettings, QSize
from src.engine.scan_engine import ScannerEngine

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner_engine = ScannerEngine()
        self.settings = QSettings("Ross", "RossPDFEditor")
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        self.setWindowTitle("Configurações")
        self.setFixedSize(450, 300)
        self.setStyleSheet("""
            QDialog { background-color: #1a1b2e; color: #e0e0e8; }
            QLabel { color: #e0e0e8; font-size: 14px; }
            QPushButton { 
                background-color: #2d2f5a; 
                border-radius: 6px; 
                padding: 8px 16px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3d5afe; }
            QComboBox {
                background-color: #12132a;
                border: 1px solid #3a3b6a;
                border-radius: 6px;
                padding: 6px;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Título
        title = QLabel("⚙️ Configurações de Scanner")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4FC3F7;")
        layout.addWidget(title)

        # Seçào Scanner
        scanner_layout = QVBoxLayout()
        scanner_layout.setSpacing(8)
        
        lbl_info = QLabel("Selecione seu scanner padrão:")
        lbl_info.setStyleSheet("font-size: 12px; color: #78909C;")
        scanner_layout.addWidget(lbl_info)

        self.cb_scanners = QComboBox()
        scanner_layout.addWidget(self.cb_scanners)
        
        btn_refresh = QPushButton("🔄 Atualizar Lista")
        btn_refresh.setFixedWidth(140)
        btn_refresh.clicked.connect(self._refresh_scanners)
        scanner_layout.addWidget(btn_refresh)

        layout.addLayout(scanner_layout)
        layout.addStretch()

        # Botões de Ação
        actions = QHBoxLayout()
        self.btn_save = QPushButton("💾 Salvar")
        self.btn_save.setStyleSheet("background-color: #2E7D32;")
        self.btn_save.clicked.connect(self._save_and_close)
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        
        actions.addStretch()
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_save)
        layout.addLayout(actions)

    def _refresh_scanners(self):
        """Busca scanners e atualiza o combobox."""
        current = self.cb_scanners.currentText()
        self.cb_scanners.clear()
        
        scanners = self.scanner_engine.list_scanners()
        if not scanners:
            self.cb_scanners.addItem("Nenhum scanner detectado")
            self.cb_scanners.setEnabled(False)
        else:
            self.cb_scanners.addItems(scanners)
            self.cb_scanners.setEnabled(True)
            index = self.cb_scanners.findText(current)
            if index >= 0:
                self.cb_scanners.setCurrentIndex(index)

    def _load_settings(self):
        """Carrega o scanner salvo."""
        self._refresh_scanners()
        saved = self.settings.value("scanner_name", "")
        if saved:
            index = self.cb_scanners.findText(str(saved))
            if index >= 0:
                self.cb_scanners.setCurrentIndex(index)

    def _save_and_close(self):
        """Salva a escolha e fecha."""
        choice = self.cb_scanners.currentText()
        if "Nenhum" in choice:
            self.settings.setValue("scanner_name", "")
        else:
            self.settings.setValue("scanner_name", choice)
        
        self.accept()
