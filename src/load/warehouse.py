"""
carga no duckdb. a regra que importa aqui é: reprocessar um periodo (ano+mes)
não pode duplicar dado, tem que substituir. por isso o DELETE antes do
INSERT, tudo dentro da mesma transacao pra não ficar num estado quebrado
se der erro no meio.
"""
import duckdb
import pandas as pd


def criar_tabelas(caminho_db: str) -> None:
    con = duckdb.connect(caminho_db)
    con.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            orgao VARCHAR,
            valor DOUBLE,
            ano INTEGER,
            mes INTEGER
        )
    """)
    con.close()


def salvar_despesas(df: pd.DataFrame, caminho_db: str) -> None:
    """Grava o DataFrame de despesas, substituindo qualquer dado do mesmo ano/mes."""
    if df.empty:
        return

    ano = int(df["ano"].iloc[0])
    mes = int(df["mes"].iloc[0])

    con = duckdb.connect(caminho_db)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM despesas WHERE ano = ? AND mes = ?", [ano, mes])
        con.execute("INSERT INTO despesas SELECT * FROM df")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
