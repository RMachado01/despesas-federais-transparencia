"""
ponto de entrada do pipeline. roda extract -> transform -> load pra um ano
especifico, passando por todos os orgaos superiores configurados em
src/extract/client.py.

uso:
    python run_pipeline.py --ano 2024
    python run_pipeline.py --ano 2020 --ano 2021 --ano 2022  (varios anos de uma vez)

a API do Portal da Transparencia so filtra despesas/por-orgao por ANO (não
tem filtro de mes nesse endpoint), e exige informar um orgao superior por
chamada - por isso o pipeline roda um loop interno pelos orgaos
configurados e junta tudo antes de gravar.
"""
import argparse
import json
import logging
import os

from dotenv import load_dotenv

from src.extract.client import ORGAOS_SUPERIORES, fetch_despesas_por_orgao, salvar_pagina_bruta
from src.transform.clean import normalizar_despesas
from src.load.warehouse import criar_tabelas, salvar_despesas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/pipeline.log")] if os.path.isdir("logs") else [logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CAMINHO_DB_PADRAO = "data/warehouse.duckdb"


def rodar_periodo(ano: int, caminho_db: str = CAMINHO_DB_PADRAO, pasta_raw_base: str = "data/raw", pular_extracao: bool = False) -> None:
    """Roda o pipeline completo pra um ano, passando por todos os orgaos configurados.

    pular_extracao existe so pra facilitar teste/reprocessamento local sem
    bater na API. quando pular_extracao=True, orgaos sem arquivo raw salvo
    pra esse ano são simplesmente ignorados (log de aviso), pra dar pra
    reprocessar um subconjunto sem precisar rebaixar tudo.
    """
    logger.info("iniciando pipeline pro ano %d (pular_extracao=%s)", ano, pular_extracao)

    token = None
    if not pular_extracao:
        token = os.environ.get("PORTAL_TRANSPARENCIA_TOKEN")
        if not token:
            raise RuntimeError("faltou configurar PORTAL_TRANSPARENCIA_TOKEN no .env")

    todos_registros_brutos = []
    for codigo_orgao, nome_orgao in ORGAOS_SUPERIORES:
        if not pular_extracao:
            logger.info("extraindo dados de %s (%s) pra %d...", nome_orgao, codigo_orgao, ano)
            dados_brutos = fetch_despesas_por_orgao(ano=ano, orgao_superior=codigo_orgao, token=token)
            salvar_pagina_bruta(dados_brutos, ano=ano, orgao_superior=codigo_orgao, pasta_base=pasta_raw_base)
        else:
            caminho_raw = os.path.join(pasta_raw_base, f"{ano:04d}", f"orgao_{codigo_orgao}.json")
            if not os.path.exists(caminho_raw):
                logger.warning("sem arquivo raw pra %s (%s) em %d, pulando", nome_orgao, codigo_orgao, ano)
                continue
            with open(caminho_raw, encoding="utf-8") as f:
                dados_brutos = json.load(f)

        todos_registros_brutos.extend(dados_brutos)

    logger.info("transformando %d registros brutos...", len(todos_registros_brutos))
    df_limpo = normalizar_despesas(todos_registros_brutos, ano=ano)

    logger.info("carregando %d registros no duckdb...", len(df_limpo))
    criar_tabelas(caminho_db)
    salvar_despesas(df_limpo, caminho_db)

    logger.info("pipeline concluido pro ano %d", ano)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Roda o pipeline de despesas do Portal da Transparencia pra um ou mais anos")
    parser.add_argument("--ano", type=int, required=True, action="append", help="pode repetir --ano pra rodar varios anos de uma vez")
    args = parser.parse_args()

    for ano in args.ano:
        rodar_periodo(ano=ano)
