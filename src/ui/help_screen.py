"""
help_screen.py - Central de Ajuda e Suporte do Ross PDF Editor.
Exibe informações de licenciamento, Machine ID, vencimento e suporte via WhatsApp.
"""

from __future__ import annotations

import urllib.parse
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication
)

from src.core.license import get_machine_id, validar_licenca, LicenseError
from PySide6.QtCore import QSettings
from version import APP_VERSION


class HelpScreen(QDialog):
    """Central de Ajuda e Suporte com informações de licenciamento."""

    WHATSAPP_NUMBER = "5516991080895"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.machine_id = get_machine_id()
        self._settings = QSettings("Ross", "RossPDFEditor")
        self.license_info = self._get_license_info()

        self.setWindowTitle("Ross PDF Editor — Ajuda e Suporte")
        self.setFixedSize(600, 500)
        self.setStyleSheet(self._global_styles())
        self._build()

    def _global_styles(self) -> str:
        return """
            QDialog {
                background-color: #0A1628;
                color: #E0E0E8;
                font-family: 'Segoe UI';
            }
            QFrame#card {
                background-color: #0D1B2A;
                border: 1px solid #1E3A5F;
                border-radius: 15px;
            }
            QFrame#mid_box {
                background-color: #152030;
                border-radius: 10px;
                border: none;
            }
        """

    def _get_license_info(self) -> dict:
        try:
            saved_key = self._settings.value("license_key", "")
            info = validar_licenca(saved_key)
            return info
        except Exception:
            return {"valido": False, "expiry": "—", "plano": "—", "dias_restantes": -1}

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # ── Título ──
        title = QLabel("Central de Ajuda e Suporte")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px; font-weight: bold;
            color: #4FC3F7; border: none; background: transparent;
            padding-bottom: 20px;
        """)
        layout.addWidget(title)

        # ── Card: Informações de Licenciamento ──
        card1 = QFrame()
        card1.setObjectName("card")
        card1_layout = QVBoxLayout(card1)
        card1_layout.setContentsMargins(25, 15, 25, 15)
        card1_layout.setSpacing(10)

        lic_title = QLabel("📋  Informações de Licenciamento")
        lic_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E0E0E8; border: none; background: transparent;")
        card1_layout.addWidget(lic_title)

        # Machine ID box
        mid_box = QFrame()
        mid_box.setObjectName("mid_box")
        mid_box_layout = QHBoxLayout(mid_box)
        mid_box_layout.setContentsMargins(20, 12, 15, 12)

        mid_label_title = QLabel("Machine ID:")
        mid_label_title.setStyleSheet("font-size: 12px; color: #90A4AE; border: none; background: transparent;")
        mid_box_layout.addWidget(mid_label_title)

        mid_value = QLabel(self.machine_id)
        mid_value.setStyleSheet("font-family: 'Courier New'; font-size: 16px; font-weight: bold; color: #E3F2FD; border: none; background: transparent;")
        mid_box_layout.addWidget(mid_value)

        mid_box_layout.addStretch()

        btn_copy = QPushButton("📋 Copiar")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setFixedSize(100, 34)
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        btn_copy.clicked.connect(self._copiar_mid)
        mid_box_layout.addWidget(btn_copy)

        card1_layout.addWidget(mid_box)

        # Vencimento, Plano e Dias Restantes
        info_row = QHBoxLayout()
        plano_nome = self.license_info.get("plano", "—").upper()
        is_vitalicio = plano_nome == "VITALICIO"

        if not is_vitalicio:
            expiry_text = self.license_info.get("expiry", "—")
            vencimento = QLabel(f"📅 Vencimento: {expiry_text}")
            vencimento.setStyleSheet("font-size: 13px; color: #4FC3F7; border: none; background: transparent;")
            info_row.addWidget(vencimento)

        info_row.addStretch()

        tipo_label = QLabel(f"Plano: {plano_nome} (v{APP_VERSION})")
        tipo_label.setStyleSheet("font-size: 13px; color: #90A4AE; border: none; background: transparent;")
        info_row.addWidget(tipo_label)

        card1_layout.addLayout(info_row)

        # Dias restantes com cor condicional (Não mostrar se for VITALICIO)
        if not is_vitalicio:
            dias = self.license_info.get("dias_restantes", -1)
            if isinstance(dias, int) and dias >= 0:
                if dias <= 3:
                    dias_cor = "#EF5350"  # Vermelho
                    dias_texto = f"⚠️ Atenção: restam apenas {dias} dia(s) de licença!"
                elif dias <= 7:
                    dias_cor = "#FFB74D"  # Amarelo
                    dias_texto = f"⏳ Restam {dias} dia(s) de licença."
                else:
                    dias_cor = "#66BB6A"  # Verde
                    dias_texto = f"✅ Licença válida por mais {dias} dia(s)."
                
                dias_label = QLabel(dias_texto)
                dias_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {dias_cor}; border: none; background: transparent; padding-top: 4px;")
                card1_layout.addWidget(dias_label)

        layout.addWidget(card1)
        layout.addSpacing(20)


        # ── Card: Suporte Técnico ──
        card2 = QFrame()
        card2.setObjectName("card")
        card2_layout = QVBoxLayout(card2)
        card2_layout.setContentsMargins(25, 15, 25, 20)
        card2_layout.setSpacing(10)

        sup_title = QLabel("⚙️  Suporte Técnico")
        sup_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E0E0E8; border: none; background: transparent;")
        card2_layout.addWidget(sup_title)

        sup_desc = QLabel("Precisa de renovação ou ajuda técnica? Chame nosso time diretamente pelo WhatsApp no botão abaixo.")
        sup_desc.setWordWrap(True)
        sup_desc.setStyleSheet("font-size: 12px; color: #90A4AE; border: none; background: transparent;")
        card2_layout.addWidget(sup_desc)

        btn_whatsapp = QPushButton("💬  Chamar Robinson no WhatsApp")
        btn_whatsapp.setCursor(Qt.PointingHandCursor)
        btn_whatsapp.setFixedHeight(48)
        btn_whatsapp.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        btn_whatsapp.clicked.connect(self._abrir_whatsapp)
        card2_layout.addWidget(btn_whatsapp)

        layout.addWidget(card2)
        layout.addStretch()

    def _copiar_mid(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.machine_id)

    def _abrir_whatsapp(self):
        msg = f"Olá Robinson, preciso de suporte técnico no Ross PDF Editor. Meu ID: {self.machine_id}"
        url = f"https://wa.me/{self.WHATSAPP_NUMBER}?text={urllib.parse.quote(msg)}"
        webbrowser.open(url)
