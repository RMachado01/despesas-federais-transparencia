"""
script pra gerar uns dados de exemplo realistas, só pra dar pra rodar o
dashboard localmente sem precisar de token da API agora. não é parte do
pipeline "de verdade", é só pra popular o warehouse.duckdb de demonstracao.

rodar: python scripts/gerar_dados_exemplo.py
"""
import json
import os
import random

ORGAOS = [
    "Ministerio da Educacao",
    "Ministerio da Saude",
    "Ministerio da Defesa",
    "Ministerio da Infraestrutura",
    "Ministerio do Desenvolvimento Social",
    "Ministerio da Agricultura",
    "Ministerio da Justica e Seguranca Publica",
    "Ministerio da Ciencia e Tecnologia",
]

random.seed(42)  # fixo pra dar sempre o mesmo resultado, facilita conferir

for mes in range(1, 7):
    pasta = f"data/raw/2025-{mes:02d}"
    os.makedirs(pasta, exist_ok=True)

    despesas = []
    for orgao in ORGAOS:
        valor = random.uniform(500_000, 15_000_000)
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        despesas.append({"orgao": orgao, "valor": valor_formatado})

    with open(f"{pasta}/despesas_por_orgao.json", "w", encoding="utf-8") as f:
        json.dump(despesas, f, ensure_ascii=False, indent=2)

    print(f"gerado {pasta}/despesas_por_orgao.json com {len(despesas)} orgaos")
