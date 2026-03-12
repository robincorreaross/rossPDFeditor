"""
Ross PDF Editor – Diálogo de Recorte (Crop).

Permite ao usuário selecionar uma região retangular sobre a página
para realizar um recorte real (CropBox), similar ao que se faz em editores
de imagem.
"""

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy
)


class CropOverlay(QLabel):
    """
    Widget que mostra a imagem da página e permite desenhar
    um retângulo de seleção de recorte com o mouse.
    """

    crop_selected = Signal(QRect)

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignCenter)

        # Seleção
        self._start = QPoint()
        self._end = QPoint()
        self._drawing = False
        self._has_selection = False
        self._selection_rect = QRect()

        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._drawing = True
            self._has_selection = False
            self.update()

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            self._end = event.pos()
            rect = QRect(self._start, self._end).normalized()
            # Mínimo de 20x20 pixels
            if rect.width() > 20 and rect.height() > 20:
                self._has_selection = True
                self._selection_rect = rect
                self.crop_selected.emit(rect)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._drawing or self._has_selection:
            rect = QRect(self._start, self._end).normalized() \
                if self._drawing else self._selection_rect

            # Overlay escuro fora da seleção
            overlay = QColor(0, 0, 0, 120)
            # Topo
            painter.fillRect(0, 0, self.width(), rect.top(), overlay)
            # Fundo
            painter.fillRect(
                0, rect.bottom(), self.width(),
                self.height() - rect.bottom(), overlay
            )
            # Esquerda
            painter.fillRect(
                0, rect.top(), rect.left(),
                rect.height(), overlay
            )
            # Direita
            painter.fillRect(
                rect.right(), rect.top(),
                self.width() - rect.right(), rect.height(), overlay
            )

            # Borda da seleção
            pen = QPen(QColor("#3d5afe"), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Alças nos cantos
            handle_size = 8
            handle_color = QColor("#3d5afe")
            painter.setBrush(QBrush(handle_color))
            painter.setPen(Qt.NoPen)
            corners = [
                rect.topLeft(), rect.topRight(),
                rect.bottomLeft(), rect.bottomRight(),
            ]
            for corner in corners:
                painter.drawEllipse(corner, handle_size // 2, handle_size // 2)

        painter.end()

    def get_crop_rect_normalized(self) -> tuple:
        """
        Retorna o retângulo de seleção normalizado para (0..1, 0..1)
        relativo ao tamanho da imagem exibida.
        """
        if not self._has_selection:
            return None
        r = self._selection_rect
        w = self.width()
        h = self.height()
        return (
            max(0, r.x() / w),
            max(0, r.y() / h),
            min(1, r.right() / w),
            min(1, r.bottom() / h),
        )


class CropDialog(QDialog):
    """
    Diálogo de recorte que mostra a página e permite
    selecionar a região de crop.
    """

    def __init__(self, png_data: bytes, page_size: tuple, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recortar Página")
        self.setMinimumSize(700, 550)
        self.page_width, self.page_height = page_size
        self._crop_result = None

        # ── Layout ───────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Instrução
        hint = QLabel("Clique e arraste para selecionar a área de recorte.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            "color: #8080b0; font-size: 13px; padding: 8px;"
        )
        layout.addWidget(hint)

        # Imagem com overlay
        img = QImage()
        img.loadFromData(png_data)
        pixmap = QPixmap.fromImage(img)

        # Escalar para caber na janela
        display_w = min(660, pixmap.width())
        display_h = min(440, pixmap.height())
        scaled = pixmap.scaled(
            display_w, display_h,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.crop_overlay = CropOverlay(scaled)
        self.crop_overlay.setFixedSize(scaled.size())
        self.crop_overlay.crop_selected.connect(self._on_crop_selected)
        layout.addWidget(self.crop_overlay, alignment=Qt.AlignCenter)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setFixedSize(120, 38)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_apply = QPushButton("Aplicar Recorte")
        self.btn_apply.setObjectName("btn_primary")
        self.btn_apply.setFixedSize(160, 38)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def _on_crop_selected(self, rect: QRect):
        self.btn_apply.setEnabled(True)

    def _apply(self):
        normalized = self.crop_overlay.get_crop_rect_normalized()
        if normalized:
            nx0, ny0, nx1, ny1 = normalized
            # Converter para coordenadas reais da página em pontos
            self._crop_result = (
                nx0 * self.page_width,
                ny0 * self.page_height,
                nx1 * self.page_width,
                ny1 * self.page_height,
            )
            self.accept()

    def get_crop_rect(self) -> tuple:
        """Retorna (x0, y0, x1, y1) em pontos da página, ou None."""
        return self._crop_result
