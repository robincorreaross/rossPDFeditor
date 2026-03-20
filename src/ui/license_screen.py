"""
license_screen.py - Tela de ativação de licença do Ross PDF Editor (PySide6).
Exibida ao iniciar o app quando não há licença válida on-line ou off-line.
"""

from __future__ import annotations

import urllib.parse
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QClipboard
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QMessageBox, QSizePolicy
)

from src.core.license import get_machine_id, validar_licenca, LicenseError


class LicenseScreen(QWidget):
    """
    Janela standalone de ativação de licença dinâmica.
    Suporta estados: 'novo', 'expirado', 'inativo' e 'padrao'.
    """

    WHATSAPP_NUMBER = "5516991080895"

    def __init__(self, on_activate, estado: str = "novo", msg_extra: str = ""):
        super().__init__()
        self.on_activate = on_activate
        self.estado = estado.lower()
        self.msg_extra = msg_extra
        self.machine_id = get_machine_id()

        self.setWindowTitle("Ross PDF Editor — Gerenciamento de Licença")
        self.setFixedSize(620, 560)
        self.setStyleSheet(self._global_styles())

        self._build()
        self._center()

    def _center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _global_styles(self) -> str:
        return """
            QWidget {
                background-color: #0A1628;
                color: #E0E0E8;
                font-family: 'Segoe UI';
            }
            QFrame#card {
                background-color: #0D1B2A;
                border: 1px solid #1E3A5F;
                border-radius: 15px;
            }
            QFrame#mid_inner {
                background-color: #152030;
                border-radius: 10px;
                border: none;
            }
        """

    def _build(self):
        config = {
            "novo": {
                "icon": "👋",
                "titulo": "Seja Bem-vindo!",
                "subtitulo": "Para começar a usar o Ross PDF Editor, você precisa de uma licença ativa.",
                "orientacao": "Fale com o administrador para escolher o plano ideal e liberar seu acesso.",
                "cor": "#4FC3F7",
                "zap_msg": f"Olá Robinson, acabei de instalar o Ross PDF Editor e gostaria de escolher um plano. Meu ID: {self.machine_id}"
            },
            "expirado": {
                "icon": "⚠️",
                "titulo": "Sua Licença Expirou",
                "subtitulo": "O prazo de validade do seu plano atual chegou ao fim.",
                "orientacao": "Entre em contato para renovar sua assinatura e continuar sua operação.",
                "cor": "#EF5350",
                "zap_msg": f"Olá Robinson, minha licença do Ross PDF Editor expirou. Gostaria de renovar. Meu ID: {self.machine_id}"
            },
            "inativo": {
                "icon": "🚫",
                "titulo": "Licença Inativada",
                "subtitulo": "Seu acesso foi desativado temporariamente pelo administrador.",
                "orientacao": "Favor entrar em contato para verificar o status da sua conta.",
                "cor": "#FF9800",
                "zap_msg": f"Olá Robinson, meu acesso ao Ross PDF Editor aparece como Inativo. Pode verificar? Meu ID: {self.machine_id}"
            }
        }.get(self.estado, {
            "icon": "📄",
            "titulo": "Ross PDF Editor",
            "subtitulo": "Gerenciamento inteligente de licenças.",
            "orientacao": "Entre em contato para ativar sua licença.",
            "cor": "#4FC3F7",
            "zap_msg": f"Olá Robinson, preciso de ativação no Ross PDF Editor. Meu ID: {self.machine_id}"
        })

        self.zap_msg = config["zap_msg"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # ── Ícone ──
        icon_label = QLabel(config["icon"])
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 50px; border: none; background: transparent;")
        layout.addWidget(icon_label)

        # ── Título ──
        title = QLabel(config["titulo"])
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 26px; font-weight: bold;
            color: {config['cor']};
            border: none; background: transparent;
            padding: 5px 0;
        """)
        layout.addWidget(title)

        # ── Subtítulo ──
        sub = QLabel(config["subtitulo"])
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 13px; color: #90A4AE; border: none; background: transparent; padding-bottom: 20px;")
        layout.addWidget(sub)

        # ── Card Machine ID ──
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 15, 25, 15)
        card_layout.setSpacing(10)

        mid_title = QLabel("🖥️  Seu Identificador (Machine ID)")
        mid_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #B0BEC5; border: none; background: transparent;")
        card_layout.addWidget(mid_title)

        mid_inner = QFrame()
        mid_inner.setObjectName("mid_inner")
        mid_inner_layout = QHBoxLayout(mid_inner)
        mid_inner_layout.setContentsMargins(20, 12, 15, 12)

        mid_label = QLabel(self.machine_id)
        mid_label.setStyleSheet("font-family: 'Courier New'; font-size: 18px; font-weight: bold; color: #E3F2FD; border: none; background: transparent;")
        mid_inner_layout.addWidget(mid_label)

        mid_inner_layout.addStretch()

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
        mid_inner_layout.addWidget(btn_copy)

        card_layout.addWidget(mid_inner)

        orientacao = QLabel(config["orientacao"])
        orientacao.setWordWrap(True)
        orientacao.setStyleSheet("font-size: 11px; font-style: italic; color: #546E7A; border: none; background: transparent;")
        card_layout.addWidget(orientacao)

        layout.addWidget(card)
        layout.addSpacing(20)

        # ── Botões de Ação ──
        btn_recheck = QPushButton("🔄  Já adquiri! Verificar Agora")
        btn_recheck.setCursor(Qt.PointingHandCursor)
        btn_recheck.setFixedHeight(48)
        btn_recheck.setStyleSheet("""
            QPushButton {
                background-color: #0D47A1;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565C0; }
        """)
        btn_recheck.clicked.connect(self._recheck)
        layout.addWidget(btn_recheck)
        layout.addSpacing(8)

        btn_whatsapp = QPushButton("💬  Falar com Robinson (WhatsApp)")
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
        layout.addWidget(btn_whatsapp)
        layout.addSpacing(15)

        # ── Status ──
        self._status_label = QLabel(self.msg_extra if self.msg_extra else "Aguardando ativação...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("font-size: 11px; color: #546E7A; border: none; background: transparent;")
        layout.addWidget(self._status_label)
        layout.addStretch()

    def _copiar_mid(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.machine_id)
        self._status_label.setText("✅ ID copiado! Envie pelo WhatsApp.")
        self._status_label.setStyleSheet("font-size: 11px; color: #66BB6A; border: none; background: transparent;")

    def _recheck(self):
        self._status_label.setText("🔍 Verificando no servidor...")
        self._status_label.setStyleSheet("font-size: 11px; color: #4FC3F7; border: none; background: transparent;")
        QApplication.processEvents()

        try:
            info = validar_licenca("")
            if info.get("valido"):
                QMessageBox.information(self, "Sucesso", "✅ Acesso liberado! Bom trabalho.")
                self.close()
                self.on_activate()
            else:
                self._status_label.setText("❌ Ainda não consta como ativo no sistema.")
                self._status_label.setStyleSheet("font-size: 11px; color: #EF5350; border: none; background: transparent;")
        except LicenseError as e:
            msg = str(e)
            if "novo" in msg:
                msg = "Aguardando liberação no sistema."
            self._status_label.setText(f"❌ {msg}")
            self._status_label.setStyleSheet("font-size: 11px; color: #EF5350; border: none; background: transparent;")
        except Exception:
            self._status_label.setText("⚠️ Verifique sua internet.")
            self._status_label.setStyleSheet("font-size: 11px; color: #FFA726; border: none; background: transparent;")

    def _abrir_whatsapp(self):
        url = f"https://wa.me/{self.WHATSAPP_NUMBER}?text={urllib.parse.quote(self.zap_msg)}"
        webbrowser.open(url)
