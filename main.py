"""
Ross PDF Editor – Ponto de entrada da aplicação.

Verifica licença antes de abrir a janela principal.
Inicia o aplicativo desktop com PySide6.
"""

import sys
import os
from pathlib import Path

# Garantir que o diretório raiz do projeto esteja no path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt

from src.core.license import LicenseError, get_machine_id, validar_licenca


def _verificar_licenca() -> tuple:
    """
    Retorna (valida, mensagem_erro).
    Tenta validar online primeiro (via ID da máquina), depois offline (via chave salva).
    """
    try:
        res = validar_licenca("")
        return res.get("valido", False), ""
    except LicenseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Erro inesperado na validação: {e}"


def main():
    # High DPI
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Ross PDF Editor")
    app.setOrganizationName("Ross")

    # Fonte padrão
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Estilo global
    app.setStyle("Fusion")

    valida, msg_erro = _verificar_licenca()

    if valida:
        # Licença OK → abre o app diretamente
        from src.ui.main_window import MainWindow
        window = MainWindow()
        window.showMaximized()
    else:
        # Sem licença ou erro → abre tela de ativação
        from src.ui.license_screen import LicenseScreen

        def _abrir_app():
            from src.ui.main_window import MainWindow
            window = MainWindow()
            window.showMaximized()
            window.show()

        # Determina o estado baseado na mensagem de erro
        estado = "padrao"
        if "novo" in msg_erro.lower():
            estado = "novo"
        elif "expirou" in msg_erro.lower():
            estado = "expirado"
        elif "inativa" in msg_erro.lower() or "inativo" in msg_erro.lower():
            estado = "inativo"

        screen = LicenseScreen(
            on_activate=_abrir_app,
            estado=estado,
            msg_extra=msg_erro if estado == "padrao" else ""
        )
        screen.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
