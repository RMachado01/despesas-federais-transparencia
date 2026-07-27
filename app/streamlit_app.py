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

# --- insights automaticos ---
# calculado em cima do periodo filtrado, não fixo - se rodar o pipeline
# pra mais anos, esses cards atualizam sozinhos.
st.subheader("Principais insights do periodo")

anos_disponiveis = sorted(df_filtrado["ano"].unique())
if len(anos_disponiveis) >= 2:
    primeiro_ano_serie, ultimo_ano_serie = anos_disponiveis[0], anos_disponiveis[-1]
    cagr = (totais_por_ano.loc[ultimo_ano_serie] / totais_por_ano.loc[primeiro_ano_serie]) ** (1 / (ultimo_ano_serie - primeiro_ano_serie)) - 1

    # "maior salto isolado": olha ano a ano qual foi a maior alta percentual
    # do total, e dentro desse ano especifico, qual ministerio mais empurrou
    # esse numero. serve pra separar "tendencia geral" de "evento pontual"
    # (tipo um programa emergencial que so durou um ano)
    variacao_anual = totais_por_ano.pct_change() * 100
    ano_maior_salto = variacao_anual.idxmax()
    ano_anterior_ao_salto = ano_maior_salto - 1

    ministerio_do_salto, pct_do_salto = None, None
    if ano_anterior_ao_salto in anos_disponiveis:
        antes = df_filtrado[df_filtrado["ano"] == ano_anterior_ao_salto].groupby("orgao_superior")["valor"].sum()
        depois = df_filtrado[df_filtrado["ano"] == ano_maior_salto].groupby("orgao_superior")["valor"].sum()
        base = pd.DataFrame({"antes": antes, "depois": depois}).dropna()
        deltas = base.assign(delta_pct=(base["depois"] / base["antes"] - 1) * 100)
        if not deltas.empty:
            ministerio_do_salto = deltas["delta_pct"].idxmax()
            pct_do_salto = deltas.loc[ministerio_do_salto, "delta_pct"]

    gasto_ultimo_ano = df_filtrado[df_filtrado["ano"] == ultimo_ano_serie].groupby("orgao_superior")["valor"].sum().sort_values(ascending=False)
    top3_share = (gasto_ultimo_ano.head(3).sum() / gasto_ultimo_ano.sum() * 100) if gasto_ultimo_ano.sum() else 0

    serie_por_ministerio = df_filtrado.groupby(["orgao_superior", "ano"])["valor"].sum().unstack()
    coef_variacao = (serie_por_ministerio.std(axis=1) / serie_por_ministerio.mean(axis=1) * 100).dropna()

    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    col_i1.metric(f"Crescimento composto ({primeiro_ano_serie}-{ultimo_ano_serie})", f"{cagr * 100:+.1f}% a.a.")

    if ministerio_do_salto:
        col_i2.metric(f"Maior salto isolado ({ano_maior_salto})", f"{pct_do_salto:+.0f}%", ministerio_do_salto)

    col_i3.metric(f"Top 3 ministerios ({ultimo_ano_serie})", f"{top3_share:.0f}% do total")

    if not coef_variacao.empty:
        ministerio_mais_volatil = coef_variacao.idxmax()
        col_i4.metric("Orcamento mais volatil", ministerio_mais_volatil, f"CV {coef_variacao.max():.0f}%")

    st.caption(
        "CAGR = taxa composta de crescimento anual. 'Maior salto isolado' identifica qual ministerio puxou "
        "sozinho a maior alta percentual do total num unico ano - ajuda a separar tendencia real de evento "
        "pontual (ex: programa emergencial). 'CV' (coeficiente de variacao) mede o quanto o gasto de um "
        "ministerio oscila ano a ano - quanto maior, menos previsivel. Nomes de orgao vem como estao hoje na "
        "API, mesmo pra anos antigos (reestruturacao de pasta ministerial não muda o codigo SIAFI)."
    )
else:
    st.caption("Selecione 2 anos ou mais pra ver os insights automaticos.")

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

    base_variacoes = pd.DataFrame({"gasto_inicio": gasto_inicio, "gasto_fim": gasto_fim}).dropna()
    variacoes = base_variacoes.assign(
        **{"variacao_%": (base_variacoes["gasto_fim"] / base_variacoes["gasto_inicio"] - 1) * 100}
    ).sort_values("variacao_%", ascending=False)

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
