"""
Script de teste para o motor de PDF do Ross PDF Editor.
Verifica as operações básicas de manipulação.
"""

import sys
import os
from pathlib import Path
import fitz

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine.pdf_engine import PDFEngine

def test_engine():
    engine = PDFEngine()
    
    # 1. Teste Criar Novo
    print("Testando criação de novo PDF...")
    engine.new()
    engine.insert_blank_page()
    assert engine.page_count == 1
    print("OK")
    
    # 2. Teste Inserir Imagem
    # Criar uma imagem fake para teste se não existir
    from PIL import Image
    img_path = Path("tests/test_img.png")
    if not img_path.parent.exists():
        img_path.parent.mkdir()
    
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(img_path)
    
    print("Testando inserção de imagem...")
    engine.insert_image_as_page(str(img_path))
    assert engine.page_count == 2
    print("OK")
    
    # 3. Teste Recorte
    print("Testando recorte (CropBox)...")
    # Tentar recortar a página 2 (imagem)
    engine.crop_page(1, 0, 0, 50, 50)
    # Verificar se as dimensões mudaram (get_page_size)
    w, h = engine.get_page_size(1)
    # fitz.Rect(0, 0, 50, 50) -> width=50, height=50
    assert int(w) == 50
    assert int(h) == 50
    print("OK")
    
    # 4. Teste Excluir
    print("Testando exclusão...")
    engine.delete_page(0)
    assert engine.page_count == 1
    print("OK")
    
    # 5. Teste Salvar
    save_path = "tests/test_output.pdf"
    print(f"Testando salvamento em {save_path}...")
    engine.save_as(save_path)
    assert Path(save_path).exists()
    print("OK")
    
    engine.close()
    print("\nTodos os testes do motor passaram com sucesso!")

if __name__ == "__main__":
    try:
        test_engine()
    except Exception as e:
        print(f"ERRO NOS TESTES: {e}")
        sys.exit(1)
