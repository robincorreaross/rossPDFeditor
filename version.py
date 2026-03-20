"""
Ross PDF Editor - Version & Supabase Configuration.
"""

# Versão atual do aplicativo (Semântica: MAJOR.MINOR.PATCH)
APP_VERSION = "1.8.1"

# Configurações do Supabase para Licenciamento
SUPABASE_URL = "https://iyyfyhefllmlhauezhur.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5eWZ5aGVmbGxtbGhhdWV6aHVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyNzIzNzcsImV4cCI6MjA4Nzg0ODM3N30.vbURdlNe-mlZoe1Fkpvc2pwRRFQgru6qb00ADra8jVE"
SUPABASE_TABLE = "ross_pdf_editor"

# --- Configurações de Auto-Update (Ross Auto Update Skill) ---
GITHUB_USER = "robincorreaross"
GITHUB_REPO = "rossPDFeditor"
APP_NAME = "RossPDFEditor"

# URL do version.json no GitHub (branch main)
UPDATE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"

# URL para baixar o ZIP da release mais recente
DOWNLOAD_ZIP_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest/download/{APP_NAME}.zip"

# Página da release (fallback / manual)
DOWNLOAD_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
