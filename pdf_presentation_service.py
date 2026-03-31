from fpdf import FPDF
import os
from pathlib import Path

# Mapa de caracteres Unicode comuns (gerados por LLMs) para equivalentes Latin-1 seguros
_UNICODE_MAP = {
    "\u2013": "-",   # en dash  (–)
    "\u2014": "-",   # em dash  (—)
    "\u2018": "'",   # aspas esquerdas simples  (')
    "\u2019": "'",   # aspas direitas simples  (')
    "\u201C": '"',   # aspas esquerdas duplas  (")
    "\u201D": '"',   # aspas direitas duplas  (")
    "\u2026": "...", # reticências  (…)
    "\u00B7": "*",   # ponto médio  (·)
    "\u2022": "*",   # bullet  (•)
    "\u00A0": " ",   # espaço não-quebrável
    "\u200B": "",    # zero-width space
}

def _sanitizar_texto(texto: str) -> str:
    """Substitui caracteres Unicode problemáticos por equivalentes Latin-1 seguros."""
    for char, substituto in _UNICODE_MAP.items():
        texto = texto.replace(char, substituto)
    # Fallback: remove qualquer caractere ainda fora do range Latin-1
    return texto.encode("latin-1", errors="replace").decode("latin-1")


class SBK_PDF(FPDF):
    def header(self):
        # SBK Dark Blue RGB: (24, 26, 82)
        self.set_fill_color(24, 26, 82)
        self.rect(0, 0, 210, 15, 'F')
        
    def footer(self):
        self.set_y(-10)
        self.set_fill_color(153, 153, 153)
        self.rect(0, 287, 210, 10, 'F')
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def criar_apresentacao_pdf(cnpj: str, slides_config: list, out_path: str):
    """
    Gera um PDF espelhando o visual do PPTX usando fpdf2.
    """
    pdf = SBK_PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    logo_path = Path("templates/sbk.png")
    
    for config in slides_config:
        pdf.add_page()
        
        # Logo
        if logo_path.exists():
            try:
                pdf.image(str(logo_path), x=160, y=18, w=40)
            except:
                pass
        
        # Título
        pdf.set_y(20)
        pdf.set_font('helvetica', 'B', 20)
        pdf.set_text_color(24, 26, 82)
        pdf.multi_cell(0, 10, _sanitizar_texto(str(config.get("title", "Evidencia")).strip()))
        
        # Descrição (Texto superior)
        pdf.set_y(pdf.get_y() + 5)
        pdf.set_font('helvetica', '', 12)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 7, _sanitizar_texto(str(config.get("description", "Sem descricao.")).strip()))
        
        y_image = pdf.get_y() + 10
        
        # Imagem (Centralizada abaixo do texto)
        img_path = config.get("image_path")
        if img_path and os.path.exists(str(img_path)):
            try:
                # Calcula largura disponível para centralizar
                # A4 largura é 210mm. Margens padrão 10mm.
                pdf.image(str(img_path), x=15, y=y_image, w=180)
            except Exception as e:
                pdf.set_y(y_image)
                pdf.set_font('helvetica', 'I', 10)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 10, f"[Erro ao carregar imagem: {os.path.basename(img_path)}]", 0, 1, 'C')
        else:
            pdf.set_y(y_image + 20)
            pdf.set_font('helvetica', 'I', 12)
            pdf.set_text_color(180, 180, 180)
            pdf.cell(0, 10, "[Evidência visual não disponível]", 0, 1, 'C')

    pdf.output(out_path)
    return out_path
