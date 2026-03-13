"""
Ross PDF Editor – Componente de Card de Página (Thumbnail).

Cada página do PDF é representada por um card com:
- Miniatura renderizada
- Número da página
- Indicador de seleção
- Botão de excluir (ao hover)
- Botão de duplicar (ao hover)
- Suporte a Drag & Drop para reordenação
"""

from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, QMimeData, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QIcon, QDrag
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect, QApplication
)

class HoverButton(QPushButton):
    """Botão customizado flutuante que desenha seu próprio fundo e ícone
    contornando bugs de renderização CSS com alpha em fontes unicode do Qt."""
    def __init__(self, text, text_color, font_size, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self._text = text
        self._text_color = QColor(text_color)
        self._font_size = font_size
        self._hovered = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Fundo circular, mais escuro no hover (0.85) vs normal (0.65)
        bg_alpha = 216 if self._hovered else 165
        painter.setBrush(QColor(0, 0, 0, bg_alpha))
        painter.setPen(Qt.NoPen)
        r = self.rect()
        painter.drawEllipse(r)

        # Texto (ícone) desenhado manualmente para forçar legibilidade e alinhamento
        painter.setPen(self._text_color)
        font = painter.font()
        font.setPixelSize(self._font_size)
        font.setBold(True)
        painter.setFont(font)
        
        # O textRect permite afinação, empurramos 1-2 px pra cima ou lado pro centro ideal
        if self._text == "+": # O "+" é teimoso
            r.translate(0, -2)
        elif self._text in ("↺", "↻"): # Setas um pouquinho maiores descem
            r.translate(0, -2)
            
        painter.drawText(r, Qt.AlignCenter, self._text)


class PageThumbnail(QFrame):
    """Card visual que representa uma página do PDF."""

    clicked = Signal(int)           # índice da página
    delete_requested = Signal(int)  # índice da página
    duplicate_requested = Signal(int) # índice da página
    rotate_left_requested = Signal(int)  # índice da página
    rotate_right_requested = Signal(int) # índice da página
    crop_requested = Signal(int)    # índice da página
    double_clicked = Signal(int)    # índice da página
    drag_started = Signal(int)      # índice da página sendo arrastada
    drop_received = Signal(int, int)  # (from_index, to_index)

    THUMB_WIDTH = 180
    THUMB_HEIGHT = 240

    def __init__(self, page_index: int, png_data: bytes, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self._selected = False
        self._drag_start_pos = None
        self._is_drag_over = False

        self.setObjectName("page_card")
        self.setFixedSize(self.THUMB_WIDTH + 20, self.THUMB_HEIGHT + 50)
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)

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
        self.btn_delete = HoverButton("✕", "#ff1744", 22, self)
        self.btn_delete.setToolTip("Excluir Página")
        self.btn_delete.hide()
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self.page_index))

        # ── Botão Duplicar (canto superior esquerdo) ──────────
        self.btn_duplicate = HoverButton("+", "#00e676", 32, self)
        self.btn_duplicate.setToolTip("Duplicar Página")
        self.btn_duplicate.hide()
        self.btn_duplicate.clicked.connect(lambda: self.duplicate_requested.emit(self.page_index))

        # ── Botão Girar Esq (canto inferior esquerdo) ──────────
        self.btn_rotate_left = HoverButton("↺", "#40c4ff", 28, self)
        self.btn_rotate_left.setToolTip("Girar para Esquerda")
        self.btn_rotate_left.hide()
        self.btn_rotate_left.clicked.connect(lambda: self.rotate_left_requested.emit(self.page_index))

        # ── Botão Girar Dir (canto inferior direito) ──────────
        self.btn_rotate_right = HoverButton("↻", "#40c4ff", 28, self)
        self.btn_rotate_right.setToolTip("Girar para Direita")
        self.btn_rotate_right.hide()
        self.btn_rotate_right.clicked.connect(lambda: self.rotate_right_requested.emit(self.page_index))

        # Posicionamento inicial
        self.btn_delete.move(self.width() - 40, 4)
        self.btn_duplicate.move(4, 4)
        self.btn_rotate_left.move(4, self.THUMB_HEIGHT - 30)
        self.btn_rotate_right.move(self.THUMB_WIDTH - 22, self.THUMB_HEIGHT - 30)


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

    # ── Eventos de Mouse (Drag) ───────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self.page_index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
            return

        # Só inicia o drag se mover mais de 20px (evita drag acidental)
        distance = (event.pos() - self._drag_start_pos).manhattanLength()
        if distance < 20:
            return

        # Criar o drag visual
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.page_index))
        drag.setMimeData(mime)

        # Criar miniatura semi-transparente para o cursor
        pixmap = self.grab()
        scaled_pixmap = pixmap.scaled(
            120, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # Adicionar efeito de transparência
        transparent = QPixmap(scaled_pixmap.size())
        transparent.fill(Qt.transparent)
        painter = QPainter(transparent)
        painter.setOpacity(0.7)
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.end()

        drag.setPixmap(transparent)
        drag.setHotSpot(QPoint(transparent.width() // 2, transparent.height() // 2))

        self.drag_started.emit(self.page_index)
        drag.exec(Qt.MoveAction)
        self._drag_start_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.page_index)
        super().mouseDoubleClickEvent(event)

    # ── Eventos de Drop ───────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            try:
                from_index = int(event.mimeData().text())
                if from_index != self.page_index:
                    event.acceptProposedAction()
                    self._is_drag_over = True
                    self.setStyleSheet("""
                        QFrame#page_card {
                            border: 3px solid #3d5afe;
                            border-radius: 12px;
                            background-color: #1a1a40;
                        }
                    """)
                    return
            except ValueError:
                pass
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_drag_over = False
        self.setStyleSheet("")  # Remove o destaque
        # Re-aplica selected se necessário
        if self._selected:
            self.selected = True
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._is_drag_over = False
        self.setStyleSheet("")
        if self._selected:
            self.selected = True

        if event.mimeData().hasText():
            try:
                from_index = int(event.mimeData().text())
                if from_index != self.page_index:
                    event.acceptProposedAction()
                    self.drop_received.emit(from_index, self.page_index)
                    return
            except ValueError:
                pass
        event.ignore()

    # ── Hover ─────────────────────────────────────────────────

    def enterEvent(self, event):
        self.btn_delete.show()
        self.btn_duplicate.show()
        self.btn_rotate_left.show()
        self.btn_rotate_right.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_delete.hide()
        self.btn_duplicate.hide()
        self.btn_rotate_left.hide()
        self.btn_rotate_right.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self.btn_delete.move(self.width() - 40, 4)
        self.btn_duplicate.move(4, 4)
        self.btn_rotate_left.move(4, self.height() - 44)
        self.btn_rotate_right.move(self.width() - 40, self.height() - 44)
        super().resizeEvent(event)
