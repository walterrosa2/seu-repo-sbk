import os
import json

caminho_respostas = "etapas"
saida_evidencias = "etapas/04_evidencias_agrupadas.json"

evidencias_por_quesito = {}

for i in range(1, 11):
    try:
        with open(os.path.join(caminho_respostas, f"03_resposta_parte_{i}.json"), "r", encoding="utf-8") as f:
            texto = f.read().strip()
            if texto.startswith("["):
                dados = json.loads(texto)
                for item in dados:
                    q = item.get("quesito")
                    t = item.get("fonte_documental_trecho", [])
                    if q and isinstance(t, list):
                        evidencias_por_quesito.setdefault(q, []).extend(t)
    except Exception as e:
        print(f"⚠️ Erro na parte {i}: {e}")

if evidencias_por_quesito:
    with open(saida_evidencias, "w", encoding="utf-8") as f:
        json.dump(evidencias_por_quesito, f, indent=2, ensure_ascii=False)
    print(f"✅ Evidências salvas em: {saida_evidencias}")
else:
    print("❌ Nenhuma evidência foi extraída.")
