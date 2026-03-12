"""
Ross PDF Editor – Janela Principal.

Interface clean e funcional com:
- Toolbar com ações principais
- Área central de miniaturas com drag & drop
- Tela inicial (drop zone) quando não há documento aberto
- Suporte a seleção múltipla, exclusão, inserção e recorte
"""

import os
import sys
import threading
from pathlib import Path
from PySide6.QtCore import (
    Qt, QSize, QMimeData, QTimer, QPropertyAnimation, QEasingCurve,
    QSettings, QStandardPaths
)
from PySide6.QtGui import (
    QIcon, QAction, QKeySequence, QDragEnterEvent, QDropEvent,
    QFont, QColor, QPainter, QPixmap
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QPushButton, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QApplication, QFrame, QGridLayout, QSizePolicy,
    QSpacerItem, QMenu
)

from src.engine.pdf_engine import PDFEngine
from src.ui.page_thumbnail import PageThumbnail
from src.ui.crop_dialog import CropDialog
from src.ui.help_screen import HelpScreen
from src.core.updater import verificar_atualizacao, baixar_e_instalar, abrir_download
from src.core.license import get_machine_id, validar_licenca
from version import APP_VERSION, DOWNLOAD_URL


class DropZone(QFrame):
    """Tela inicial de boas-vindas com drag & drop."""

    file_dropped = None  # será conectado depois

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.setMinimumSize(500, 350)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        # Ícone
        icon_label = QLabel("📄")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 64px; border: none;")
        layout.addWidget(icon_label)

        # Título
        title = QLabel("Arraste um PDF ou imagem aqui")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 22px; font-weight: 600; color: #e0e0e8; border: none;"
        )
        layout.addWidget(title)

        # Subtítulo
        sub = QLabel("ou clique no botão abaixo para selecionar")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            "font-size: 14px; color: #7070a0; border: none;"
        )
        layout.addWidget(sub)

        # Botão abrir
        self.btn_open = QPushButton("📂  Abrir Arquivo")
        self.btn_open.setObjectName("btn_primary")
        self.btn_open.setFixedSize(220, 48)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background-color: #3d5afe;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #536dfe;
            }
        """)
        layout.addWidget(self.btn_open, alignment=Qt.AlignCenter)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame#drop_zone {
                    background-color: #1e1f50;
                    border: 2px dashed #3d5afe;
                    border-radius: 16px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if self.file_dropped:
                self.file_dropped(path)


class FlowLayout(QVBoxLayout):
    """Layout simples baseado em linhas para organizar as thumbnails."""
    pass


class MainWindow(QMainWindow):
    """Janela principal do Ross PDF Editor."""

    APP_TITLE = "Ross PDF Editor"
    SUPPORTED_PDF = "Arquivos PDF (*.pdf)"
    SUPPORTED_IMAGES = "Imagens (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
    SUPPORTED_ALL = "PDF e Imagens (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff *.webp)"

    def __init__(self):
        super().__init__()
        self.engine = PDFEngine()
        self.thumbnails: list[PageThumbnail] = []
        self.selected_indices: set[int] = set()
        self.is_dirty = False  # Rastreia se há alterações não salvas

        # Histórico de Undo/Redo (snapshots do PDF em bytes)
        self._undo_stack: list[bytes] = []
        self._redo_stack: list[bytes] = []
        self._max_history = 30

        # Última pasta visitada (persistência via QSettings)
        self._settings = QSettings("Ross", "RossPDFEditor")

        self._setup_window()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._show_drop_zone()

        # Verificações em background após a janela estar pronta (igual DocPopular)
        QTimer.singleShot(1000, self._iniciar_verificacao_update)
        QTimer.singleShot(2000, self._verificar_expiracao_licenca)


    # ══════════════════════════════════════════════════════════
    # Setup
    # ══════════════════════════════════════════════════════════

    def _setup_window(self):
        self.setWindowTitle(self.APP_TITLE)
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)
        self.setAcceptDrops(True)

        # Carregar stylesheet
        qss_path = Path(__file__).parent.parent.parent / "assets" / "styles.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _setup_toolbar(self):
        self.toolbar = QToolBar("Ferramentas")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(self.toolbar)

        # Ações
        self.act_open = QAction("📂 Abrir", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.setToolTip("Abrir arquivo PDF (Ctrl+O)")
        self.act_open.triggered.connect(self._action_open)
        self.toolbar.addAction(self.act_open)

        self.act_new = QAction("📄 Novo", self)
        self.act_new.setToolTip("Iniciar um novo projeto (Ctrl+N)")
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.triggered.connect(self._action_new)
        self.toolbar.addAction(self.act_new)

        self.act_save = QAction("💾 Salvar", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setToolTip("Salvar documento (Ctrl+S)")
        self.act_save.triggered.connect(self._action_save)
        self.act_save.setEnabled(False)
        self.toolbar.addAction(self.act_save)

        self.act_save_as = QAction("💾 Salvar Como", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setToolTip("Salvar como... (Ctrl+Shift+S)")
        self.act_save_as.triggered.connect(self._action_save_as)
        self.act_save_as.setEnabled(False)
        self.toolbar.addAction(self.act_save_as)

        self.toolbar.addSeparator()

        self.act_add_pages = QAction("➕ Adicionar", self)
        self.act_add_pages.setToolTip("Adicionar páginas (PDF ou imagens)")
        self.act_add_pages.triggered.connect(self._action_add_pages)
        self.act_add_pages.setEnabled(False)
        self.toolbar.addAction(self.act_add_pages)

        self.act_add_blank = QAction("📃 Página Branca", self)
        self.act_add_blank.setToolTip("Inserir página em branco")
        self.act_add_blank.triggered.connect(self._action_add_blank)
        self.act_add_blank.setEnabled(False)
        self.toolbar.addAction(self.act_add_blank)

        self.toolbar.addSeparator()

        self.act_delete = QAction("🗑️ Excluir", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.setToolTip("Excluir páginas selecionadas (Del)")
        self.act_delete.triggered.connect(self._action_delete)
        self.act_delete.setEnabled(False)
        self.toolbar.addAction(self.act_delete)

        self.act_crop = QAction("✂️ Recortar", self)
        self.act_crop.setToolTip("Recortar a página selecionada")
        self.act_crop.triggered.connect(self._action_crop)
        self.act_crop.setEnabled(False)
        self.toolbar.addAction(self.act_crop)

        self.toolbar.addSeparator()

        self.act_undo = QAction("↩️ Desfazer", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setToolTip("Desfazer última ação (Ctrl+Z)")
        self.act_undo.triggered.connect(self._action_undo)
        self.act_undo.setEnabled(False)
        self.toolbar.addAction(self.act_undo)

        self.act_redo = QAction("↪️ Refazer", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.setToolTip("Refazer ação desfeita (Ctrl+Y)")
        self.act_redo.triggered.connect(self._action_redo)
        self.act_redo.setEnabled(False)
        self.toolbar.addAction(self.act_redo)

        self.toolbar.addSeparator()

        self.act_help = QAction("❓ Ajuda", self)
        self.act_help.setToolTip("Central de Ajuda e Suporte")
        self.act_help.triggered.connect(self._action_help)
        self.toolbar.addAction(self.act_help)

    def _setup_central(self):
        """Cria o widget central com scroll area para os thumbnails."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Banner de atualização (oculto inicialmente)
        self._update_banner = QFrame(self.central_widget)
        self._update_banner.setObjectName("updateBanner")
        self._update_banner.setFixedHeight(42)
        self._update_banner.setStyleSheet("QFrame#updateBanner { background-color: #0D2B0D; border: none; }")
        self._update_banner_layout = QHBoxLayout(self._update_banner)
        self._update_banner_layout.setContentsMargins(20, 0, 20, 0)
        
        self._lbl_update_msg = QLabel("")
        self._lbl_update_msg.setStyleSheet("color: white; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        self._update_banner_layout.addWidget(self._lbl_update_msg)
        
        self._update_banner_layout.addStretch()
        
        self._btn_download_update = QPushButton("⬇️  Baixar agora")
        self._btn_download_update.setFixedSize(130, 28)
        self._btn_download_update.setCursor(Qt.PointingHandCursor)
        self._btn_download_update.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self._btn_download_update.clicked.connect(self._abrir_download)
        self._update_banner_layout.addWidget(self._btn_download_update)
        
        self._btn_close_update = QPushButton("✕")
        self._btn_close_update.setFixedSize(28, 28)
        self._btn_close_update.setCursor(Qt.PointingHandCursor)
        self._btn_close_update.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A5D6A7;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { color: white; }
        """)
        self._btn_close_update.clicked.connect(self._update_banner.hide)
        self._update_banner_layout.addWidget(self._btn_close_update)
        
        self._update_banner.hide()

        # Banner de licença (oculto inicialmente)
        self._license_banner = QFrame(self.central_widget)
        self._license_banner.setObjectName("licenseBanner")
        self._license_banner.setFixedHeight(45)
        self._license_banner.setStyleSheet("QFrame#licenseBanner { background-color: #D84315; border-bottom: 1px solid #BF360C; }") 
        self._license_banner_layout = QHBoxLayout(self._license_banner)
        self._license_banner_layout.setContentsMargins(20, 0, 20, 0)
        
        self._lbl_license_msg = QLabel("")
        self._lbl_license_msg.setStyleSheet("color: white; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        self._license_banner_layout.addWidget(self._lbl_license_msg)
        
        self._btn_renovar = QPushButton("💎  Renovar Agora")
        self._btn_renovar.setFixedSize(140, 28)
        self._btn_renovar.setCursor(Qt.PointingHandCursor)
        self._btn_renovar.setStyleSheet("""
            QPushButton {
                background-color: #E65100;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid #BF360C;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self._btn_renovar.clicked.connect(self._abrir_whatsapp_renovacao)
        self._license_banner_layout.addWidget(self._btn_renovar)
        
        self._license_banner_layout.addStretch()
        
        btn_close_lic = QPushButton("✕")
        btn_close_lic.setFixedSize(28, 28)
        btn_close_lic.setCursor(Qt.PointingHandCursor)
        btn_close_lic.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #FFCCBC;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { color: white; }
        """)
        btn_close_lic.clicked.connect(self._license_banner.hide)
        self._license_banner_layout.addWidget(btn_close_lic)
        
        self._license_banner.hide()


        # Scroll area para as páginas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.pages_container = QWidget()
        self.pages_layout = None  # Será criado ao carregar o documento
        self.scroll_area.setWidget(self.pages_container)
        self.scroll_area.hide()

        # Wrapper para organizar a DropZone centralizada ou a ScrollArea expansiva
        self.content_wrapper = QWidget()
        self.wrapper_layout = QVBoxLayout(self.content_wrapper)
        self.wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        self.wrapper_layout.addWidget(self.scroll_area, 1) # Scroll area preenche quando visível

        self.main_layout.addWidget(self._update_banner)
        self.main_layout.addWidget(self._license_banner)
        self.main_layout.addWidget(self.content_wrapper, 1)  # Wrapper preenche espaço restante



    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bem-vindo ao Ross PDF Editor")

    # ══════════════════════════════════════════════════════════
    # Ajuda
    # ══════════════════════════════════════════════════════════

    def _action_help(self):
        """Abre a Central de Ajuda e Suporte."""
        dialog = HelpScreen(self)
        dialog.exec()

    # ── Sistema de update ────────────────────────────────────────────────────────

    def _iniciar_verificacao_update(self):
        """Dispara a verificação de update em background."""
        try:
            verificar_atualizacao(
                on_update_available=lambda v, c, m, z: QTimer.singleShot(
                    0, lambda: self._mostrar_banner_update(v, c, m, z)
                )
            )
        except Exception as e:
            print(f"[DEBUG] Falha na verificação de update: {e}")

    def _mostrar_banner_update(self, nova_versao: str, changelog: list[str], obrigatoria: bool, zip_url: str = ""):
        """Exibe o banner de notificação de update no topo do app."""
        self._update_zip_url = zip_url
        
        emoji = "🚨" if obrigatoria else "🟢"
        tipo = "OBRIGATÓRIA" if obrigatoria else "disponível"
        desc = changelog[0] if changelog else ""
        texto = f"{emoji}  Atualização {tipo}: versão {nova_versao}   —   {desc}"

        self._lbl_update_msg.setText(texto)
        self._lbl_update_msg.setStyleSheet(f"color: {'#FFCDD2' if obrigatoria else '#A5D6A7'}; font-weight: bold; font-size: 13px; border: none; background: transparent;")
        
        if obrigatoria:
            self._btn_download_update.setStyleSheet("""
                QPushButton { background-color: #C62828; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 11px; }
                QPushButton:hover { background-color: #D32F2F; }
            """)
            self._btn_close_update.hide()
        else:
            self._btn_download_update.setStyleSheet("""
                QPushButton { background-color: #2E7D32; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 11px; }
                QPushButton:hover { background-color: #388E3C; }
            """)
            self._btn_close_update.show()

        self._update_banner.show()
        self._update_banner.raise_()

    def _abrir_download(self):
        """Inicia download automático se possível, senão abre browser."""
        if hasattr(self, '_update_zip_url') and self._update_zip_url:
            self._mostrar_progresso_download(self._update_zip_url)
        else:
            abrir_download()

    def _mostrar_progresso_download(self, zip_url: str):
        """Abre janela modal de progresso de download e instala automaticamente."""
        from PySide6.QtWidgets import QDialog, QProgressBar
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Instalando Atualização")
        dialog.setFixedSize(480, 220)
        dialog.setStyleSheet("background-color: #0A1628; border: none;")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        title = QLabel("⬇️  Baixando atualização...")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4FC3F7;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        status_lbl = QLabel("Conectando ao servidor...")
        status_lbl.setStyleSheet("font-size: 13px; color: #78909C;")
        status_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_lbl)

        prog_bar = QProgressBar()
        prog_bar.setFixedHeight(12)
        prog_bar.setRange(0, 100)
        prog_bar.setValue(0)
        prog_bar.setTextVisible(False)
        prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e2a3a;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #3d5afe;
                border-radius: 6px;
            }
        """)
        layout.addWidget(prog_bar)

        pct_lbl = QLabel("0%")
        pct_lbl.setStyleSheet("font-size: 12px; color: #546E7A;")
        pct_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(pct_lbl)

        def on_progress(pct: int, msg: str):
            # Usar invokeMethod ou similar seria melhor para threads, 
            # mas QTimer.singleShot(0, ...) funciona bem aqui.
            QTimer.singleShot(0, lambda: [
                prog_bar.setValue(pct),
                status_lbl.setText(msg),
                pct_lbl.setText(f"{pct}%")
            ])

        def on_success():
            QTimer.singleShot(0, lambda: [
                status_lbl.setText("✅ Instalação pronta! Reiniciando..."),
                status_lbl.setStyleSheet("color: #66BB6A; font-weight: bold;"),
                QTimer.singleShot(2000, self.close) # Fecha o app para o .bat assumir
            ])

        def on_error(msg: str):
            QTimer.singleShot(0, lambda: [
                status_lbl.setText(f"❌ Erro: {msg}"),
                status_lbl.setStyleSheet("color: #EF5350;"),
                QPushButton("OK", dialog, clicked=dialog.reject).pack()
            ])

        baixar_e_instalar(zip_url, on_progress, on_success, on_error)
        dialog.exec()

    def _verificar_expiracao_licenca(self):
        """Verifica se a licença expira em breve e mostra o banner se necessário.
        Executado na thread principal (via QTimer), igual ao DocPopular."""
        try:
            saved_key = self._settings.value("license_key", "")
            print(f"[DEBUG] Iniciando verificação de expiração (Key: {saved_key[:10]}...)")
            info = validar_licenca(saved_key)
            if info is None:
                print("[DEBUG] validar_licenca retornou None")
                return
            dias = info.get("dias_restantes", 999)
            print(f"[DEBUG] Dias restantes calculados: {dias}")
            
            if 0 <= dias <= 3:
                print(f"[DEBUG] Mostrando banner de expiração ({dias} dias)")
                self._mostrar_banner_expiracao(dias)
            else:
                print(f"[DEBUG] Não é necessário mostrar banner (dias > 3)")
        except Exception as e:
            print(f"[DEBUG] Erro na verificação de expiração: {e}")

    def _mostrar_banner_expiracao(self, dias: int):
        """Exibe o banner laranja de aviso de expiração no topo."""
        print(f"[DEBUG] _mostrar_banner_expiracao chamado para {dias} dias")
        
        msg = f"⚠️ SUA LICENÇA EXPIRA EM {dias} DIA(S)! Renove agora para continuar usando." if dias > 0 else "⚠️ SUA LICENÇA EXPIRA HOJE! Renove agora para não perder o acesso."
        self._lbl_license_msg.setText(msg)
        
        self._license_banner.show()
        self._license_banner.raise_()
        print(f"[DEBUG] Banner visível? {self._license_banner.isVisible()} - Geometria: {self._license_banner.geometry()}")

    def _abrir_whatsapp_renovacao(self):
        """Abre o WhatsApp para renovação da licença."""
        import webbrowser
        import urllib.parse
        mid = get_machine_id()
        msg = f"Olá Robinson, minha licença do Ross PDF Editor está vencendo (ID: {mid}) e gostaria de renovar."
        url = f"https://wa.me/5516991080895?text={urllib.parse.quote(msg)}"
        webbrowser.open(url)

    # ══════════════════════════════════════════════════════════
    # Drop Zone
    # ══════════════════════════════════════════════════════════

    def _show_drop_zone(self):
        """Mostra a tela inicial de drop zone."""
        if hasattr(self, 'drop_zone') and self.drop_zone:
            return

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped = self._open_file
        self.drop_zone.btn_open.clicked.connect(self._action_open)
        
        # Centraliza a DropZone no wrapper
        self.wrapper_layout.addStretch(1)
        self.wrapper_layout.addWidget(self.drop_zone, alignment=Qt.AlignCenter)
        self.wrapper_layout.addStretch(1)
        
        self.act_new.setEnabled(False)

    def _hide_drop_zone(self):
        """Esconde a drop zone e mostra as páginas."""
        if hasattr(self, 'drop_zone') and self.drop_zone:
            self.drop_zone.hide()
            
            # Limpa tudo do wrapper exceto a scroll_area
            for i in reversed(range(self.wrapper_layout.count())):
                item = self.wrapper_layout.itemAt(i)
                if item.widget() == self.drop_zone:
                    item.widget().setParent(None)
                elif item.spacerItem():
                    self.wrapper_layout.removeItem(item)

            self.drop_zone.deleteLater()
            self.drop_zone = None
            self.act_new.setEnabled(True)


    # ══════════════════════════════════════════════════════════
    # Ações
    # ══════════════════════════════════════════════════════════

    def _action_open(self):
        if not self._maybe_save_changes():
            return
            
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Arquivo", self._get_last_dir(),
            f"{self.SUPPORTED_ALL};;{self.SUPPORTED_PDF};;{self.SUPPORTED_IMAGES}"
        )
        if path:
            self._open_file(path)

    def _action_new(self):
        """Inicia um novo projeto voltando à tela inicial."""
        if self._maybe_save_changes():
            self._reset_to_initial_state()

    def _reset_to_initial_state(self):
        """Fecha o documento atual e volta para a zona de drop."""
        self.engine.close()
        self.thumbnails.clear()
        self.selected_indices.clear()
        self.is_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        
        if self.pages_layout:
            while self.pages_layout.count():
                item = self.pages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        
        self.scroll_area.hide()
        self._show_drop_zone()
        self._enable_tools(False)
        self.setWindowTitle(self.APP_TITLE)
        self.status.showMessage("Novo projeto iniciado")

    def _maybe_save_changes(self) -> bool:
        """
        Verifica se há alterações e pergunta se o usuário deseja salvar.
        Retorna True se for seguro prosseguir, False se o usuário cancelar.
        """
        if not self.is_dirty:
            return True

        msg = QMessageBox(self)
        msg.setWindowTitle("Salvar Alterações?")
        msg.setText("Existem alterações não salvas. Deseja salvar o trabalho atual antes de prosseguir?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        msg.setButtonText(QMessageBox.Yes, "Sim")
        msg.setButtonText(QMessageBox.No, "Não")
        msg.setButtonText(QMessageBox.Cancel, "Cancelar")
        msg.setDefaultButton(QMessageBox.Yes)
        msg.setIcon(QMessageBox.Question)
        reply = msg.exec()

        if reply == QMessageBox.Yes:
            self._action_save()
            return not self.is_dirty # Se salvou com sucesso, is_dirty será False
        elif reply == QMessageBox.No:
            # Dupla checagem de cancelamento (discarte)
            msg = QMessageBox(self)
            msg.setWindowTitle("Confirmar Descarte")
            msg.setText("Tem certeza que deseja descartar todas as alterações? Todo o trabalho atual será perdido permanentemente.")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setButtonText(QMessageBox.Yes, "Sim")
            msg.setButtonText(QMessageBox.No, "Não")
            msg.setDefaultButton(QMessageBox.No)
            msg.setIcon(QMessageBox.Warning)
            confirm = msg.exec()
            return confirm == QMessageBox.Yes
        else:
            return False

    def _open_file(self, path: str):
        """Abre um PDF ou imagem."""
        ext = Path(path).suffix.lower()
        self._save_last_dir(path)
        try:
            if ext == ".pdf":
                self.engine.close()
                self.engine.open(path)
            else:
                # Se for imagem, criar um PDF novo e inserir como página
                self.engine.close()
                self.engine.new()
                self.engine.insert_image_as_page(path)

            self._hide_drop_zone()
            self._enable_tools(True)
            self.is_dirty = False
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._push_snapshot()  # Snapshot inicial
            self._rebuild_thumbnails()
            self.setWindowTitle(
                f"{self.APP_TITLE} — {Path(path).name}"
            )
            self.status.showMessage(
                f"Aberto: {Path(path).name} — "
                f"{self.engine.page_count} página(s)"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível abrir o arquivo:\n{e}"
            )

    def _action_save(self):
        if self.engine.file_path:
            try:
                self.engine.save()
                self.is_dirty = False
                self.status.showMessage("Documento salvo com sucesso!")
                QMessageBox.information(self, "Sucesso", "Documento Salvo com Sucesso!")
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro ao Salvar", str(e)
                )
        else:
            self._action_save_as()

    def _action_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Como", self._get_last_dir(), self.SUPPORTED_PDF
        )
        if path:
            self._save_last_dir(path)
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            try:
                self.engine.save_as(path)
                self.engine.file_path = path
                self.is_dirty = False
                self.setWindowTitle(
                    f"{self.APP_TITLE} — {Path(path).name}"
                )
                self.status.showMessage(f"Salvo: {Path(path).name}")
                QMessageBox.information(self, "Sucesso", "Documento Salvo com Sucesso!")
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro ao Salvar", str(e)
                )

    def _action_add_pages(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar Páginas", self._get_last_dir(),
            f"{self.SUPPORTED_ALL};;{self.SUPPORTED_PDF};;{self.SUPPORTED_IMAGES}"
        )
        if not paths:
            return

        self._push_snapshot()
        if paths:
            self._save_last_dir(paths[0])

        for path in paths:
            ext = Path(path).suffix.lower()
            try:
                if ext == ".pdf":
                    self.engine.insert_pdf_pages(path)
                else:
                    self.engine.insert_image_as_page(path)
            except Exception as e:
                QMessageBox.warning(
                    self, "Aviso",
                    f"Erro ao inserir arquivo {Path(path).name}:\n{e}"
                )

        self.is_dirty = True
        self._rebuild_thumbnails()
        self.status.showMessage(
            f"{len(paths)} arquivo(s) adicionado(s) — "
            f"Total: {self.engine.page_count} página(s)"
        )

    def _action_add_blank(self):
        self._push_snapshot()
        self.engine.insert_blank_page()
        self.is_dirty = True
        self._rebuild_thumbnails()
        self.status.showMessage(
            f"Página em branco adicionada — "
            f"Total: {self.engine.page_count} página(s)"
        )

    def _action_delete(self):
        if not self.selected_indices:
            self.status.showMessage("Selecione uma ou mais páginas para excluir.")
            return

        count = len(self.selected_indices)
        if self.engine.page_count - count < 1:
            QMessageBox.warning(
                self, "Aviso",
                "O documento deve ter pelo menos 1 página."
            )
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar Exclusão")
        msg.setText(f"Deseja excluir {count} página(s)?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setButtonText(QMessageBox.Yes, "Sim")
        msg.setButtonText(QMessageBox.No, "Não")
        msg.setDefaultButton(QMessageBox.No)
        msg.setIcon(QMessageBox.Question)
        reply = msg.exec()
        if reply == QMessageBox.Yes:
            self._push_snapshot()
            self.engine.delete_pages(list(self.selected_indices))
            self.selected_indices.clear()
            self.is_dirty = True
            self._rebuild_thumbnails()
            self.status.showMessage(
                f"{count} página(s) excluída(s) — "
                f"Total: {self.engine.page_count} página(s)"
            )

    def _action_crop(self):
        """Abre o diálogo de recorte para a página selecionada."""
        if len(self.selected_indices) != 1:
            self.status.showMessage(
                "Selecione exatamente 1 página para recortar."
            )
            return

        idx = list(self.selected_indices)[0]
        png_data = self.engine.render_page(idx, zoom=2.0)
        page_size = self.engine.get_page_size(idx)

        dialog = CropDialog(png_data, page_size, self)
        if dialog.exec() == CropDialog.Accepted:
            crop_rect = dialog.get_crop_rect()
            if crop_rect:
                self._push_snapshot()
                self.engine.crop_page(idx, *crop_rect)
                self.is_dirty = True
                self._rebuild_thumbnails()
                self.status.showMessage(
                    f"Página {idx + 1} recortada com sucesso!"
                )

    # ══════════════════════════════════════════════════════════
    # Thumbnails
    # ══════════════════════════════════════════════════════════

    def _rebuild_thumbnails(self):
        """Reconstrói todas as miniaturas das páginas."""
        # Limpar layout existente
        self.thumbnails.clear()
        self.selected_indices.clear()

        if self.pages_layout:
            while self.pages_layout.count():
                item = self.pages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        # Recriar container
        self.pages_container = QWidget()
        self.pages_container.setStyleSheet("background-color: #0f1024;")
        self.pages_layout = QGridLayout(self.pages_container)
        self.pages_layout.setContentsMargins(24, 24, 24, 24)
        self.pages_layout.setSpacing(16)
        self.pages_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        cols = max(1, (self.width() - 80) // 220)

        for i in range(self.engine.page_count):
            png_data = self.engine.render_page(i, zoom=1.0)
            thumb = PageThumbnail(i, png_data)
            thumb.clicked.connect(self._on_page_clicked)
            thumb.delete_requested.connect(self._on_page_delete)
            thumb.duplicate_requested.connect(self._on_page_duplicate)
            thumb.double_clicked.connect(self._on_page_double_click)
            thumb.drop_received.connect(self._on_page_drop)

            row = i // cols
            col = i % cols
            self.pages_layout.addWidget(thumb, row, col, Qt.AlignCenter)
            self.thumbnails.append(thumb)

        self.scroll_area.setWidget(self.pages_container)
        self.scroll_area.show()
        self._update_actions()

    def _on_page_clicked(self, index: int):
        """Gerencia seleção de páginas (Ctrl para múltipla)."""
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.ControlModifier:
            # Toggle seleção
            if index in self.selected_indices:
                self.selected_indices.discard(index)
            else:
                self.selected_indices.add(index)
        else:
            # Seleção única
            self.selected_indices.clear()
            self.selected_indices.add(index)

        # Atualizar visual
        for thumb in self.thumbnails:
            thumb.selected = thumb.page_index in self.selected_indices

        self._update_actions()
        count = len(self.selected_indices)
        if count == 1:
            idx = list(self.selected_indices)[0]
            self.status.showMessage(f"Página {idx + 1} selecionada")
        elif count > 1:
            self.status.showMessage(f"{count} páginas selecionadas")

    def _on_page_delete(self, index: int):
        """Excluir uma página específica (via botão X no thumbnail)."""
        if self.engine.page_count <= 1:
            QMessageBox.warning(
                self, "Aviso",
                "Não é possível excluir a única página do documento."
            )
            return

        self._push_snapshot()
        self.engine.delete_page(index)
        self.selected_indices.clear()
        self.is_dirty = True
        self._rebuild_thumbnails()
        self.status.showMessage(
            f"Página {index + 1} excluída — "
            f"Total: {self.engine.page_count} página(s)"
        )

    def _on_page_duplicate(self, index: int):
        """Duplicar uma página específica (via botão + no thumbnail)."""
        self._push_snapshot()
        self.engine.duplicate_page(index)
        self.selected_indices.clear()
        self.selected_indices.add(index + 1)  # Seleciona a nova cópia
        self.is_dirty = True
        self._rebuild_thumbnails()
        self.status.showMessage(
            f"Página {index + 1} duplicada — "
            f"Total: {self.engine.page_count} página(s)"
        )

    def _on_page_drop(self, from_index: int, to_index: int):
        """Trocar a posição de duas páginas (Swap via drag & drop)."""
        if from_index == to_index:
            return

        self._push_snapshot()
        self.engine.swap_pages(from_index, to_index)
        self.selected_indices.clear()
        self.is_dirty = True
        self._rebuild_thumbnails()
        self.status.showMessage(
            f"Página {from_index + 1} trocada com Página {to_index + 1}"
        )

    def _on_page_double_click(self, index: int):
        """Duplo clique abre o crop da página."""
        self.selected_indices = {index}
        for thumb in self.thumbnails:
            thumb.selected = thumb.page_index in self.selected_indices
        self._action_crop()

    # ══════════════════════════════════════════════════════════
    # Estado & Drag/Drop
    # ══════════════════════════════════════════════════════════

    def _enable_tools(self, enabled: bool):
        self.act_new.setEnabled(enabled)
        self.act_save.setEnabled(enabled)
        self.act_save_as.setEnabled(enabled)
        self.act_add_pages.setEnabled(enabled)
        self.act_add_blank.setEnabled(enabled)
        self.act_undo.setEnabled(len(self._undo_stack) > 0)
        self.act_redo.setEnabled(len(self._redo_stack) > 0)
        self._update_actions()

    def _update_actions(self):
        has_selection = len(self.selected_indices) > 0
        self.act_delete.setEnabled(has_selection)
        self.act_crop.setEnabled(len(self.selected_indices) == 1)
        self.act_undo.setEnabled(len(self._undo_stack) > 0)
        self.act_redo.setEnabled(len(self._redo_stack) > 0)

    # ══════════════════════════════════════════════════════════
    # Undo / Redo (Snapshot)
    # ══════════════════════════════════════════════════════════

    def _push_snapshot(self):
        """Salva o estado atual do documento para o histórico de undo."""
        if self.engine.doc is None:
            return
        try:
            snapshot = self.engine.doc.tobytes(garbage=0, deflate=False)
            self._undo_stack.append(snapshot)
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
            self._update_actions()
        except Exception:
            pass

    def _action_undo(self):
        """Desfaz a última ação restaurando o snapshot anterior."""
        if not self._undo_stack or self.engine.doc is None:
            return
        # Salvar estado atual para redo
        try:
            current = self.engine.doc.tobytes(garbage=0, deflate=False)
            self._redo_stack.append(current)
        except Exception:
            pass
        # Restaurar snapshot anterior
        snapshot = self._undo_stack.pop()
        self._restore_from_snapshot(snapshot)
        self.is_dirty = True
        self.status.showMessage("Ação desfeita (Ctrl+Z)")

    def _action_redo(self):
        """Refaz a ação que foi desfeita."""
        if not self._redo_stack or self.engine.doc is None:
            return
        # Salvar estado atual para undo
        try:
            current = self.engine.doc.tobytes(garbage=0, deflate=False)
            self._undo_stack.append(current)
        except Exception:
            pass
        # Restaurar snapshot do redo
        snapshot = self._redo_stack.pop()
        self._restore_from_snapshot(snapshot)
        self.is_dirty = True
        self.status.showMessage("Ação refeita (Ctrl+Y)")

    def _restore_from_snapshot(self, snapshot: bytes):
        """Restaura o documento a partir de um snapshot em bytes."""
        import fitz
        file_path = self.engine.file_path
        self.engine.doc.close()
        self.engine.doc = fitz.open("pdf", snapshot)
        self.engine.file_path = file_path
        self.selected_indices.clear()
        self._rebuild_thumbnails()

    # ══════════════════════════════════════════════════════════
    # Persistência de Pasta (QSettings)
    # ══════════════════════════════════════════════════════════

    def _get_last_dir(self) -> str:
        """Retorna a última pasta visitada ou a pasta de Documentos."""
        last = self._settings.value("last_directory", "")
        if last and os.path.isdir(last):
            return last
        # Fallback para pasta de Documentos do Windows
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        return docs if docs else ""

    def _save_last_dir(self, file_path: str):
        """Salva a pasta do arquivo para uso futuro."""
        folder = str(Path(file_path).parent)
        self._settings.setValue("last_directory", folder)

    # ══════════════════════════════════════════════════════════
    # Drag / Drop
    # ══════════════════════════════════════════════════════════

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return

        first_path = urls[0].toLocalFile()
        first_ext = Path(first_path).suffix.lower()

        # Se não tem documento aberto, abrir o primeiro arquivo
        if not self.engine.doc:
            self._open_file(first_path)
            urls = urls[1:]  # Processar restantes como inserção

        # Inserir os demais
        for url in urls:
            path = url.toLocalFile()
            ext = Path(path).suffix.lower()
            try:
                if ext == ".pdf":
                    self.engine.insert_pdf_pages(path)
                elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
                    self.engine.insert_image_as_page(path)
            except Exception as e:
                self.status.showMessage(f"Erro ao inserir: {e}")

        if self.engine.doc:
            self.is_dirty = True
            self._rebuild_thumbnails()
            self.status.showMessage(
                f"Arquivo(s) adicionado(s) — "
                f"Total: {self.engine.page_count} página(s)"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalcular grid ao redimensionar se houver páginas
        if self.thumbnails and self.pages_layout:
            cols = max(1, (self.width() - 80) // 220)
            for i, thumb in enumerate(self.thumbnails):
                self.pages_layout.removeWidget(thumb)
                row = i // cols
                col = i % cols
                self.pages_layout.addWidget(thumb, row, col, Qt.AlignCenter)

    def closeEvent(self, event):
        # 1. Primeiro lidar com salvamento se necessário
        if not self._maybe_save_changes():
            event.ignore()
            return
            
        # 2. Confirmação geral de saída
        msg = QMessageBox(self)
        msg.setWindowTitle("Sair do Ross PDF Editor")
        msg.setText("Deseja realmente fechar o aplicativo?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setButtonText(QMessageBox.Yes, "Sim")
        msg.setButtonText(QMessageBox.No, "Não")
        msg.setDefaultButton(QMessageBox.No)
        msg.setIcon(QMessageBox.Question)
        
        if msg.exec() == QMessageBox.Yes:
            self.engine.close()
            event.accept()
        else:
            event.ignore()
