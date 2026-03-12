"""
Ross PDF Editor – Componente de Card de Página (Thumbnail).

Cada página do PDF é representada por um card com:
- Miniatura renderizada
- Número da página
- Indicador de seleção
- Botão de excluir (ao hover)
"""

from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect
)


class PageThumbnail(QFrame):
    """Card visual que representa uma página do PDF."""

    clicked = Signal(int)           # índice da página
    delete_requested = Signal(int)  # índice da página
    duplicate_requested = Signal(int) # índice da página
    crop_requested = Signal(int)    # índice da página
    double_clicked = Signal(int)    # índice da página

    THUMB_WIDTH = 180
    THUMB_HEIGHT = 240

    def __init__(self, page_index: int, png_data: bytes, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self._selected = False

        self.setObjectName("page_card")
        self.setFixedSize(self.THUMB_WIDTH + 20, self.THUMB_HEIGHT + 50)
        self.setCursor(Qt.PointingHandCursor)

        # ── Layout ───────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(4)

        # Miniatura
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setFixedSize(self.THUMB_WIDTH, self.THUMB_HEIGHT)
        self.thumb_label.setStyleSheet(
            "background-color: #ffffff; border-radius: 6px;"
        )
        layout.addWidget(self.thumb_label, alignment=Qt.AlignCenter)

        # Número da página
        self.page_label = QLabel(f"Página {page_index + 1}")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet(
            "color: #8080b0; font-size: 11px; font-weight: 500;"
        )
        layout.addWidget(self.page_label)

        # ── Botão Fechar (canto superior direito) ────────────
        self.btn_delete = QPushButton("✕")
        self.btn_delete.setParent(self)
        self.btn_delete.setFixedSize(26, 26)
        self.btn_delete.setToolTip("Excluir Página")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #e53935;
                color: white;
                border: none;
                border-radius: 13px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
        """)
        self.btn_delete.move(self.width() - 30, 4)
        self.btn_delete.hide()
        self.btn_delete.clicked.connect(
            lambda: self.delete_requested.emit(self.page_index)
        )

        # ── Botão Duplicar (canto superior esquerdo) ──────────
        self.btn_duplicate = QPushButton("+")
        self.btn_duplicate.setParent(self)
        self.btn_duplicate.setFixedSize(26, 26)
        self.btn_duplicate.setToolTip("Duplicar Página")
        self.btn_duplicate.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 13px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        self.btn_duplicate.move(4, 4)
        self.btn_duplicate.hide()
        self.btn_duplicate.clicked.connect(
            lambda: self.duplicate_requested.emit(self.page_index)
        )

        # Carregar imagem
        self._set_thumbnail(png_data)

    def _set_thumbnail(self, png_data: bytes):
        """Carrega os bytes PNG na label de miniatura."""
        img = QImage()
        img.loadFromData(png_data)
        pixmap = QPixmap.fromImage(img)
        scaled = pixmap.scaled(
            self.THUMB_WIDTH - 8, self.THUMB_HEIGHT - 8,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.thumb_label.setPixmap(scaled)

    def update_thumbnail(self, png_data: bytes):
        """Atualiza a imagem da miniatura."""
        self._set_thumbnail(png_data)

    def update_index(self, new_index: int):
        """Atualiza o índice da página após reordenação/exclusão."""
        self.page_index = new_index
        self.page_label.setText(f"Página {new_index + 1}")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool):
        self._selected = value
        self.setProperty("selected", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ── Eventos ──────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.page_index)
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self.btn_delete.show()
        self.btn_duplicate.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_delete.hide()
        self.btn_duplicate.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self.btn_delete.move(self.width() - 30, 4)
        self.btn_duplicate.move(4, 4)
        super().resizeEvent(event)
