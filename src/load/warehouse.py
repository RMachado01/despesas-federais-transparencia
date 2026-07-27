"""
carga no duckdb. a regra que importa aqui é: reprocessar um ano não pode
duplicar dado, tem que substituir. por isso o DELETE antes do INSERT, tudo
dentro da mesma transacao pra não ficar num estado quebrado se der erro no
meio.

a chave de idempotencia é só o ano (não ano+orgao) porque o pipeline sempre
busca TODOS os orgaos configurados de uma vez pra um ano e recarrega tudo
junto - ver run_pipeline.py.
"""
import duckdb
import pandas as pd


def criar_tabelas(caminho_db: str) -> None:
    con = duckdb.connect(caminho_db)
    con.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            orgao VARCHAR,
            orgao_superior VARCHAR,
            valor DOUBLE,
            ano INTEGER
        )
    """)
    con.close()


def salvar_despesas(df: pd.DataFrame, caminho_db: str) -> None:
    """Grava o DataFrame de despesas, substituindo qualquer dado do mesmo ano."""
    if df.empty:
        return

    ano = int(df["ano"].iloc[0])

    con = duckdb.connect(caminho_db)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM despesas WHERE ano = ?", [ano])
        con.execute("INSERT INTO despesas SELECT * FROM df")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
