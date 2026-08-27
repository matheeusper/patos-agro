import math
from dataclasses import asdict, dataclass, fields, replace

from patos_agro.erros import ErroEntrada


@dataclass(frozen=True)
class ParametrosReconstrucao:
    espacamento_plantas_manual: float | None = None
    espacamento_fileiras_manual: float | None = None
    comprimento_inicial_plantas: float = 2.6
    angulo_inicial_graus: float = 32.0
    lateral_inicial_fileiras: float = 0.28
    lacuna_normal_plantas: float = 10.0
    lacuna_curva_plantas: float = 18.0
    angulo_lacuna_curva_graus: float = 55.0
    corredor_seguranca_fileiras: float = 0.35
    quantil_arestas_curtas: float = 0.55
    fator_aresta_curta_plantas: float = 1.8
    tamanho_bloco_plantas: float = 12.0
    tamanho_bloco_diagonal: float = 0.12
    lateral_inicial_plantas: float = 0.22
    lacuna_fileiras: float = 3.0
    lateral_lacuna_normal_fileiras: float = 0.8
    lateral_lacuna_normal_plantas: float = 0.4
    lateral_lacuna_curva_fileiras: float = 3.0
    angulo_lacuna_normal_graus: float = 40.0
    angulo_extremidade_curva_graus: float = 35.0
    limiar_lacuna_curva_graus: float = 8.0
    pontos_tangente: int = 5
    iteracoes_lacunas: int = 4
    min_pontos_fileira: int = 4
    melhoria_minima_curva: float = 0.35
    mudanca_direcao_curva_graus: float = 15.0

    def como_dict(self):
        return asdict(self)


DEFINICOES_PARAMETROS = {
    "espacamento_plantas_manual": ("Espaçamento entre plantas", "m", 0.05, 20.0, 0.05, "basico", True),
    "espacamento_fileiras_manual": ("Espaçamento entre fileiras", "m", 0.10, 30.0, 0.05, "basico", True),
    "comprimento_inicial_plantas": ("Conexão inicial máxima", "× plantas", 1.2, 6.0, 0.1, "basico", False),
    "angulo_inicial_graus": ("Ângulo inicial máximo", "°", 5.0, 75.0, 1.0, "basico", False),
    "lateral_inicial_fileiras": ("Desvio lateral inicial", "× fileiras", 0.05, 1.5, 0.05, "basico", False),
    "lacuna_normal_plantas": ("Lacuna normal máxima", "× plantas", 2.0, 40.0, 1.0, "basico", False),
    "lacuna_curva_plantas": ("Lacuna curva máxima", "× plantas", 3.0, 60.0, 1.0, "basico", False),
    "angulo_lacuna_curva_graus": ("Diferença direcional em curvas", "°", 10.0, 85.0, 1.0, "basico", False),
    "corredor_seguranca_fileiras": ("Corredor de segurança", "× fileiras", 0.15, 0.75, 0.05, "basico", False),
    "quantil_arestas_curtas": ("Quantil de vizinhos curtos", "", 0.2, 0.9, 0.05, "avancado", False),
    "fator_aresta_curta_plantas": ("Alcance da direção local", "× plantas", 1.0, 4.0, 0.1, "avancado", False),
    "tamanho_bloco_plantas": ("Tamanho do bloco local", "× plantas", 4.0, 40.0, 1.0, "avancado", False),
    "tamanho_bloco_diagonal": ("Bloco relativo ao campo", "× diagonal", 0.03, 0.4, 0.01, "avancado", False),
    "lateral_inicial_plantas": ("Desvio lateral mínimo", "× plantas", 0.05, 1.0, 0.05, "avancado", False),
    "lacuna_fileiras": ("Alcance mínimo de lacuna", "× fileiras", 1.0, 10.0, 0.5, "avancado", False),
    "lateral_lacuna_normal_fileiras": ("Lateral de lacuna normal", "× fileiras", 0.1, 3.0, 0.1, "avancado", False),
    "lateral_lacuna_normal_plantas": ("Lateral normal mínima", "× plantas", 0.1, 2.0, 0.1, "avancado", False),
    "lateral_lacuna_curva_fileiras": ("Lateral de lacuna curva", "× fileiras", 0.5, 6.0, 0.25, "avancado", False),
    "angulo_lacuna_normal_graus": ("Ângulo de lacuna normal", "°", 10.0, 80.0, 1.0, "avancado", False),
    "angulo_extremidade_curva_graus": ("Ângulo da extremidade curva", "°", 10.0, 60.0, 1.0, "avancado", False),
    "limiar_lacuna_curva_graus": ("Limiar para lacuna curva", "°", 1.0, 30.0, 1.0, "avancado", False),
    "pontos_tangente": ("Pontos para estimar tangente", "", 3, 10, 1, "avancado", False),
    "iteracoes_lacunas": ("Iterações de reconexão", "", 1, 10, 1, "avancado", False),
    "min_pontos_fileira": ("Mínimo de pontos por fileira", "", 3, 20, 1, "avancado", False),
    "melhoria_minima_curva": ("Melhoria mínima da spline", "", 0.05, 0.8, 0.05, "avancado", False),
    "mudanca_direcao_curva_graus": ("Mudança para classificar curva", "°", 3.0, 60.0, 1.0, "avancado", False),
}


def parametros_de_dict(valores=None):
    if valores is None:
        return ParametrosReconstrucao()
    if not isinstance(valores, dict):
        raise ErroEntrada("os parâmetros devem ser enviados como um objeto JSON")
    permitidos = {campo.name for campo in fields(ParametrosReconstrucao)}
    desconhecidos = sorted(set(valores) - permitidos)
    if desconhecidos:
        raise ErroEntrada(f"parâmetros desconhecidos: {', '.join(desconhecidos)}")

    normalizados = {}
    inteiros = {"pontos_tangente", "iteracoes_lacunas", "min_pontos_fileira"}
    opcionais = {"espacamento_plantas_manual", "espacamento_fileiras_manual"}
    for nome, valor in valores.items():
        if nome in opcionais and valor is None:
            normalizados[nome] = None
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ErroEntrada(f"o parâmetro {nome} deve ser numérico")
        numero = float(valor)
        if not math.isfinite(numero):
            raise ErroEntrada(f"o parâmetro {nome} deve ser finito")
        _, _, minimo, maximo, _, _, _ = DEFINICOES_PARAMETROS[nome]
        if numero < minimo or numero > maximo:
            raise ErroEntrada(f"o parâmetro {nome} deve estar entre {minimo} e {maximo}")
        if nome in inteiros:
            if not numero.is_integer():
                raise ErroEntrada(f"o parâmetro {nome} deve ser inteiro")
            normalizados[nome] = int(numero)
        else:
            normalizados[nome] = numero
    return replace(ParametrosReconstrucao(), **normalizados)


def esquema_parametros():
    padrao = ParametrosReconstrucao()
    campos = []
    for nome, (rotulo, unidade, minimo, maximo, passo, grupo, opcional) in DEFINICOES_PARAMETROS.items():
        campos.append(
            {
                "nome": nome,
                "rotulo": rotulo,
                "unidade": unidade,
                "minimo": minimo,
                "maximo": maximo,
                "passo": passo,
                "grupo": grupo,
                "opcional": opcional,
                "padrao": getattr(padrao, nome),
            }
        )

    presets = {
        "padrao": padrao,
        "conservador": replace(
            padrao,
            comprimento_inicial_plantas=2.2,
            angulo_inicial_graus=25,
            lateral_inicial_fileiras=0.2,
            lacuna_normal_plantas=7,
            lacuna_curva_plantas=12,
            angulo_lacuna_curva_graus=40,
            corredor_seguranca_fileiras=0.45,
        ),
        "flexivel": replace(
            padrao,
            comprimento_inicial_plantas=3.2,
            angulo_inicial_graus=42,
            lateral_inicial_fileiras=0.4,
            lacuna_normal_plantas=14,
            lacuna_curva_plantas=24,
            angulo_lacuna_curva_graus=65,
            corredor_seguranca_fileiras=0.3,
        ),
        "curvas_lacunas": replace(
            padrao,
            angulo_inicial_graus=35,
            lateral_inicial_fileiras=0.3,
            lacuna_normal_plantas=12,
            lacuna_curva_plantas=24,
            angulo_lacuna_curva_graus=65,
            pontos_tangente=6,
        ),
    }
    return {
        "versao": 1,
        "grupos": {"basico": "Básicos", "avancado": "Avançados"},
        "campos": campos,
        "padrao": padrao.como_dict(),
        "presets": {nome: valor.como_dict() for nome, valor in presets.items()},
    }
