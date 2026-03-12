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
        (x0, y0) = canto superior esquerdo do recorte
        (x1, y1) = canto inferior direito do recorte
        """
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        page = self.doc[page_index]
        crop_rect = fitz.Rect(x0, y0, x1, y1)
        page.set_cropbox(crop_rect)

    # ── Reordenar Páginas ────────────────────────────────────────

    def move_page(self, from_index: int, to_index: int):
        """Move uma página de from_index para to_index."""
        if self.doc is None:
            raise ValueError("Nenhum documento aberto.")
        self.doc.move_page(from_index, to_index)

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
            temp_path = str(save_path) + ".tmp"
            try:
                # 1. Salva em um arquivo temporário
                self.doc.save(temp_path, garbage=4, deflate=True)
                # 2. Fecha o documento atual para liberar o arquivo original
                self.doc.close()
                
                # 3. Substitui o original pelo temporário
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    os.rename(temp_path, save_path)
                    
                    # 4. Reabre o documento final
                    self.doc = fitz.open(save_path)
                    self.file_path = save_path
                except Exception as rename_err:
                    # Se falhar o rename (ex: arquivo em uso), tentamos 
                    # recuperar reabrindo do documento temporário para não perder o trabalho
                    self.doc = fitz.open(temp_path)
                    raise OSError(
                        f"O arquivo original está sendo usado por outro programa.\n"
                        f"Suas alterações estão salvas temporariamente em:\n{temp_path}\n\n"
                        f"Dica: Feche o outro programa ou use 'Salvar Como'."
                    ) from rename_err
                    
            except Exception as e:
                # Se ainda estiver aberto, não faz nada. Se fechou no passo 2, 
                # o bloco interno de rename_err já tentou reabrir.
                raise e
        else:
            # Salvando em um novo local (Save As)
            self.doc.save(save_path, garbage=4, deflate=True)
            self.file_path = save_path

    def save_as(self, path: str):
        """Salva o documento em um novo caminho."""
        self.save(path)
