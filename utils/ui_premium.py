"""
ui_premium.py
Helpers de estilo premium para a aba Apresentação (Editor de Slides + Config de Mapeamento).
Baseado em: knowledge/streamlit_premium_ui.md
"""
import streamlit as st


# ──────────────────────────────────────────────
# CSS BASE — Dark mode + Glassmorphism + Fontes
# ──────────────────────────────────────────────
_PRESENTATION_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Reset de fonte global */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Glass Card ── */
.glass-card {
    background: rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 20px 24px;
    margin-bottom: 16px;
}

/* ── Section Header ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}
.section-header h2 {
    font-size: 1.4rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00D1FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.section-tag {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #00D1FF;
    border: 1px solid rgba(0, 209, 255, 0.35);
    border-radius: 6px;
    padding: 2px 8px;
    opacity: 0.85;
}

/* ── Slide Card ── */
.slide-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: rgba(0, 209, 255, 0.06);
    border-left: 3px solid #00D1FF;
    border-radius: 0 10px 10px 0;
    margin-bottom: 14px;
}
.slide-card-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #E8EAED;
}

/* ── Cropper Container ── */
.crop-container {
    border: 1px solid rgba(0, 209, 255, 0.3);
    border-radius: 12px;
    padding: 16px;
    background: rgba(0, 209, 255, 0.03);
    margin-top: 8px;
}
.crop-instruction {
    font-size: 0.82rem;
    color: #8A94A6;
    margin-bottom: 8px;
    display: flex;
    gap: 6px;
    align-items: center;
}

/* ── AI Suggestion Card ── */
.ai-card {
    background: linear-gradient(135deg,
        rgba(0, 209, 255, 0.08) 0%,
        rgba(123, 97, 255, 0.08) 100%);
    border: 1px solid rgba(0, 209, 255, 0.2);
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 12px;
}

/* ── Status Badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-ok {
    background: rgba(0, 209, 145, 0.15);
    color: #00D191;
    border: 1px solid rgba(0, 209, 145, 0.3);
}
.badge-warn {
    background: rgba(255, 186, 0, 0.1);
    color: #FFBA00;
    border: 1px solid rgba(255, 186, 0, 0.25);
}
.badge-info {
    background: rgba(0, 209, 255, 0.1);
    color: #00D1FF;
    border: 1px solid rgba(0, 209, 255, 0.25);
}

/* ── Coords Display ── */
.coords-box {
    background: rgba(123, 97, 255, 0.1);
    border: 1px solid rgba(123, 97, 255, 0.25);
    border-radius: 8px;
    padding: 8px 14px;
    font-family: monospace;
    font-size: 0.85rem;
    color: #C2B0FF;
    margin-top: 6px;
}

/* ── Instruction Banner ── */
.instruction-banner {
    background: rgba(0, 209, 255, 0.06);
    border-left: 3px solid rgba(0, 209, 255, 0.5);
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 0.84rem;
    color: #9EB3C9;
    margin-bottom: 10px;
}
</style>
"""


def apply_presentation_premium_css() -> None:
    """Injeta o CSS dark premium na aba de Apresentação. Chamar uma vez no topo da seção."""
    st.markdown(_PRESENTATION_CSS, unsafe_allow_html=True)


def section_header(title: str, tag: str = "", icon: str = "") -> None:
    """Renderiza um cabeçalho de seção com gradiente e tag opcional."""
    icon_html = f"<span style='font-size:1.4rem'>{icon}</span>" if icon else ""
    tag_html = f'<span class="section-tag">{tag}</span>' if tag else ""
    st.markdown(
        f"""
        <div class="section-header">
            {icon_html}
            <h2>{title}</h2>
            {tag_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def slide_card_header(slide_num: int, title: str, has_image: bool) -> None:
    """Renderiza o cabeçalho de cada card de slide com badge de status."""
    badge_class = "badge-ok" if has_image else "badge-warn"
    badge_text = "✓ Imagem OK" if has_image else "⚠ Sem imagem"
    st.markdown(
        f"""
        <div class="slide-card-header">
            <span class="slide-card-title">🪟 Slide {slide_num} — {title[:40]}{"..." if len(title) > 40 else ""}</span>
            <span class="badge {badge_class}">{badge_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def crop_tool_header() -> None:
    """Cabeçalho visual da ferramenta de recorte com instrução premium."""
    st.markdown(
        """
        <div class="crop-container">
            <div class="crop-instruction">
                ✂️&nbsp;<strong style="color:#00D1FF">Ferramenta de Recorte Visual</strong>
                &nbsp;—&nbsp;Clique e arraste para selecionar a área de evidência.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def coords_display(x0: int, y0: int, x1: int, y1: int) -> None:
    """Exibe as coordenadas selecionadas num box monospace estilizado."""
    st.markdown(
        f'<div class="coords-box">📍 Área selecionada &nbsp;→&nbsp; x0={x0}, y0={y0}, x1={x1}, y1={y1}</div>',
        unsafe_allow_html=True,
    )


def instruction_banner(text: str) -> None:
    """Banner de instrução com borda cyan sutil."""
    st.markdown(
        f'<div class="instruction-banner">💡 {text}</div>',
        unsafe_allow_html=True,
    )


def ai_card_open(title: str = "✨ Sugestão Automática de Âncoras via IA") -> None:
    """Abre o card estilizado para o bloco de IA."""
    st.markdown(
        f'<div class="ai-card"><strong style="color:#00D1FF">{title}</strong>',
        unsafe_allow_html=True,
    )


def ai_card_close() -> None:
    """Fecha o div do ai_card."""
    st.markdown("</div>", unsafe_allow_html=True)


def glass_card_open() -> None:
    """Abre um container glass-card."""
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)


def glass_card_close() -> None:
    """Fecha o container glass-card."""
    st.markdown("</div>", unsafe_allow_html=True)
