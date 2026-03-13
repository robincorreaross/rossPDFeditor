"""
ViewerDialog - Visualizador de Páginas Interativo
Abre ao dar duplo clique numa página. Oferece zoom avançado ancorado, Pan (Mãozinha),
impressão nativa e botão rápido para recorte.
"""

import math
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPixmap, QPainter, QTransform
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QMessageBox
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

class CustomGraphicsView(QGraphicsView):
    """
    Subclasse de QGraphicsView para capturar eventos de roda do mouse (Ctrl+Scroll)
    e aplicar zoom ancorado na posição do ponteiro, similar a leitores PDF nativos.
    """
    zoom_changed = Signal(float)  # Sinaliza a alteração do fator matemático do zoom

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        # Habilita a Mãozinha para arrastar o documento (Pan Tool)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse) # Ancora o zoom no mouse
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.current_zoom = 1.0
        self.min_zoom = 0.1  # 10%
        self.max_zoom = 10.0 # 1000%
        
        self.setStyleSheet("""
            QGraphicsView {
                border: 1px solid #30315c;
                background-color: #1a1b41;
            }
        """)

    def wheelEvent(self, event):
        """Aplica zoom se Ctrl estiver pressionado, caso contrário, rola a página normalmente."""
        if event.modifiers() == Qt.ControlModifier:
            # Padrão: 120 graus por 'click' na roda
            angle = event.angleDelta().y()
            if angle > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self._set_zoom(self.current_zoom * 1.2)

    def zoom_out(self):
        self._set_zoom(self.current_zoom / 1.2)

    def zoom_reset(self):
        self._set_zoom(1.0)
        
    def _set_zoom(self, raw_zoom: float):
        # Clampa o valor de zoom
        new_zoom = max(self.min_zoom, min(raw_zoom, self.max_zoom))
        if new_zoom != self.current_zoom:
            self.current_zoom = new_zoom
            # Aplica a transformação baseada no fator absoluto
            transform = QTransform()
            transform.scale(self.current_zoom, self.current_zoom)
            self.setTransform(transform)
            self.zoom_changed.emit(self.current_zoom)


class ViewerDialog(QDialog):
    """
    Diálogo para visualização rica de uma página do PDF usando QGraphicsView.
    """
    request_crop = Signal()

    def __init__(self, pixmap: QPixmap, page_index: int, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.page_index = page_index
        
        self.setWindowTitle(f"Visualizador de Página - [Página {page_index + 1}]")
        self.setMinimumSize(900, 700)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        
        self._setup_ui()
        self._setup_scene()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ---- TOP BAR (Controles) ----
        top_bar = QHBoxLayout()
        
        # Grupo Botões de Zoom
        btn_zoom_out = QPushButton("➖")
        btn_zoom_out.setToolTip("Diminuir Zoom (Ctrl -)")
        
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        
        btn_zoom_reset = QPushButton("1:1")
        btn_zoom_reset.setToolTip("Tamanho Original")
        
        btn_zoom_in = QPushButton("➕")
        btn_zoom_in.setToolTip("Aumentar Zoom (Ctrl +)")
        

        # Grupo Ferramentas
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.setToolTip("Imprimir apenas esta página")
        btn_print.setStyleSheet("background-color: #3d5afe; color: white; font-weight: bold;")
        btn_print.clicked.connect(self._action_print)
        
        btn_crop = QPushButton("✂️ Recortar Página")
        btn_crop.setToolTip("Ir para o modo de recorte profundo")
        btn_crop.setStyleSheet("background-color: #ff5252; color: white; font-weight: bold;")
        btn_crop.clicked.connect(self._action_crop)

        top_bar.addWidget(btn_zoom_out)
        top_bar.addWidget(self.lbl_zoom)
        top_bar.addWidget(btn_zoom_reset)
        top_bar.addWidget(btn_zoom_in)
        
        top_bar.addSpacing(20)
        lbl_hint = QLabel("💡 Dica: Ctrl + Roda do Mouse para Zoom / Segure o Botão para Arrastar")
        lbl_hint.setStyleSheet("color: #a0a0b0; font-style: italic;")
        top_bar.addWidget(lbl_hint)
        
        top_bar.addStretch()
        top_bar.addWidget(btn_print)
        top_bar.addWidget(btn_crop)
        
        # ---- ÁREA DE VISUALIZAÇÃO (GraphicsView) ----
        self.scene = QGraphicsScene(self)
        self.view = CustomGraphicsView(self.scene, self)
        
        # Conecta os sinais de zoom aos botões e ao label
        self.view.zoom_changed.connect(self._update_zoom_label)
        btn_zoom_in.clicked.connect(self.view.zoom_in)
        btn_zoom_out.clicked.connect(self.view.zoom_out)
        btn_zoom_reset.clicked.connect(self.view.zoom_reset)

        layout.addLayout(top_bar)
        layout.addWidget(self.view)

    def _setup_scene(self):
        """Carrega a imagem na cena gráfica."""
        if not self.original_pixmap.isNull():
            self.pixmap_item = QGraphicsPixmapItem(self.original_pixmap)
            self.scene.addItem(self.pixmap_item)
            
            # Centraliza a cena em volta do papel (adiciona borda branca visual)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
            
            # Centraliza a visão no início
            self.view.centerOn(self.pixmap_item)

    def _update_zoom_label(self, zoom_factor: float):
        """Atualiza a label mostrando a porcentagem do zoom atual."""
        percent = int(round(zoom_factor * 100))
        self.lbl_zoom.setText(f"{percent}%")
            
    def _action_print(self):
        """Dispara diálogo de impressão do Windows para esta folha usando QtPrintSupport."""
        if self.original_pixmap.isNull():
            return
            
        printer = QPrinter(QPrinter.HighResolution)
        
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.Accepted:
            try:
                painter = QPainter(printer)
                rect = painter.viewport()
                size = self.original_pixmap.size()
                size.scale(rect.size(), Qt.KeepAspectRatio)
                
                painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
                painter.setWindow(self.original_pixmap.rect())
                
                painter.drawPixmap(0, 0, self.original_pixmap)
                painter.end()
                
                QMessageBox.information(self, "Impressão", "Comando de impressão enviado com sucesso.")
            except Exception as e:
                QMessageBox.critical(self, "Erro de Impressão", f"Falha ao comunicar com a impressora:\n{e}")

    def _action_crop(self):
        """Avisa a tela principal para transicionar para a ferramenta de recorte."""
        self.request_crop.emit()
        self.accept()
