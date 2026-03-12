@echo off
echo ============================================================
echo   Ross PDF Editor - Build Completo (PyInstaller + Instalador)
echo ============================================================

REM Tenta fechar o app e o compilador se estiverem abertos
taskkill /F /IM RossPDFEditor.exe /T >nul 2>&1
taskkill /F /IM ISCC.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

REM Limpa a pasta installer para evitar erros de lock
if exist installer (
    echo [+] Limpando pasta installer...
    del /q installer\* >nul 2>&1
) else (
    mkdir installer
)

REM Extrai a versao do version.py usando python
for /f %%I in ('python -c "from version import APP_VERSION; print(APP_VERSION)"') do set APP_VERSION=%%I
echo [+] Versao detectada: v%APP_VERSION%
echo.

echo [1/2] Compilando o aplicativo com PyInstaller...
python -m PyInstaller --clean --noconfirm ross_pdf_editor.spec
if errorlevel 1 (
    echo ERRO: falha ao gerar o aplicativo.
    pause & exit /b 1
)
echo     OK - dist\RossPDFEditor\

echo.
echo [2/2] Gerando instalador com Inno Setup...
python _gerar_iss.py

REM Procura o compilador do Inno Setup
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
    echo AVISO: Inno Setup nao encontrado.
    echo Instale em: https://jrsoftware.org/isdl.php
    echo Depois execute novamente ou compile manualmente: RossPDFEditor.iss
    pause & exit /b 0
)

"%ISCC%" RossPDFEditor.iss
if errorlevel 1 (
    echo ERRO: falha ao gerar o instalador.
    pause & exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETO!
echo ============================================================
echo.
echo  Instalador:  installer\RossPDFEditor_Setup_v%APP_VERSION%.exe
echo.
echo ============================================================
pause
