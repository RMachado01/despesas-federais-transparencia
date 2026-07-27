"""
ponto de entrada do pipeline. roda extract -> transform -> load pra um
ano/mes especifico.

uso:
    python run_pipeline.py --ano 2025 --mes 6

fiz assim (ano+mes obrigatorios, sem "rodar tudo") porque a API cobre
bastante historico e eu não queria puxar tudo de uma vez enquanto ainda
to testando o pipeline. dá pra rodar mes a mes e ir acumulando no duckdb.
"""
import argparse
import json
import logging
import os

from dotenv import load_dotenv

from src.extract.client import fetch_despesas_por_orgao, salvar_pagina_bruta
from src.transform.clean import normalizar_despesas
from src.load.warehouse import criar_tabelas, salvar_despesas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/pipeline.log")] if os.path.isdir("logs") else [logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CAMINHO_DB_PADRAO = "data/warehouse.duckdb"


def rodar_periodo(ano: int, mes: int, caminho_db: str = CAMINHO_DB_PADRAO, pasta_raw_base: str = "data/raw", pular_extracao: bool = False) -> None:
    """Roda o pipeline completo pra um periodo. pular_extracao existe so pra facilitar teste/reprocessamento local."""
    logger.info("iniciando pipeline pra %d-%02d (pular_extracao=%s)", ano, mes, pular_extracao)

    if not pular_extracao:
        logger.info("extraindo dados da API...")
        token = os.environ.get("PORTAL_TRANSPARENCIA_TOKEN")
        if not token:
            raise RuntimeError("faltou configurar PORTAL_TRANSPARENCIA_TOKEN no .env")
        dados_brutos = fetch_despesas_por_orgao(ano=ano, mes=mes, token=token)
        salvar_pagina_bruta(dados_brutos, ano=ano, mes=mes, pasta_base=pasta_raw_base)
    else:
        caminho_raw = os.path.join(pasta_raw_base, f"{ano:04d}-{mes:02d}", "despesas_por_orgao.json")
        with open(caminho_raw, encoding="utf-8") as f:
            dados_brutos = json.load(f)

    logger.info("transformando %d registros brutos...", len(dados_brutos))
    df_limpo = normalizar_despesas(dados_brutos, ano=ano, mes=mes)

    logger.info("carregando %d registros no duckdb...", len(df_limpo))
    criar_tabelas(caminho_db)
    salvar_despesas(df_limpo, caminho_db)

    logger.info("pipeline concluido pra %d-%02d", ano, mes)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Roda o pipeline de despesas do Portal da Transparencia pra um ano/mes")
    parser.add_argument("--ano", type=int, required=True)
    parser.add_argument("--mes", type=int, required=True)
    args = parser.parse_args()

    rodar_periodo(ano=args.ano, mes=args.mes)
