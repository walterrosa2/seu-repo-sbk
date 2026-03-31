import json
import os
from pathlib import Path

CONFIG_FILE = Path("config_evidencias.json")

def _init_config():
    if not CONFIG_FILE.exists():
        default_config = {
            "Serasa PJ": {
                "exibir_usuario": True,
                "palavras_chave": ["serasa"],
                "slides": [
                    {
                        "id": "serasa_risco",
                        "modo": "ancora",
                        "ancora": "Painel de Risco",
                        "cabecalho": "Destaque Risco Serasa - {nome_empresa}",
                        "descricao": "Nível de risco identificado: {risco}"
                    }
                ]
            },
            "IRPF Sócio": {
                "exibir_usuario": True,
                "palavras_chave": ["irpf", "imposto de renda"],
                "slides": [
                    {
                        "id": "irpf_bens",
                        "modo": "ancora",
                        "ancora": "Bens e Direitos",
                        "cabecalho": "Resumo de Bens - IRPF",
                        "descricao": "Principais bens declarados."
                    }
                ]
            },
            "VADU": {
                "exibir_usuario": True,
                "palavras_chave": ["vadu"],
                "slides": []
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
    else:
        # Migração automática se o formato for antigo
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
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
