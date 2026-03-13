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

    def scan_with_dialog(self, callback: Callable[[Optional[bytes], Optional[str]], None], device_name: Optional[str] = None):
        """
        Inicia escaneamento. 
        Se device_name for fornecido, tenta conectar diretamente.
        Caso contrário, abre o diálogo de seleção/aquisição.
        """
        if not self.is_available():
            callback(None, "Bibliotecas pywin32 não instaladas.")
            return

        def task():
            png_bytes = None
            error_msg = None
            try:
                pythoncom.CoInitialize()
                try:
                    dialog = win32com.client.Dispatch("WIA.CommonDialog")
                    
                    image_file = None
                    if device_name:
                        # Tenta conectar ao scanner específico usando a estratégia do DocPopular
                        manager = win32com.client.Dispatch("WIA.DeviceManager")
                        target_device = None
                        for dev_info in manager.DeviceInfos:
                            if dev_info.Properties("Name").Value == device_name:
                                target_device = dev_info.Connect()
                                break
                        
                        if target_device:
                            if target_device.Items.Count > 0:
                                # Usar ShowTransfer fornece diálogo de progresso nativo do Windows
                                # Isso evita o hang visual "Aguardando resposta do scanner"
                                try:
                                    image_file = dialog.ShowTransfer(target_device.Items[1], "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}", False)
                                except Exception as e:
                                    # Se falhar a transferência direta, o fallback abaixo tentará abrir o diálogo
                                    pass
                            else:
                                error_msg = "O scanner não possui itens de digitalização."
                        else:
                            # Se não achou pelo nome salvo, limpa para cair no fallback de diálogo de seleção
                            device_name = None
                    
                    # Fallback para diálogo se não houver device_name ou se falhou
                    if not image_file and not error_msg:
                        image_file = dialog.ShowAcquireImage(
                            1, 1, 4,
                            "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}",
                            False, True, False
                        )

                    if image_file:
                        data = bytes(image_file.FileData.BinaryData)
                        img = Image.open(io.BytesIO(data))
                        img = img.convert("RGB")
                        
                        buffer = io.BytesIO()
                        img.save(buffer, format="PNG", optimize=True)
                        png_bytes = buffer.getvalue()
                    elif not error_msg:
                        error_msg = "Usuário cancelou o escaneamento."
                except Exception as e:
                    error_msg = str(e)
                    if "0x80210015" in error_msg:
                        error_msg = "Nenhum Scanner Instalado ou Desconectado."
                    elif "0x8021001A" in error_msg:
                        error_msg = "Scanner ocupado ou em uso."
                finally:
                    pythoncom.CoUninitialize()
            except Exception as e:
                error_msg = f"Erro crítico de sistema: {e}"
            
            callback(png_bytes, error_msg)

        thread = threading.Thread(target=task, daemon=True)
        thread.start()
