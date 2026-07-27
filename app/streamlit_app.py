"""
dashboard de despesas publicas federais. le direto do duckdb, sem
cache complicado por enquanto - o volume de dados é pequeno o suficiente
pra não precisar.
"""
import duckdb
import pandas as pd
import streamlit as st

CAMINHO_DB = "data/warehouse.duckdb"

st.set_page_config(page_title="Despesas Federais - Portal da Transparencia", layout="wide")


@st.cache_resource
def conectar():
    return duckdb.connect(CAMINHO_DB, read_only=True)


def carregar_despesas(con) -> pd.DataFrame:
    return con.execute("SELECT orgao, valor, ano, mes FROM despesas ORDER BY ano, mes").df()


con = conectar()
df = carregar_despesas(con)

st.title("Despesas publicas federais")
st.caption("Dados de exemplo gerados localmente. Pra usar dados reais, rode run_pipeline.py com um token da API (ver README).")

# --- filtros ---
col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    orgaos_selecionados = st.multiselect("Orgao", options=sorted(df["orgao"].unique()), default=None)
with col_filtro2:
    meses_selecionados = st.multiselect("Mes", options=sorted(df["mes"].unique()), default=None)

df_filtrado = df.copy()
if orgaos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["orgao"].isin(orgaos_selecionados)]
if meses_selecionados:
    df_filtrado = df_filtrado[df_filtrado["mes"].isin(meses_selecionados)]

# --- KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("Total gasto", f"R$ {df_filtrado['valor'].sum():,.2f}")
col2.metric("Numero de registros", len(df_filtrado))
media = df_filtrado["valor"].mean() if len(df_filtrado) else 0
col3.metric("Valor medio por registro", f"R$ {media:,.2f}")

# --- serie temporal ---
st.subheader("Gasto por mes")
serie = df_filtrado.groupby("mes")["valor"].sum().reset_index()
st.line_chart(serie, x="mes", y="valor")

# --- ranking por orgao ---
st.subheader("Ranking por orgao")
ranking = df_filtrado.groupby("orgao")["valor"].sum().sort_values(ascending=False).reset_index()
st.bar_chart(ranking, x="orgao", y="valor")

# --- tabela crua, pra quem quiser conferir os numeros ---
with st.expander("Ver dados brutos"):
    st.dataframe(df_filtrado)
