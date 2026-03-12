"""
updater.py - Verificador e instalador automático de atualizações do Ross PDF Editor.

Fluxo de auto-update no Windows:
 1. Baixa RossPDFEditor.zip para %TEMP%
 2. Extrai para %TEMP%/ross_update/
 3. Cria update_helper.bat que aguarda o app fechar e copia os arquivos
 4. Lança o bat em background e fecha o app atual
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
import zipfile
from pathlib import Path
from typing import Callable, List, Optional
from urllib import request
from urllib.error import URLError
from urllib.request import urlretrieve

from version import APP_VERSION, DOWNLOAD_URL, DOWNLOAD_ZIP_URL, UPDATE_URL, APP_NAME


# ─── Comparação de versão ─────────────────────────────────────────────────────

def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


# ─── Verificação remota ───────────────────────────────────────────────────────

def verificar_atualizacao(
    on_update_available: Callable[[str, List[str], bool, str], None],
    timeout: int = 6,
) -> None:
    """
    Verifica atualizações em background.
    Chama on_update_available(nova_versao, changelog, obrigatoria, download_zip_url) se houver update.
    """
    def _check() -> None:
        try:
            req = request.Request(
                UPDATE_URL,
                headers={"User-Agent": f"RossPDFEditor/{APP_VERSION}"},
            )
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())

            remote_version: str = data.get("version", "0.0.0")
            changelog: List[str] = data.get("changelog", [])
            mandatory: bool = bool(data.get("mandatory", False))
            zip_url: str = data.get("download_zip_url", DOWNLOAD_ZIP_URL)

            if _parse_version(remote_version) > _parse_version(APP_VERSION):
                on_update_available(remote_version, changelog, mandatory, zip_url)

        except (URLError, OSError, json.JSONDecodeError, Exception):
            pass  # Silencioso: sem internet, servidor fora, etc.

    threading.Thread(target=_check, daemon=True).start()


def abrir_download() -> None:
    """Abre o navegador na página de download."""
    webbrowser.open(DOWNLOAD_URL)


# ─── Download + Instalação automática ────────────────────────────────────────

def get_app_dir() -> Path:
    """Retorna o diretório onde o executável do app está instalado."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def baixar_e_instalar(
    zip_url: str,
    on_progress: Callable[[int, str], None],
    on_success: Callable[[], None],
    on_error: Callable[[str], None],
) -> None:
    """
    Baixa o ZIP da nova versão, extrai e substitui os arquivos do app.
    Tudo em background. Callbacks são chamados na thread de UI via after().

    Args:
        zip_url: URL do ZIP para download
        on_progress: chamado com (percentual 0-100, mensagem)
        on_success: chamado quando concluído com sucesso
        on_error: chamado com mensagem de erro em caso de falha
    """
    def _run() -> None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="ross_update_"))
        zip_path = tmp_dir / f"{APP_NAME}.zip"
        extract_dir = tmp_dir / "extracted"

        try:
            # ── 1. Download ───────────────────────────────────────────────────
            on_progress(5, "Conectando ao servidor...")

            def report_hook(count: int, block_size: int, total: int) -> None:
                if total > 0:
                    pct = min(int(count * block_size * 60 / total), 60)
                    mb_done = count * block_size / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    on_progress(5 + pct, f"Baixando... {mb_done:.1f} / {mb_total:.1f} MB")

            urlretrieve(zip_url, zip_path, reporthook=report_hook)
            on_progress(65, "Download concluído. Extraindo arquivos...")

            # ── 2. Extração ───────────────────────────────────────────────────
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            on_progress(80, "Preparando instalação...")

            # Encontra a pasta raiz dentro do ZIP (pode ser FarmaPop_IA/ ou .)
            contents = list(extract_dir.iterdir())
            if len(contents) == 1 and contents[0].is_dir():
                source_dir = contents[0]
            else:
                source_dir = extract_dir

            # ── 3. Cria o bat helper ──────────────────────────────────────────
            app_dir = get_app_dir()
            app_exe = app_dir / f"{APP_NAME}.exe"
            bat_path = tmp_dir / "update_helper.bat"

            bat_content = f"""@echo off
title Ross PDF Editor - Instalando Atualizacao...
echo Aguardando o aplicativo fechar...
timeout /t 3 /nobreak >nul

echo Instalando nova versao...
robocopy "{source_dir}" "{app_dir}" /E /IS /IT /IM /R:3 /W:1 >nul 2>&1
if errorlevel 8 (
    echo ERRO ao copiar arquivos. Tente manualmente.
    pause
    exit /b 1
)

echo Limpando arquivos temporarios...
rd /s /q "{tmp_dir}" >nul 2>&1

echo Reiniciando o aplicativo...
start "" "{app_exe}"
exit
"""
            bat_path.write_text(bat_content, encoding="utf-8")
            on_progress(95, "Aplicando atualização...")

            # ── 4. Lança o bat e fecha o app ──────────────────────────────────
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True,
            )

            on_progress(100, "Reiniciando...")
            on_success()

        except Exception as exc:
            # Limpa temporários em caso de erro
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            on_error(str(exc))

    threading.Thread(target=_run, daemon=True).start()
