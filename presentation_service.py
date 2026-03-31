import os
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

def apply_sbk_theme(slide, prs):
    # SBK Dark Blue RGB: (24, 26, 82) from their logo/website approximation
    dark_blue = RGBColor(24, 26, 82)
    gray = RGBColor(153, 153, 153)
    
    # Top bar
    left = Inches(0)
    top = Inches(0)
    width = prs.slide_width
    height = Inches(0.4)
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = dark_blue
    shape.line.fill.background()
    
    # Bottom subtle bar
    shape_btm = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, prs.slide_height - Inches(0.2), width, Inches(0.2)
    )
    shape_btm.fill.solid()
    shape_btm.fill.fore_color.rgb = gray
    shape_btm.line.fill.background()

def criar_apresentacao_evidencias(cnpj: str, slides_config: list, out_path: str):
    """
    slides_config: [
        {"title": "...", "description": "...", "image_path": "..."}
    ]
    """
    prs = Presentation()
    # Formato Widescreen 16:9
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # Layout em branco
    blank_slide_layout = prs.slide_layouts[6]
    
    for config in slides_config:
        slide = prs.slides.add_slide(blank_slide_layout)
        apply_sbk_theme(slide, prs)
        
        # Inserção da Logo Corporativa
        logo_path = Path("templates/sbk.png")
        if logo_path.exists():
            # Canto superior direito (dentro ou abaixo da top bar)
            try:
                slide.shapes.add_picture(str(logo_path), prs.slide_width - Inches(2), Inches(0.5), width=Inches(1.8))
            except:
                pass
        
        # Título do Slide
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(12), Inches(0.8))
        tf = txBox.text_frame
        p = tf.add_paragraph()
        p.text = str(config.get("title", "Evidência / Destaque")).strip()
        p.font.bold = True
        p.font.size = Pt(24)
        p.font.color.rgb = RGBColor(24, 26, 82)
        
        # Descrição Dinâmica
        # Aumentamos a largura para permitir mais texto se necessário
        txBoxDesc = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(12), Inches(1.5))
        tfDesc = txBoxDesc.text_frame
        tfDesc.word_wrap = True
        pDesc = tfDesc.add_paragraph()
        pDesc.text = str(config.get("description", "Sem descrição.")).strip()
        pDesc.font.size = Pt(14)
        pDesc.font.color.rgb = RGBColor(60, 60, 60)
        
        # Cálculo de posição da imagem baseado na "altura" do texto (estimativa)
        # Se o texto for longo, a imagem desce
        top_imagem = Inches(2.8)
        
        # Imagem Recortada
        img_path = config.get("image_path")
        if img_path and os.path.exists(str(img_path)):
            try:
                # Centraliza a imagem horizontalmente e ajusta altura para caber no slide
                # Largura total 13.3, imagem centralizada com 10 inches -> margem de 1.6
                pic = slide.shapes.add_picture(str(img_path), Inches(1.6), top_imagem)
                
                # Redimensionamento proporcional para caber na altura restante
                max_height = prs.slide_height - top_imagem - Inches(0.5)
                max_width = prs.slide_width - Inches(3.2) # margem de 1.6 de cada lado
                
                if pic.height > max_height:
                    pic.height = max_height
                if pic.width > max_width:
                    pic.width = max_width
                
                # Centraliza horizontalmente após redimensionar
                pic.left = int((prs.slide_width - pic.width) / 2)
                
            except Exception as e:
                print(f"Erro ao inserir imagem: {e}")
                txBoxImg = slide.shapes.add_textbox(Inches(2), top_imagem, Inches(9), Inches(1))
                pImg = txBoxImg.text_frame.add_paragraph()
                pImg.text = f"[Erro ao carregar imagem: {os.path.basename(img_path)}]"
        else:
            # Placeholder vazio
            txBoxImg = slide.shapes.add_textbox(Inches(2), top_imagem, Inches(9), Inches(1))
            tfImg = txBoxImg.text_frame
            tfImg.word_wrap = True
            pImg = tfImg.add_paragraph()
            pImg.text = "[Evidência visual não disponível - O registro de âncora pode precisar de revisão]"
            pImg.font.size = Pt(18)
            pImg.font.italic = True
            pImg.font.color.rgb = RGBColor(200, 200, 200)
            pImg.alignment = PP_ALIGN.CENTER
    
    # Criar diretório destino se não existir
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
