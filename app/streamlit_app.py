"""
dashboard de despesas publicas federais. le direto do duckdb, sem
cache complicado por enquanto - o volume de dados (pouco mais de mil
linhas) é pequeno o suficiente pra não precisar.

a ideia aqui não é só jogar numero na tela, é contar a historia dos dados:
quanto cresceu, quem gastou mais, onde caiu. por isso tem bloco de KPI,
tendencia, ranking e variação ano a ano, não só uma tabela.
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
    return con.execute("SELECT orgao, orgao_superior, valor, ano FROM despesas ORDER BY ano, orgao_superior").df()


def formatar_moeda(valor: float) -> str:
    # bilhoes de reais ficam mais legiveis abreviado, tipo "R$ 725,8 bi",
    # do que escrever "R$ 725.768.700.188,65" numa tela cheia de numero
    if abs(valor) >= 1_000_000_000:
        return f"R$ {valor / 1_000_000_000:,.1f} bi"
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:,.1f} mi"
    return f"R$ {valor:,.2f}"


con = conectar()
df = carregar_despesas(con)

st.title("Despesas publicas federais")
st.caption(
    "Dados reais da API do Portal da Transparencia (endpoint despesas/por-orgao, valor = 'pago'). "
    "Cobre os ministerios configurados em src/extract/client.py, ano a ano (a API não tem filtro mensal nesse endpoint)."
)

# --- filtros ---
col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    anos_selecionados = st.multiselect("Ano", options=sorted(df["ano"].unique()), default=sorted(df["ano"].unique()))
with col_filtro2:
    ministerios_selecionados = st.multiselect("Ministerio", options=sorted(df["orgao_superior"].unique()), default=None)

df_filtrado = df.copy()
if anos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["ano"].isin(anos_selecionados)]
if ministerios_selecionados:
    df_filtrado = df_filtrado[df_filtrado["orgao_superior"].isin(ministerios_selecionados)]

if df_filtrado.empty:
    st.warning("Nenhum dado pros filtros selecionados.")
    st.stop()

totais_por_ano = df_filtrado.groupby("ano")["valor"].sum().sort_index()

# --- KPIs ---
st.subheader("Panorama do periodo")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total gasto no periodo", formatar_moeda(df_filtrado["valor"].sum()))

if len(totais_por_ano) >= 2:
    ultimo_ano, penultimo_ano = totais_por_ano.index[-1], totais_por_ano.index[-2]
    variacao = (totais_por_ano.iloc[-1] / totais_por_ano.iloc[-2] - 1) * 100
    col2.metric(f"Variacao {penultimo_ano} -> {ultimo_ano}", f"{variacao:+.1f}%")
else:
    col2.metric("Variacao ano a ano", "precisa de 2+ anos")

ano_pico = totais_por_ano.idxmax()
col3.metric("Ano de maior gasto", f"{ano_pico}", formatar_moeda(totais_por_ano.max()))

ministerio_top = df_filtrado.groupby("orgao_superior")["valor"].sum().idxmax()
col4.metric("Ministerio que mais gastou", ministerio_top)

# --- tendencia ---
st.subheader("Evolucao do gasto por ano")
st.line_chart(totais_por_ano.reset_index(), x="ano", y="valor")

# --- ranking por ministerio ---
st.subheader("Ranking por ministerio (soma do periodo filtrado)")
ranking = df_filtrado.groupby("orgao_superior")["valor"].sum().sort_values(ascending=False).reset_index()
st.bar_chart(ranking, x="orgao_superior", y="valor", horizontal=True)

# --- composicao por ministerio ao longo dos anos ---
st.subheader("De onde saiu o dinheiro, ano a ano")
composicao = df_filtrado.pivot_table(index="ano", columns="orgao_superior", values="valor", aggfunc="sum", fill_value=0)
st.area_chart(composicao)

# --- maiores variacoes no periodo ---
if len(anos_selecionados) >= 2:
    st.subheader(f"Quem mais cresceu / mais caiu entre {min(anos_selecionados)} e {max(anos_selecionados)}")

    primeiro_ano, ultimo_ano_sel = min(anos_selecionados), max(anos_selecionados)
    gasto_inicio = df_filtrado[df_filtrado["ano"] == primeiro_ano].groupby("orgao_superior")["valor"].sum()
    gasto_fim = df_filtrado[df_filtrado["ano"] == ultimo_ano_sel].groupby("orgao_superior")["valor"].sum()

    variacoes = pd.DataFrame({"gasto_inicio": gasto_inicio, "gasto_fim": gasto_fim}).dropna().copy()
    variacoes["variacao_%"] = (variacoes["gasto_fim"] / variacoes["gasto_inicio"] - 1) * 100
    variacoes = variacoes.sort_values("variacao_%", ascending=False)

    col_cresceu, col_caiu = st.columns(2)
    with col_cresceu:
        st.caption("Maior crescimento")
        st.dataframe(variacoes.head(3)[["variacao_%"]].style.format("{:+.1f}%"))
    with col_caiu:
        st.caption("Maior queda")
        st.dataframe(variacoes.tail(3)[["variacao_%"]].sort_values("variacao_%").style.format("{:+.1f}%"))

# --- drill-down: quem mais gastou num ano especifico ---
st.subheader("Quem mais gastou, entidade por entidade, num ano especifico")
ano_drill = st.selectbox("Escolhe um ano", options=sorted(df_filtrado["ano"].unique(), reverse=True))
top_entidades = (
    df_filtrado[df_filtrado["ano"] == ano_drill]
    .sort_values("valor", ascending=False)
    .head(10)[["orgao", "orgao_superior", "valor"]]
)
st.dataframe(top_entidades, hide_index=True, column_config={"valor": st.column_config.NumberColumn(format="R$ %.2f")})

# --- tabela crua, pra quem quiser conferir os numeros ---
with st.expander("Ver dados brutos"):
    st.dataframe(df_filtrado)
