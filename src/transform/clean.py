"""
aqui a gente pega o JSON cru que veio da API e transforma numa tabela
arrumada. a parte mais chata foi o formato de numero: a API devolve valor
em formato brasileiro tipo "1.234,56" (ponto de milhar, virgula decimal),
então tem que inverter isso antes de converter pra float.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def normalizar_despesas(registros_brutos: list[dict], ano: int, mes: int) -> pd.DataFrame:
    """Limpa a lista de despesas por orgao e devolve um DataFrame pronto pra carga."""
    linhas_ok = []
    descartados = 0

    for registro in registros_brutos:
        valor = _parse_valor_brasileiro(registro.get("valor"))
        orgao = registro.get("orgao")

        if valor is None or not orgao:
            descartados += 1
            continue

        linhas_ok.append({"orgao": orgao, "valor": valor, "ano": ano, "mes": mes})

    if descartados:
        logger.warning("descartei %d registro(s) de %d-%d por dado invalido", descartados, ano, mes)

    return pd.DataFrame(linhas_ok, columns=["orgao", "valor", "ano", "mes"])


def _parse_valor_brasileiro(valor_str) -> float | None:
    """Converte "1.234,56" pra 1234.56. Devolve None se não der pra converter."""
    if not valor_str:
        return None

    try:
        # tira ponto de milhar, troca virgula decimal por ponto
        limpo = str(valor_str).replace(".", "").replace(",", ".")
        return float(limpo)
    except ValueError:
        return None
