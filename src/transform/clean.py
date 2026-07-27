"""
aqui a gente pega o JSON cru que veio da API e transforma numa tabela
arrumada. a parte mais chata foi o formato de numero: a API devolve valor
em formato brasileiro tipo "1.234,56" (ponto de milhar, virgula decimal),
então tem que inverter isso antes de converter pra float.

uso o campo "pago" da API como "valor". a API devolve tres estagios da
despesa (empenhado, liquidado, pago) e "pago" é o que efetivamente saiu
do caixa, que é o numero que faz mais sentido pra um dashboard de "quanto
foi gasto".

guardo dois niveis de orgao: "orgao" (entidade vinculada, ex: uma
universidade federal especifica) e "orgao_superior" (o ministerio dela).
o dashboard usa orgao_superior pra comparacao no topo, ja que só tem 8
categorias e da pra olhar tudo de uma vez sem virar sopa de letrinha.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def normalizar_despesas(registros_brutos: list[dict], ano: int) -> pd.DataFrame:
    """Limpa a lista de despesas por orgao e devolve um DataFrame pronto pra carga."""
    linhas_ok = []
    descartados = 0

    for registro in registros_brutos:
        valor = _parse_valor_brasileiro(registro.get("pago"))
        orgao = registro.get("orgao")
        orgao_superior = registro.get("orgaoSuperior")

        if valor is None or not orgao or not orgao_superior:
            descartados += 1
            continue

        linhas_ok.append({"orgao": orgao, "orgao_superior": orgao_superior, "valor": valor, "ano": ano})

    if descartados:
        logger.warning("descartei %d registro(s) de %d por dado invalido", descartados, ano)

    return pd.DataFrame(linhas_ok, columns=["orgao", "orgao_superior", "valor", "ano"])


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
