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
        return br(f"R$ {valor / 1_000_000_000:,.1f} bi")
    if abs(valor) >= 1_000_000:
        return br(f"R$ {valor / 1_000_000:,.1f} mi")
    return br(f"R$ {valor:,.2f}")


def br(texto: str) -> str:
    # o Python formata número no padrão americano (1,234.5). Aqui eu troco
    # vírgula por ponto e vice-versa pra ficar no padrão brasileiro (1.234,5).
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


con = conectar()
df = carregar_despesas(con)

st.title("Despesas públicas federais")
st.caption(
    "Dados reais da API do Portal da Transparência (endpoint despesas/por-orgao, valor = 'pago'). "
    "Cobre os ministérios configurados em src/extract/client.py, ano a ano (a API não tem filtro mensal nesse endpoint)."
)

# --- filtros ---
col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    anos_selecionados = st.multiselect("Ano", options=sorted(df["ano"].unique()), default=sorted(df["ano"].unique()))
with col_filtro2:
    ministerios_selecionados = st.multiselect("Ministério", options=sorted(df["orgao_superior"].unique()), default=None, placeholder="Todos os ministérios")

df_filtrado = df.copy()
if anos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["ano"].isin(anos_selecionados)]
if ministerios_selecionados:
    df_filtrado = df_filtrado[df_filtrado["orgao_superior"].isin(ministerios_selecionados)]

if df_filtrado.empty:
    st.warning("Nenhum dado para os filtros selecionados.")
    st.stop()

totais_por_ano = df_filtrado.groupby("ano")["valor"].sum().sort_index()

# --- KPIs ---
st.subheader("Panorama do período")
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total gasto no período", formatar_moeda(df_filtrado["valor"].sum()))

if len(totais_por_ano) >= 2:
    ultimo_ano, penultimo_ano = totais_por_ano.index[-1], totais_por_ano.index[-2]
    variacao = (totais_por_ano.iloc[-1] / totais_por_ano.iloc[-2] - 1) * 100
    col2.metric(f"Variação {penultimo_ano} → {ultimo_ano}", br(f"{variacao:+.1f}%"))
else:
    col2.metric("Variação ano a ano", "precisa de 2+ anos")

ano_pico = totais_por_ano.idxmax()
col3.metric("Ano de maior gasto", f"{ano_pico}", formatar_moeda(totais_por_ano.max()))

ministerio_top = df_filtrado.groupby("orgao_superior")["valor"].sum().idxmax()
col4.metric("Ministério que mais gastou", ministerio_top)

# --- insights automaticos ---
# calculado em cima do periodo filtrado, não fixo - se rodar o pipeline
# pra mais anos, esses cards atualizam sozinhos.
st.subheader("Principais insights do período")

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
    col_i1.metric(f"Crescimento composto ({primeiro_ano_serie}-{ultimo_ano_serie})", br(f"{cagr * 100:+.1f}%") + " a.a.")

    if ministerio_do_salto:
        col_i2.metric(f"Maior salto isolado ({ano_maior_salto})", f"{pct_do_salto:+.0f}%", ministerio_do_salto)

    col_i3.metric(f"Top 3 ministérios ({ultimo_ano_serie})", f"{top3_share:.0f}% do total")

    if not coef_variacao.empty:
        ministerio_mais_volatil = coef_variacao.idxmax()
        col_i4.metric("Orçamento mais volátil", ministerio_mais_volatil, f"CV {coef_variacao.max():.0f}%")

    st.caption(
        "CAGR = taxa composta de crescimento anual. 'Maior salto isolado' identifica qual ministério puxou "
        "sozinho a maior alta percentual do total num único ano — ajuda a separar tendência real de evento "
        "pontual (ex.: programa emergencial). 'CV' (coeficiente de variação) mede o quanto o gasto de um "
        "ministério oscila ano a ano — quanto maior, menos previsível. Os nomes dos órgãos vêm como estão hoje na "
        "API, mesmo para anos antigos (reestruturação de pasta ministerial não muda o código SIAFI)."
    )
else:
    st.caption("Selecione 2 anos ou mais para ver os insights automáticos.")

# --- tendencia ---
st.subheader("Evolução do gasto por ano")
# divido por 1 bilhão pro eixo mostrar "780" em vez de "780,000,000,000"
# o ano vira texto pro eixo não mostrar "2,019"
serie_anual = (totais_por_ano / 1e9).rename("R$ bilhões").reset_index()
serie_anual["ano"] = serie_anual["ano"].astype(str)
st.line_chart(serie_anual, x="ano", y="R$ bilhões")

# --- ranking por ministerio ---
st.subheader("Ranking por ministério (soma do período filtrado)")
ranking = df_filtrado.groupby("orgao_superior")["valor"].sum().sort_values(ascending=False).reset_index()
ranking["R$ bilhões"] = ranking["valor"] / 1e9
st.bar_chart(ranking, x="orgao_superior", y="R$ bilhões", horizontal=True, x_label="", y_label="R$ bilhões")

# --- composicao por ministerio ao longo dos anos ---
st.subheader("De onde saiu o dinheiro, ano a ano")
composicao = df_filtrado.pivot_table(index="ano", columns="orgao_superior", values="valor", aggfunc="sum", fill_value=0)
composicao.index = composicao.index.astype(str)
st.area_chart(composicao / 1e9, y_label="R$ bilhões", x_label="ano")

# --- maiores variacoes no periodo ---
if len(anos_selecionados) >= 2:
    st.subheader(f"Quem mais cresceu e quem menos cresceu entre {min(anos_selecionados)} e {max(anos_selecionados)}")

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
        # se ninguém caiu de verdade, chamar de "maior queda" seria enganoso
        menores = variacoes.tail(3)[["variacao_%"]].sort_values("variacao_%")
        st.caption("Maior queda" if (menores["variacao_%"] < 0).any() else "Menor crescimento (nenhum ministério caiu)")
        st.dataframe(menores.style.format("{:+.1f}%"))

# --- drill-down: quem mais gastou num ano especifico ---
st.subheader("Quem mais gastou, entidade por entidade, num ano específico")
ano_drill = st.selectbox("Escolha um ano", options=sorted(df_filtrado["ano"].unique(), reverse=True))
top_entidades = (
    df_filtrado[df_filtrado["ano"] == ano_drill]
    .sort_values("valor", ascending=False)
    .head(10)[["orgao", "orgao_superior", "valor"]]
)
st.dataframe(top_entidades, hide_index=True, column_config={
    "orgao": "Órgão",
    "orgao_superior": "Ministério",
    "valor": st.column_config.NumberColumn("Valor pago", format="localized"),
})

# --- tabela crua, pra quem quiser conferir os numeros ---
with st.expander("Ver dados brutos"):
    st.dataframe(df_filtrado)
