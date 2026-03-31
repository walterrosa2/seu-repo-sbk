import json
import os
from pathlib import Path
from config import get_settings

CONFIG_FILE = Path(get_settings().CONFIG_DIR) / "config_evidencias.json"

def _init_config():
    default_config = {
        "SERASA": {
            "exibir_usuario": True,
            "palavras_chave": ["serasa", "confin"],
            "slides": [
                {
                    "id": "serasa_identificacao",
                    "modo": "ancora",
                    "ancora": "SERASA",
                    "cabecalho": "SERASA - Identificação e Risco",
                    "descricao": "Identificação: {serasa.identificacao_e_cadastro_da_empresa}\n\nRisco: {serasa.endividamento_e_risco_de_credito}\n{serasa.pendencias_financeiras_e_restritivas}"
                },
                {
                    "id": "serasa_historico",
                    "modo": "ancora",
                    "ancora": "SERASA",
                    "cabecalho": "SERASA - Consultas e Consultas Relevantes",
                    "descricao": "{serasa.consultas_ao_serasa_spc}\n\nPagamentos: {serasa.historico_de_pagamentos_e_pontualidade}"
                }
            ]
        },
        "SPC": {
            "exibir_usuario": True,
            "palavras_chave": ["spc", "boa vista", "boavista"],
            "slides": [
                {
                    "id": "spc_identificacao",
                    "modo": "ancora",
                    "ancora": "SPC",
                    "cabecalho": "SPC - Identificação e Risco",
                    "descricao": "{spc.identificacao_e_cadastro_da_empresa}\n\nRiscos e Pendências:\n{spc.endividamento_e_risco_de_credito}"
                }
            ]
        },
        "IRPF": {
            "exibir_usuario": True,
            "palavras_chave": ["irpf", "imposto de renda", "declaracao", "recibo de entrega"],
            "slides": [
                {
                    "id": "irpf_bens",
                    "modo": "ancora",
                    "ancora": "IRPF",
                    "cabecalho": "IRPF - Informações e Patrimônio",
                    "descricao": "{irpf.informacoes_pessoais_e_patrimoniais}\n\nParticipação: {irpf.participacao_em_empresas}"
                },
                {
                    "id": "irpf_dividas",
                    "modo": "ancora",
                    "ancora": "IRPF",
                    "cabecalho": "IRPF - Renda e Dívidas",
                    "descricao": "Renda/Capacidade: {irpf.renda_e_capacidade_de_pagamento}\n\nEndividamento: {irpf.endividamento_e_compromissos_financeiros}"
                }
            ]
        },
        "VADU": {
            "exibir_usuario": True,
            "palavras_chave": ["vadu", "relatorio completo"],
            "slides": [
                {
                    "id": "vadu_cadastral",
                    "modo": "ancora",
                    "ancora": "VADU",
                    "cabecalho": "VADU - Situação Cadastral e Fiscal",
                    "descricao": "{vadu.identificacao_e_cadastro_da_empresa}\n\nSituação Fiscal/Tributária: {vadu.situacao_fiscal_e_tributaria}"
                },
                {
                    "id": "vadu_processos",
                    "modo": "ancora",
                    "ancora": "VADU",
                    "cabecalho": "VADU - Processos e Risco",
                    "descricao": "{vadu.processos_judiciais}\n\nRisco e Conformidade: {vadu.analise_de_risco_e_conformidade}"
                }
            ]
        },
        "Cartão CNPJ": {
            "exibir_usuario": True,
            "palavras_chave": ["cartao cnpj", "comprovante cnpj", "comprovante de inscricao", "cnpj"],
            "slides": [
                {
                    "id": "cnpj_info",
                    "modo": "ancora",
                    "ancora": "CNPJ",
                    "cabecalho": "Cartão CNPJ - Extrato",
                    "descricao": "Dados Extraídos: {cartao_cnpj.extracao_razao_social_numero_atividade}\n\nValidação: {cartao_cnpj.validacao_situacao_cadastral}"
                }
            ]
        },
        "Faturamento": {
            "exibir_usuario": True,
            "palavras_chave": ["faturamento", "extrato", "defis", "pgdas", "receita bruta"],
            "slides": [
                {
                    "id": "faturamento_info",
                    "modo": "ancora",
                    "ancora": "Faturamento",
                    "cabecalho": "Faturamento - Evolução Mensal",
                    "descricao": "Tabela e Média:\n{faturamento.tabela_de_faturamento_mes_a_mes}\n\nMédia e Desvio:\n{faturamento.media_mensal_e_desvio_padrao}"
                },
                {
                    "id": "faturamento_comp",
                    "modo": "ancora",
                    "ancora": "Faturamento",
                    "cabecalho": "Faturamento - Comparativo e Sazonalidade",
                    "descricao": "Sazonalidade:\n{faturamento.sazonalidade}\n\nComparativo com ano anterior:\n{faturamento.comparativo_com_ano_anterior}"
                }
            ]
        },
        "Lista de Clientes": {
            "exibir_usuario": True,
            "palavras_chave": ["lista de clientes", "relacao de clientes", "principais clientes"],
            "slides": [
                {
                    "id": "clientes_info",
                    "modo": "ancora",
                    "ancora": "Clientes",
                    "cabecalho": "Lista de Principais Clientes",
                    "descricao": "{lista_de_clientes.extracao_e_lista_de_clientes}"
                }
            ]
        },
        "Curva ABC": {
            "exibir_usuario": True,
            "palavras_chave": ["curva abc", "abc de clientes", "abc de fornecedores", "concentracao"],
            "slides": [
                {
                    "id": "curva_info",
                    "modo": "ancora",
                    "ancora": "Curva ABC",
                    "cabecalho": "Análise da Curva ABC (Concentração)",
                    "descricao": "{curva_abc.analise_de_curva_abc}"
                }
            ]
        },
        "Endividamento Bancário": {
            "exibir_usuario": True,
            "palavras_chave": ["endividamento", "scr", "bacen", "registrato", "divida bancaria"],
            "slides": [
                {
                    "id": "scr_info",
                    "modo": "ancora",
                    "ancora": "Endividamento",
                    "cabecalho": "Endividamento Bancário (SCR) - Nível e Prazos",
                    "descricao": "Análise do Endividamento:\n{endividamento_bancario_scr.analise_de_nivel_de_endividamento}\n\nCurto vs Longo Prazo:\n{endividamento_bancario_scr.comparativo_curto_vs_longo_prazo}\n\nCruzamento com Saldos:\n{endividamento_bancario_scr.cruzamento_com_saldos_bancarios}"
                }
            ]
        },
        "BALANÇO / DRE": {
            "exibir_usuario": True,
            "palavras_chave": ["balanco", "dre", "balancete", "demonstracao", "contabil"],
            "slides": [
                {
                    "id": "balanco_info",
                    "modo": "ancora",
                    "ancora": "Balanço",
                    "cabecalho": "Balanço / DRE - Liquidez e Solvência",
                    "descricao": "{balanco_dre.analise_completa_de_liquidez_e_solvencia}"
                }
            ]
        },
        "Relatório de Risco": {
            "exibir_usuario": True,
            "palavras_chave": ["raroc", "pd", "lgd", "relatorio risco"],
            "slides": [
                {
                    "id": "risco_info",
                    "modo": "ancora",
                    "ancora": "Risco",
                    "cabecalho": "Avaliação de Risco e Limite de Crédito",
                    "descricao": "Score/Risco Definido: {relatorio_risco.definicao_do_risco_de_credito}\n\nRAROC/PD/LGD: {relatorio_risco.calculo_quantitativo_raroc_pd_e_lgd}\n\nLimite Sugerido: {relatorio_risco.limite_de_credito_sugerido}\n\nConclusão Técnica: \n{relatorio_risco.conclusao_justificativa_tecnica}"
                }
            ]
        }
    }

    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
    else:
        # Migração automática se o formato for antigo ou arquivo vazio
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Se o usuário ou o branch limpar o arquivo sem querer (ex: {})
            if not data:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                return
            
            modified = False
            for doc_type, content in data.items():
                if "slides" not in content:
                    # Converte formato 1:1 para lista de slides
                    old_slide = {
                        "id": f"{doc_type.lower().replace(' ', '_')}_auto",
                        "modo": content.get("modo", "ancora"),
                        "ancora": content.get("ancora", ""),
                        "ancora_inicio": content.get("ancora_inicio", ""),
                        "ancora_fim": content.get("ancora_fim", ""),
                        "coordenadas": content.get("coordenadas", ""),
                        "pagina": content.get("pagina", 1),
                        "cabecalho": content.get("cabecalho", ""),
                        "descricao": content.get("descricao", "")
                    }
                    data[doc_type] = {
                        "exibir_usuario": content.get("status") != "pendente",
                        "palavras_chave": [],
                        "slides": [old_slide]
                    }
                    modified = True
                
                # Nova migração: Garantir que todo tipo tenha lista de palavras_chave
                if "palavras_chave" not in content:
                    # Injeta palavras_chave hardcoded do sistema legado para compatibilidade local
                    if doc_type == "Serasa PJ":
                        content["palavras_chave"] = ["serasa", "serasa pj"]
                    elif doc_type == "IRPF Sócio":
                        content["palavras_chave"] = ["irpf", "imposto de renda", "irpf socio"]
                    elif doc_type == "VADU":
                        content["palavras_chave"] = ["vadu"]
                    else:
                        content["palavras_chave"] = []
                    data[doc_type] = content
                    modified = True
            
            if modified:
                save_config(data)
        except Exception as e:
            print(f"Erro na migração de config: {e}")

def load_config() -> dict:
    _init_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar config de evidências: {e}")
        return {}

def save_config(config_data: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar config de evidências: {e}")
        return False

def get_config_for_type(doc_type: str) -> dict:
    config = load_config()
    return config.get(doc_type, {})

def get_all_aliases() -> dict:
    """
    Retorna um dicionário mapeando cada tipo de documento
    para a sua lista de palavras-chave (aliases).
    Ex: {'Serasa PJ': ['serasa', 'serasa pj']}
    """
    config = load_config()
    aliases_dict = {}
    for doc_type, data in config.items():
        palavras = data.get("palavras_chave", [])
        if not palavras:
            # Fallback: O próprio nome como palavra-chave
            palavras = [doc_type.lower()]
        aliases_dict[doc_type] = palavras
    return aliases_dict
