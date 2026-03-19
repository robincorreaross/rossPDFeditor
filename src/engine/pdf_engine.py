"""
Ross PDF Editor - Motor de manipulação de PDFs.

Usa PyMuPDF (fitz) para manipulação rápida e precisa de PDFs:
- Carregar / renderizar páginas como thumbnails
- Remover páginas
- Inserir páginas de outro PDF
- Inserir imagens como novas páginas
- Recortar (crop) páginas com CropBox real
- Salvar o resultado final
"""

import fitz  # PyMuPDF
import os
import uuid
from pathlib import Path
from typing import Optional


class PDFEngine:
    """Motor principal para manipulação de documentos PDF."""

    def __init__(self):
        self.doc: Optional[fitz.Document] = None
        self.file_path: Optional[str] = None

    # ── Carregar / Criar ─────────────────────────────────────────

    def open(self, path: str) -> int:
        """Abre um PDF e retorna a quantidade de páginas."""
        self.doc = fitz.open(path)
        self.file_path = path
        return len(self.doc)

    def new(self):
        """Cria um documento vazio."""
        self.doc = fitz.open()
        self.file_path = None

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
            self.file_path = None

    @property
    def page_count(self) -> int:
        return len(self.doc) if self.doc else 0

    # ── Renderização ─────────────────────────────────────────────

    def render_page(self, page_index: int, zoom: float = 1.0) -> bytes:
        """
        Renderiza uma página como imagem PNG e retorna os bytes.
        `zoom` controla a qualidade (1.0 = 72dpi, 2.0 = 144dpi).
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        page = self.doc[page_index]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")

    def get_page_pixmap(self, page_index: int, zoom: float = 1.0):
        """
        Retorna a página renderizada diretamente como um objeto QPixmap do PySide6.
        Ideal para visualização em alta resolução.
        """
        from PySide6.QtGui import QImage, QPixmap
        png_bytes = self.render_page(page_index, zoom)
        
        image = QImage()
        image.loadFromData(png_bytes)
        return QPixmap.fromImage(image)

    def get_page_size(self, page_index: int) -> tuple:
        """Retorna (width, height) da página em pontos."""
        page = self.doc[page_index]
        rect = page.rect
        return (rect.width, rect.height)

    # ── Excluir Páginas ──────────────────────────────────────────

    def delete_page(self, page_index: int):
        """Remove uma página pelo índice."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        self.doc.delete_page(page_index)

    def delete_pages(self, indices: list[int]):
        """Remove múltiplas páginas (índices em ordem decrescente)."""
        for idx in sorted(indices, reverse=True):
            self.delete_page(idx)

    # ── Inserir Páginas ──────────────────────────────────────────

    def insert_pdf_pages(self, pdf_path: str, after_index: int = -1):
        """
        Insere todas as páginas de outro PDF após `after_index`.
        Se after_index == -1, insere no final.
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        src = fitz.open(pdf_path)
        insert_at = after_index + 1 if after_index >= 0 else self.page_count
        self.doc.insert_pdf(src, start_at=insert_at)
        src.close()

    def insert_image_as_page(self, image_path: str, after_index: int = -1):
        """
        Insere uma imagem (JPG, PNG, etc.) como uma nova página do PDF.
        A página é dimensionada para caber a imagem.
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")

        img = fitz.open(image_path)
        # Converter imagem para PDF de 1 página
        pdf_bytes = img.convert_to_pdf()
        img.close()

        img_pdf = fitz.open("pdf", pdf_bytes)
        insert_at = after_index + 1 if after_index >= 0 else self.page_count
        self.doc.insert_pdf(img_pdf, start_at=insert_at)
        img_pdf.close()

    def insert_image_bytes(self, image_bytes: bytes, after_index: int = -1):
        """Insere imagem vinda de bytes (PNG/JPG) como nova página."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")

        try:
            img = fitz.open("png", image_bytes) # Assume PNG mas fitz detecta
            pdf_bytes = img.convert_to_pdf()
            img.close()

            img_pdf = fitz.open("pdf", pdf_bytes)
            insert_at = after_index + 1 if after_index >= 0 else self.page_count
            self.doc.insert_pdf(img_pdf, start_at=insert_at)
            img_pdf.close()
        except Exception as e:
            raise RuntimeError(f"Falha ao injetar image_bytes ({len(image_bytes)} bytes) no documento: {e}")

    def insert_blank_page(self, after_index: int = -1,
                          width: float = 595, height: float = 842):
        """Insere uma página em branco (A4 por padrão) após after_index."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        insert_at = after_index + 1 if after_index >= 0 else self.page_count
        self.doc.new_page(pno=insert_at, width=width, height=height)

    # ── Recortar Páginas (Crop real) ─────────────────────────────

    def crop_page(self, page_index: int, x0: float, y0: float,
                  x1: float, y1: float):
        """
        Aplica um recorte REAL na página, alterando o CropBox.
        Coordenadas em pontos (1 ponto = 1/72 polegada).
        Lida com páginas rotacionadas convertendo as coordenadas.
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        page = self.doc[page_index]
        
        # O CropDialog envia coordenadas baseadas na visualização ATUAL (com rotação e crop).
        # set_cropbox exige coordenadas relativas à página ORIGINAL (MediaBox).
        # Primeiro desfazemos a rotação e depois somamos o top-left do CropBox atual.
        rect_view = fitz.Rect(x0, y0, x1, y1)
        rect_derotated = rect_view * page.derotation_matrix
        
        # O CropBox atual define a origem da visualização que foi usada no diálogo.
        cb = page.cropbox
        rect_original = fitz.Rect(
            rect_derotated.x0 + cb.x0,
            rect_derotated.y0 + cb.y0,
            rect_derotated.x1 + cb.x0,
            rect_derotated.y1 + cb.y0
        )
        
        page.set_cropbox(rect_original)

    # ── Rotacionar Páginas ─────────────────────────────────────

    def rotate_page(self, page_index: int, angle: int):
        """
        Rotaciona uma página pelo ângulo especificado.
        `angle` deve ser múltiplo de 90 (+90 = horário, -90 = anti-horário).
        A rotação é acumulada com a rotação atual da página.
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        page = self.doc[page_index]
        current = page.rotation
        page.set_rotation((current + angle) % 360)

    def rotate_pages(self, indices: list[int], angle: int):
        """Rotaciona múltiplas páginas pelo mesmo ângulo."""
        for idx in indices:
            self.rotate_page(idx, angle)

    # ── Reordenar Páginas ────────────────────────────────────────

    def swap_pages(self, index1: int, index2: int):
        """Troca as posições de duas páginas entre si (Swap)."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        
        count = self.doc.page_count
        if not (0 <= index1 < count and 0 <= index2 < count):
            raise ValueError("Índices de página inválidos.")

        # Criar a nova lista de ordem de páginas
        page_list = list(range(count))
        # Swap dos índices
        page_list[index1], page_list[index2] = page_list[index2], page_list[index1]
        
        # Aplicar a nova ordem
        self.doc.select(page_list)

    def duplicate_page(self, page_index: int):
        """Duplica a página especificada, inserindo a cópia logo após ela."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        
        # Criar um documento temporário com apenas a página a duplicar,
        # depois inserir essa cópia no documento principal.
        temp_doc = fitz.open()
        temp_doc.insert_pdf(self.doc, from_page=page_index, to_page=page_index)
        pdf_bytes = temp_doc.tobytes()
        temp_doc.close()
        
        # Reabrir os bytes como novo documento e inserir após a página original
        src = fitz.open("pdf", pdf_bytes)
        self.doc.insert_pdf(src, start_at=page_index + 1)
        src.close()

    # ── Salvar ───────────────────────────────────────────────────

    def save(self, path: Optional[str] = None):
        """
        Salva o documento.
        Se path for None, salva no caminho original.
        """
        if not self.doc:
            raise ValueError("Nenhum documento aberto.")
        
        save_path = path or self.file_path
        if not save_path:
            raise ValueError("Nenhum caminho de salvamento definido.")

        # Se for salvar no mesmo arquivo que está aberto, precisamos
        # de uma estratégia de arquivo temporário para evitar o erro
        # "save to original must be incremental".
        is_overwrite = (path is None or (self.file_path and 
                        os.path.abspath(path) == os.path.abspath(self.file_path)))

        if is_overwrite and self.file_path:
            # Gerar um nome temporário único para evitar conflitos (ex: retentativas após falha)
            target_path = os.path.abspath(save_path)
            temp_path = target_path + f".{uuid.uuid4().hex[:8]}.tmp"
            
            try:
                # 1. Salva em um arquivo temporário novo
                self.doc.save(temp_path, garbage=1, deflate=True)
                
                # Guardamos o caminho do documento atual antes de fechar (pode ser um .tmp anterior)
                old_doc_path = self.doc.name
                
                # 2. Fecha o documento atual para liberar os arquivos
                self.doc.close()
                
                # 3. Tenta substituir o original pelo novo temporário
                try:
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    os.rename(temp_path, target_path)
                    
                    # 4. Sucesso! Reabre no local correto
                    self.doc = fitz.open(target_path)
                    self.file_path = target_path
                    
                    # 5. Limpeza: Se estávamos em um fallback (.tmp), remove o arquivo antigo
                    if ".tmp" in old_doc_path and os.path.exists(old_doc_path):
                        try:
                            os.remove(old_doc_path)
                        except: pass
                        
                except Exception as rename_err:
                    # Se falhar o rename (arquivo ainda bloqueado), voltamos para o NOVO temp
                    self.doc = fitz.open(temp_path)
                    raise OSError(
                        f"O arquivo original ainda está sendo usado por outro programa.\n"
                        f"Suas alterações atuais foram salvas em:\n{temp_path}\n\n"
                        f"Feche o outro programa e tente salvar novamente no botão 'Salvar'."
                    ) from rename_err
                    
            except Exception as e:
                # Erro na gravação do próprio temp ou erro inesperado
                if "must be incremental" in str(e):
                    # Fallback extremo caso o PyMuPDF se perca
                    raise OSError("Erro interno de salvamento. Tente fechar e abrir o arquivo novamente ou use 'Salvar Como'.")
                raise e
        else:
            # Salvando em um novo local (Save As)
            self.doc.save(save_path, garbage=1, deflate=True)
            self.file_path = save_path

    def save_as(self, path: str):
        """Salva o documento em um novo caminho."""
        self.save(path)
