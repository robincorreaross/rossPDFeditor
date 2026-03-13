"""
ScannerEngine - Interface com scanners via WIA (Windows Image Acquisition).
Versão avançada com suporte a listagem e seleção de dispositivos.
"""

import io
import threading
from typing import Optional, Callable, List
from PIL import Image

try:
    import win32com.client
    import pythoncom
except ImportError:
    win32com = None
    pythoncom = None


class ScannerEngine:
    def __init__(self):
        pass

    def is_available(self) -> bool:
        return win32com is not None and pythoncom is not None

    def list_scanners(self) -> List[str]:
        """Lista nomes de scanners disponíveis."""
        if not self.is_available():
            return []
        
        scanners = []
        pythoncom.CoInitialize()
        try:
            wia = win32com.client.Dispatch("WIA.DeviceManager")
            for device_info in wia.DeviceInfos:
                if device_info.Type == 1: # Scanner
                    name = device_info.Properties("Name").Value
                    scanners.append(name)
        except Exception:
            pass
        finally:
            pythoncom.CoUninitialize()
        return scanners

    def scan_with_dialog(self, callback: Callable[[Optional[bytes], Optional[str]], None], status_callback: Callable[[str], None], device_name: Optional[str] = None):
        """
        Inicia escaneamento. 
        Se device_name for fornecido, tenta conectar diretamente.
        Caso contrário, abre o diálogo de seleção/aquisição.
        """
        if not self.is_available():
            callback(None, "Bibliotecas pywin32 não instaladas.")
            return

        def task():
            import datetime
            import os
            from pathlib import Path

            log_file_path = Path.cwd() / "scanner_debug.log"
            debug_png_path = Path.cwd() / "debug_scanner.png"
            
            def cleanup_old_files():
                """Remove arquivos de log ou dumps de dias anteriores"""
                try:
                    for p in [log_file_path, debug_png_path]:
                        if p.exists():
                            mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
                            if mtime.date() < datetime.date.today():
                                p.unlink()
                except Exception:
                    pass

            cleanup_old_files()

            def log_step(msg: str):
                """Mostra na UI e salva no arquivo local"""
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_line = f"[{timestamp}] {msg}"
                try:
                    with open(log_file_path, "a", encoding="utf-8") as f:
                        f.write(log_line + "\n")
                except Exception:
                    pass
                # Envia para a UI
                status_callback(msg)

            log_step("=== NOVO ESCANEAMENTO INICIADO (v1.4.3) ===")
            png_bytes = None
            error_msg = None
            try:
                log_step("1. Chamando pythoncom.CoInitialize()...")
                pythoncom.CoInitialize()
                log_step("1. CoInitialize concluído.")
                
                try:
                    nonlocal device_name
                    log_step("2. Instanciando WIA.CommonDialog...")
                    dialog = win32com.client.Dispatch("WIA.CommonDialog")
                    log_step("2. Dialog instanciado.")
                    
                    image_file = None
                    if device_name:
                        log_step(f"3. Tentando conexão nomeada: '{device_name}'...")
                        log_step("3.1. Dispatching WIA.DeviceManager...")
                        manager = win32com.client.Dispatch("WIA.DeviceManager")
                        target_device = None
                        
                        log_step("3.2. Iterando DeviceInfos...")
                        for dev_info in manager.DeviceInfos:
                            if dev_info.Properties("Name").Value == device_name:
                                log_step(f"3.3. Dispositivo '{device_name}' encontrado. Chamando Connect()...")
                                target_device = dev_info.Connect()
                                log_step("3.3. Connect() finalizado.")
                                break
                        
                        if target_device:
                            log_step("4. Scanner conectado. Verificando Items...")
                            scan_item = None
                            if target_device.Items.Count > 0:
                                log_step(f"4.1. Encontrados {target_device.Items.Count} itens.")
                                for i in range(1, target_device.Items.Count + 1):
                                    try:
                                        log_step(f"4.2. Avaliando Item {i}...")
                                        item = target_device.Items[i]
                                        item.Properties("Horizontal Resolution")
                                        scan_item = item
                                        log_step(f"4.2. Item {i} eleito pela prop de Resolução.")
                                        break
                                    except Exception as e:
                                        log_step(f"4.2. Item {i} falhou na prop de resolução: {e}")
                                        continue
                                
                                if not scan_item:
                                    log_step("4.3. Fallback: Forçando escolha do Item 1.")
                                    try:
                                        scan_item = target_device.Items[1]
                                    except Exception as e:
                                        log_step(f"4.3. Falha ao forçar Item 1: {e}")
                            
                            if scan_item:
                                log_step("5. Injetando 200 DPI nas propriedades...")
                                try:
                                    scan_item.Properties("Horizontal Resolution").Value = 200
                                    scan_item.Properties("Vertical Resolution").Value = 200
                                    log_step("5. DPI de 200 injetado com sucesso.")
                                except Exception as e:
                                    log_step(f"5. AVISO: Falha ao injetar DPI: {e} (Continuando...)")

                                log_step("6. Iniciando TRANSFERÊNCIA DA IMAGEM [PONTO DE ENFORCAMENTO POTENCIAL]...")
                                try:
                                    image_file = scan_item.Transfer("{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}")
                                    log_step("6. TRANSFERÊNCIA DA IMAGEM CONCLUÍDA com sucesso.")
                                except Exception as e:
                                    error_msg = str(e)
                                    log_step(f"6. ERRO NA TRANSFERÊNCIA: {error_msg}")
                                    if "0x8021001A" in error_msg:
                                        error_msg = "Scanner ocupado ou em uso por outro programa (0x8021001A)."
                                    elif "0x80210015" in error_msg:
                                        error_msg = "Scanner offline ou desconectado (0x80210015)."
                            else:
                                error_msg = "O scanner não possui itens de digitalização compatíveis."
                                log_step(f"X. Abortando: {error_msg}")
                        else:
                            log_step(f"3.4. Dispositivo '{device_name}' NÃO conectado (Caindo em Fallback).")
                            device_name = None
                    
                    if not image_file and not error_msg:
                        log_step("7. Fallback: Chamando diálogo visual ShowAcquireImage()... [PONTO DE ENFORCAMENTO POTENCIAL]")
                        image_file = dialog.ShowAcquireImage(
                            1, 1, 4,
                            "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}",
                            False, True, False
                        )
                        log_step("7. ShowAcquireImage() concluído.")

                    if image_file:
                        log_step("8. Extraindo bits binários do image_file...")
                        data = bytes(image_file.FileData.BinaryData)
                        log_step("8.1. Convertendo bytes para PIL Image (RGB)...")
                        img = Image.open(io.BytesIO(data))
                        img = img.convert("RGB")
                        
                        log_step("8.2. Otimizando exportação em memória para formato PNG...")
                        buffer = io.BytesIO()
                        img.save(buffer, format="PNG", optimize=True)
                        png_bytes = buffer.getvalue()
                        log_step("9. Bytes PNG processados com sucesso. Fluxo concluído.")
                        
                        try:
                            debug_path = Path.cwd() / "debug_scanner.png"
                            with open(debug_path, "wb") as f:
                                f.write(png_bytes)
                            log_step(f"DUMP: Imagem bruta salva fisicamente em {debug_path}")
                        except Exception as e:
                            log_step(f"DUMP AVISO: não foi possivel salvar png de debug: {e}")
                    elif not error_msg:
                        error_msg = "Usuário cancelou o escaneamento o diálogo nativo."
                        log_step("X. Processo cancelado.")
                except Exception as e:
                    error_msg = str(e)
                    log_step(f"ERRO DE EXCEÇÃO WIA GENÉRICA: {error_msg}")
                    if "0x80210015" in error_msg:
                        error_msg = "Nenhum Scanner Instalado ou Desconectado."
                    elif "0x8021001A" in error_msg:
                        error_msg = "Scanner ocupado ou em uso."
                finally:
                    log_step("10. Desempacotando COM (CoUninitialize)...")
                    pythoncom.CoUninitialize()
                    log_step("10. CoUninitialize concluído.")
            except Exception as e:
                error_msg = f"Erro crítico de sistema na Thead: {e}"
                try:
                    log_step(f"CRASH: {error_msg}")
                except Exception:
                    pass
            
            callback(png_bytes, error_msg)

        thread = threading.Thread(target=task, daemon=True)
        thread.start()
