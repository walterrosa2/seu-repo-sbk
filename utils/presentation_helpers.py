import re
from pathlib import Path
import json
from report_parser import extract_executive_summary, parse_unified_report

def extract_dynamic_blocks_from_report(text: str) -> dict:
    """
    Faz o parsing de blocos <bloco>"NOME_DO_ARQUIVO_LIDO" e extrai os subitens.
    Mapeia para um dicionário de chaves achatadas: {'nome_bloco.nome_subitem': '...'}
    """
    extracted = {}
    if not text:
        return extracted
        
    # Encontra todos os blocos usando regex. Se não tiver fechamento, captura até a próxima tag ou fim do texto.
    blocks = re.finditer(r'<bloco>[="]*(.*?)"*[\n\r]+(.*?)(?=</bloco>|<bloco>|\Z)', text, re.DOTALL | re.IGNORECASE)
    
    for b in blocks:
        raw_name = b.group(1).strip()
        content = b.group(2)
        if not content:
            continue
            
        import unicodedata
        def clean_key(s):
            s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            s = re.sub(r'[^a-zA-Z0-9]', '_', s).lower()
            return re.sub(r'_+', '_', s).strip('_')

        clean_name = clean_key(raw_name)
        if not clean_name:
            clean_name = "bloco_sem_nome"
            
        # Extrai subitens marcados com 'Subitem =>'
        subitem_pattern = r'Subitem\s*=>\s*(.*?)\n(.*?)?(?=Subitem\s*=>|</bloco>|\Z)'
        subitems_matches = list(re.finditer(subitem_pattern, content, re.DOTALL | re.IGNORECASE))
        
        if subitems_matches:
            for s in subitems_matches:
                raw_sub = s.group(1).strip()
                sub_content = s.group(2).strip() if s.group(2) else ""
                clean_sub = clean_key(raw_sub)
                
                key = f"{clean_name}.{clean_sub}"
                extracted[key] = sub_content
        else:
            # Tenta fallback para **Topico** (padrão antigo/variável de markdown)
            fallback_pattern = r'\*\*([^*]+)\*\*\n(.*?)?(?=\*\*|</bloco>|\Z)'
            fallback_matches = list(re.finditer(fallback_pattern, content, re.DOTALL))
            if fallback_matches:
                for s in fallback_matches:
                    raw_sub = s.group(1).strip()
                    sub_content = s.group(2).strip() if s.group(2) else ""
                    clean_sub = clean_key(raw_sub)
                    key = f"{clean_name}.{clean_sub}"
                    extracted[key] = sub_content
            else:
                # Se não tem subitem estruturado, salva o bloco inteiro
                extracted[clean_name] = content.strip()
                
    return extracted

STATIC_AGENT_VARIABLES = [
    # IRPF
    "irpf.informacoes_pessoais_e_patrimoniais",
    "irpf.renda_e_capacidade_de_pagamento",
    "irpf.endividamento_e_compromissos_financeiros",
    "irpf.participacao_em_empresas",
    "irpf.relacao_com_a_empresa_pleiteante",
    
    # VADU
    "vadu.identificacao_e_cadastro_da_empresa",
    "vadu.quadro_societario_e_empresas_relacionadas",
    "vadu.situacao_fiscal_e_tributaria",
    "vadu.endividamento_e_risco_de_credito",
    "vadu.processos_judiciais",
    "vadu.atividade_economica_e_setor",
    "vadu.analise_de_risco_e_conformidade",
    
    # SERASA / SPC
    "serasa.identificacao_e_cadastro_da_empresa",
    "serasa.quadro_societario_e_administracao",
    "serasa.consultas_ao_serasa_spc",
    "serasa.historico_de_pagamentos_e_pontualidade",
    "serasa.endividamento_e_risco_de_credito",
    "serasa.pendencias_financeiras_e_restritivas",
    "serasa.fornecedores_e_relacionamento_comercial",
    "serasa.analises_comparativas_e_tendencias",
    
    # RISCO E CONTABILIDADE
    "relatorio_risco.calculo_quantitativo_raroc_pd_e_lgd",
    "relatorio_risco.definicao_do_risco_de_credito",
    "relatorio_risco.limite_de_credito_sugerido",
    "relatorio_risco.conclusao_justificativa_tecnica",
    "balanco_dre.analise_completa_de_liquidez_e_solvencia",
    
    # NOVOS TIPOS (AGENTE 2)
    "faturamento.tabela_de_faturamento_mes_a_mes",
    "faturamento.media_mensal_e_desvio_padrao",
    "faturamento.comparativo_com_ano_anterior",
    "faturamento.sazonalidade",
    "cartao_cnpj.extracao_razao_social_numero_atividade",
    "cartao_cnpj.validacao_situacao_cadastral",
    "lista_de_clientes.extracao_e_lista_de_clientes",
    "curva_abc.analise_de_curva_abc",
    "endividamento_bancario_scr.analise_de_nivel_de_endividamento",
    "endividamento_bancario_scr.cruzamento_com_saldos_bancarios",
    "endividamento_bancario_scr.comparativo_curto_vs_longo_prazo"
]

def get_presentation_variables(cnpj: str, exec_path: Path) -> dict:
    """
    Consolida variáveis extraídas da análise para uso nos slides.
    Busca no relatório unificado e metadados.
    Inclui chaves estáticas (pré-cadastradas) para que a UI sempre as mostre.
    """
    vars_dict = {
        "cnpj": cnpj,
        "nome_empresa": "N/D",
        "risco": "N/D",
        "limite": "N/D",
        "raroc": "N/D",
        "score_serasa": "N/D",
        "faturamento": "N/D"
    }

    # Popula inicialmente as variáveis estáticas pré-cadastradas (para Autocomplete)
    for expected_key in STATIC_AGENT_VARIABLES:
        vars_dict[expected_key] = ""
    
    unificado_path = exec_path / "Retorno_IA" / "relatorio_unificado.md"
    if unificado_path.exists():
        text = unificado_path.read_text(encoding="utf-8", errors="ignore")
        summary = extract_executive_summary(text)
        
        vars_dict["risco"] = summary.get("risco", "N/D")
        vars_dict["limite"] = summary.get("limite", "N/D")
        vars_dict["raroc"] = summary.get("raroc", "N/D")
        vars_dict["decisao"] = summary.get("decisao", "Em análise")
        
        # Tenta extrair score e faturamento via regex simples no texto unificado
        # Se não encontrar, fica N/D
        m_score = re.search(r"(?i)score[:\s]+(\d+)", text)
        if m_score: vars_dict["score_serasa"] = m_score.group(1)
        
        m_fat = re.search(r"(?i)faturamento[:\s]+(R\$\s?[\d\.,]+)", text)
        if m_fat: vars_dict["faturamento"] = m_fat.group(1)
        
        # Razão Social
        m_razao = re.search(r"(?i)Razão Social[:\s]+([^\n]+)", text)
        if m_razao: vars_dict["nome_empresa"] = m_razao.group(1).strip()

        # Extração de blocos dinâmicos (Agentes IAs)
        dynamic_blocks = extract_dynamic_blocks_from_report(text)
        if dynamic_blocks:
            vars_dict.update(dynamic_blocks)

    return vars_dict

def inject_variables(text: str, variables: dict) -> str:
    """
    Substitui padrões {variavel} pelo valor real com tolerância a vazios e fuzzy match.
    """
    if not text: return ""
    
    # 1. Encontrar todos os placeholders no texto
    placeholders = re.findall(r'\{([a-zA-Z0-9_\.]+)\}', text)
    if not placeholders:
        return text
        
    result = text
    
    # Normalizador global para a busca
    import unicodedata
    def norm(s):
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    valid_vars = {k: v for k, v in variables.items() if str(v).strip() and str(v).strip() != "N/D"}
    norm_vars = {norm(k): k for k in valid_vars.keys()}

    for ph in placeholders:
        if ph in valid_vars:
            val = valid_vars[ph]
        else:
            ph_norm = norm(ph)
            matched_key = None
            
            # Match exato da string limpa
            for nk, real_k in norm_vars.items():
                if ph_norm in nk or nk in ph_norm:
                    matched_key = real_k
                    break
            
            # Match parcial por similaridade dos tokens
            if not matched_key:
                parts = [norm(p) for p in ph.replace('.', '_').split('_') if len(norm(p)) > 2]
                best_match, best_score = None, 0
                for nk, real_k in norm_vars.items():
                    score = sum(1 for p in parts if p in nk)
                    if score > best_score and score >= len(parts) * 0.5:
                        best_score = score
                        best_match = real_k
                matched_key = best_match

            # Substitui valor encontrado ou apaga o placeholder
            val = variables[matched_key] if matched_key else ""
            
        if val is None: val = ""
        result = result.replace("{" + ph + "}", str(val))
        
    return result
