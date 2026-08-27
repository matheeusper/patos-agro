import json
import math
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point

from patos_agro.io import criar_resultado_fileiras


CORES = {
    "pontos": "#1f6a4b",
    "duplicatas": "#c95a4f",
    "delaunay": "#9aa59e",
    "direcoes": "#4489a3",
    "transversais": "#806ea8",
    "selecionada": "#1f6a4b",
    "angulo": "#c95a4f",
    "comprimento": "#e28a43",
    "lateral": "#806ea8",
    "conflito": "#8c8175",
    "lacunas": "#d5a62e",
    "ponte_curva": "#e05d2f",
    "ponte_rejeitada": "#c95a4f",
    "componentes": "#4489a3",
    "descartados": "#c95a4f",
    "reta": "#1f6a4b",
    "curva": "#e28a43",
}


def _colecao(geometrias, propriedades, crs_utm):
    quadro = gpd.GeoDataFrame(propriedades, geometry=geometrias, crs=crs_utm).to_crs("EPSG:4326")
    return json.loads(quadro.to_json(drop_id=True))


def _pontos(coordenadas):
    return [Point(float(x), float(y)) for x, y in coordenadas]


def _linhas_arestas(coordenadas, arestas):
    return [LineString(coordenadas[[int(primeiro), int(segundo)]]) for primeiro, segundo in arestas]


def _arestas_adjacencias(adjacencias):
    return [
        (primeiro, segundo)
        for primeiro, vizinhos in enumerate(adjacencias)
        for segundo in sorted(vizinhos)
        if primeiro < segundo
    ]


def _camada(rotulo, cor, tipo, dados, *, espessura=2, tracejado=None, cores_por_tipo=None):
    camada = {
        "rotulo": rotulo,
        "cor": cor,
        "tipo": tipo,
        "espessura": espessura,
        "dados": dados,
    }
    if tracejado:
        camada["tracejado"] = tracejado
    if cores_por_tipo:
        camada["cores_por_tipo"] = cores_por_tipo
    return camada


def _metrica(rotulo, valor, unidade=None):
    metrica = {"rotulo": rotulo, "valor": valor}
    if unidade:
        metrica["unidade"] = unidade
    return metrica


def criar_resposta_visualizacao(dados_pontos, diagnostico, nome_arquivo, duracao_ms=None):
    coordenadas = dados_pontos.coordenadas
    crs_utm = dados_pontos.crs_utm
    arestas = diagnostico.arestas

    camadas = {}
    camadas["pontos"] = _camada(
        "Pontos únicos",
        CORES["pontos"],
        "ponto",
        _colecao(
            _pontos(coordenadas),
            [{"ponto_id": indice + 1} for indice in range(len(coordenadas))],
            crs_utm,
        ),
    )
    camadas["duplicatas"] = _camada(
        "Duplicatas removidas",
        CORES["duplicatas"],
        "ponto",
        _colecao(
            _pontos(dados_pontos.coordenadas_duplicadas),
            [{"motivo": "coordenada duplicada"} for _ in dados_pontos.coordenadas_duplicadas],
            crs_utm,
        ),
    )
    camadas["delaunay"] = _camada(
        "Arestas de Delaunay",
        CORES["delaunay"],
        "linha",
        _colecao(
            _linhas_arestas(coordenadas, arestas),
            [
                {"comprimento_m": round(float(comprimento), 2)}
                for comprimento in diagnostico.comprimentos
            ],
            crs_utm,
        ),
        espessura=1,
    )

    meio_comprimento = max(diagnostico.espacamento_plantas * 0.75, 0.05)
    segmentos_direcao = []
    for ponto, direcao in zip(coordenadas, diagnostico.direcoes):
        deslocamento = meio_comprimento * np.array([math.cos(direcao), math.sin(direcao)])
        segmentos_direcao.append(LineString([ponto - deslocamento, ponto + deslocamento]))
    camadas["direcoes"] = _camada(
        "Direções locais",
        CORES["direcoes"],
        "linha",
        _colecao(
            segmentos_direcao,
            [{"angulo_graus": round(math.degrees(float(direcao)), 2)} for direcao in diagnostico.direcoes],
            crs_utm,
        ),
        espessura=2,
    )

    mascara_transversal = (
        (diagnostico.lateral > 0.75 * diagnostico.comprimentos)
        & (diagnostico.lateral > 0.45 * diagnostico.espacamento_plantas)
        & (diagnostico.comprimentos < np.quantile(diagnostico.comprimentos, 0.8))
    )
    indices_transversais = np.flatnonzero(mascara_transversal)
    camadas["transversais"] = _camada(
        "Referências transversais",
        CORES["transversais"],
        "linha",
        _colecao(
            _linhas_arestas(coordenadas, arestas[indices_transversais]),
            [
                {
                    "distancia_lateral_m": round(float(diagnostico.lateral[indice]), 2),
                    "comprimento_m": round(float(diagnostico.comprimentos[indice]), 2),
                }
                for indice in indices_transversais
            ],
            crs_utm,
        ),
        espessura=2,
    )

    grupos_estados = {
        "arestas_selecionadas": ({"selecionada"}, "Selecionadas", CORES["selecionada"], None),
        "rejeitadas_angulo": ({"rejeitada_angulo"}, "Rejeitadas por ângulo", CORES["angulo"], "5 5"),
        "rejeitadas_comprimento": (
            {"rejeitada_comprimento"},
            "Rejeitadas por distância",
            CORES["comprimento"],
            "5 5",
        ),
        "rejeitadas_lateral": ({"rejeitada_lateral"}, "Rejeitadas por lateral", CORES["lateral"], "5 5"),
        "rejeitadas_conflito": (
            {"rejeitada_lado", "rejeitada_grau", "rejeitada_ciclo"},
            "Rejeitadas por conflito",
            CORES["conflito"],
            "3 5",
        ),
    }
    for identificador, (estados, rotulo, cor, tracejado) in grupos_estados.items():
        indices = [indice for indice, estado in enumerate(diagnostico.estados_arestas) if estado in estados]
        camadas[identificador] = _camada(
            rotulo,
            cor,
            "linha",
            _colecao(
                _linhas_arestas(coordenadas, arestas[indices]),
                [
                    {
                        "estado": diagnostico.estados_arestas[indice],
                        "pontuacao": diagnostico.pontuacoes_arestas[indice],
                    }
                    for indice in indices
                ],
                crs_utm,
            ),
            espessura=2 if identificador == "arestas_selecionadas" else 1,
            tracejado=tracejado,
        )

    arestas_iniciais = _arestas_adjacencias(diagnostico.adjacencias_iniciais)
    camadas["grafo_inicial"] = _camada(
        "Grafo inicial",
        CORES["selecionada"],
        "linha",
        _colecao(
            _linhas_arestas(coordenadas, np.asarray(arestas_iniciais, dtype=int)),
            [{"origem": "conexão inicial"} for _ in arestas_iniciais],
            crs_utm,
        ),
        espessura=3,
    )
    camadas["lacunas"] = _camada(
        "Lacunas conectadas",
        CORES["lacunas"],
        "linha",
        _colecao(
            _linhas_arestas(coordenadas, np.asarray(diagnostico.conexoes_lacunas, dtype=int)),
            [{"origem": "reconexão de lacuna"} for _ in diagnostico.conexoes_lacunas],
            crs_utm,
        ),
        espessura=4,
        tracejado="8 5",
    )
    camadas["pontes_curvas"] = _camada(
        "Pontes curvas seguras",
        CORES["ponte_curva"],
        "linha",
        _colecao(
            [ponte.geometria for ponte in diagnostico.pontes_lacunas],
            [
                {
                    "primeiro": ponte.primeiro,
                    "segundo": ponte.segundo,
                    "folga_minima_m": round(ponte.folga_minima, 2),
                    "fator_curvatura": ponte.fator_curvatura,
                }
                for ponte in diagnostico.pontes_lacunas
            ],
            crs_utm,
        ),
        espessura=5,
    )
    camadas["pontes_curvas_rejeitadas"] = _camada(
        "Pontes curvas rejeitadas",
        CORES["ponte_rejeitada"],
        "linha",
        _colecao(
            [item["ponte"].geometria for item in diagnostico.pontes_rejeitadas],
            [
                {
                    "primeiro": item["ponte"].primeiro,
                    "segundo": item["ponte"].segundo,
                    "motivo": item["motivo"],
                    "folga_minima_m": round(item["ponte"].folga_minima, 2),
                }
                for item in diagnostico.pontes_rejeitadas
            ],
            crs_utm,
        ),
        espessura=2,
        tracejado="4 6",
    )
    arestas_finais = _arestas_adjacencias(diagnostico.adjacencias_finais)
    camadas["grafo_final"] = _camada(
        "Grafo após lacunas",
        CORES["selecionada"],
        "linha",
        _colecao(
            _linhas_arestas(coordenadas, np.asarray(arestas_finais, dtype=int)),
            [{"origem": "grafo final"} for _ in arestas_finais],
            crs_utm,
        ),
        espessura=2,
    )

    geometrias_validas = []
    propriedades_validas = []
    geometrias_descartadas = []
    propriedades_descartadas = []
    for indice, ordenados in enumerate(diagnostico.componentes_ordenados, start=1):
        geometria = LineString(coordenadas[ordenados])
        propriedades = {"componente_id": indice, "quantidade_pontos": len(ordenados)}
        if len(ordenados) >= diagnostico.parametros.min_pontos_fileira:
            geometrias_validas.append(geometria)
            propriedades_validas.append(propriedades)
        else:
            geometrias_descartadas.append(geometria)
            propriedades_descartadas.append(propriedades)
    camadas["componentes_validos"] = _camada(
        "Componentes válidos",
        CORES["componentes"],
        "linha",
        _colecao(geometrias_validas, propriedades_validas, crs_utm),
        espessura=3,
    )
    camadas["componentes_descartados"] = _camada(
        "Componentes descartados",
        CORES["descartados"],
        "linha",
        _colecao(geometrias_descartadas, propriedades_descartadas, crs_utm),
        espessura=3,
        tracejado="5 5",
    )

    resultado = criar_resultado_fileiras(diagnostico.fileiras, crs_utm)
    geojson_final = json.loads(resultado.to_json(drop_id=True))
    camadas["fileiras_finais"] = _camada(
        "Fileiras finais",
        CORES["reta"],
        "linha",
        geojson_final,
        espessura=4,
        cores_por_tipo={"reta": CORES["reta"], "curva": CORES["curva"]},
    )

    contagem_estados = Counter(diagnostico.estados_arestas)
    retas = sum(1 for _, tipo, _ in diagnostico.fileiras if tipo == "reta")
    curvas = len(diagnostico.fileiras) - retas
    componentes_validos = sum(
        1
        for grupo in diagnostico.componentes_ordenados
        if len(grupo) >= diagnostico.parametros.min_pontos_fileira
    )
    componentes_descartados = len(diagnostico.componentes_ordenados) - componentes_validos

    etapas = [
        {
            "id": "pontos",
            "titulo": "Pontos recebidos",
            "descricao": "A entrada é validada, reprojetada para UTM e tem coordenadas repetidas removidas.",
            "camadas": ["pontos", "duplicatas"],
            "metricas": [
                _metrica("Recebidos", dados_pontos.quantidade_original),
                _metrica("Pontos únicos", dados_pontos.quantidade_unica),
                _metrica("Duplicatas", dados_pontos.duplicatas_removidas),
            ],
        },
        {
            "id": "delaunay",
            "titulo": "Triangulação Delaunay",
            "descricao": "Conecta vizinhos espaciais para formar o conjunto inicial de arestas possíveis.",
            "camadas": ["delaunay", "pontos"],
            "metricas": [_metrica("Arestas", len(arestas)), _metrica("Pontos", len(coordenadas))],
        },
        {
            "id": "direcoes",
            "titulo": "Direções locais",
            "descricao": "Blocos sobrepostos estimam a orientação predominante da fileira em cada ponto.",
            "camadas": ["direcoes", "pontos"],
            "metricas": [
                _metrica("Direções", len(diagnostico.direcoes)),
                _metrica("Blocos cobertos", len(diagnostico.direcoes)),
            ],
        },
        {
            "id": "escalas",
            "titulo": "Estimativa de escalas",
            "descricao": "Distâncias entre vizinhos estimam os espaçamentos de plantas e de fileiras.",
            "camadas": ["transversais", "direcoes", "pontos"],
            "metricas": [
                _metrica("Entre plantas", round(diagnostico.espacamento_plantas, 2), "m"),
                _metrica("Entre fileiras", round(diagnostico.espacamento_fileiras, 2), "m"),
                _metrica("Referências", len(indices_transversais)),
            ],
        },
        {
            "id": "classificacao",
            "titulo": "Classificação de arestas",
            "descricao": "Cada conexão é aceita ou rejeitada por ângulo, distância, deslocamento lateral ou conflito.",
            "camadas": list(grupos_estados),
            "metricas": [
                _metrica("Selecionadas", contagem_estados["selecionada"]),
                _metrica("Por ângulo", contagem_estados["rejeitada_angulo"]),
                _metrica("Por distância", contagem_estados["rejeitada_comprimento"]),
                _metrica("Por lateral", contagem_estados["rejeitada_lateral"]),
            ],
        },
        {
            "id": "grafo",
            "titulo": "Grafo inicial",
            "descricao": "As melhores arestas formam cadeias sem ciclos e com no máximo dois vizinhos por ponto.",
            "camadas": ["grafo_inicial", "pontos"],
            "metricas": [
                _metrica("Conexões", len(arestas_iniciais)),
                _metrica("Pontos conectados", sum(bool(v) for v in diagnostico.adjacencias_iniciais)),
            ],
        },
        {
            "id": "lacunas",
            "titulo": "Conexão de lacunas",
            "descricao": "Extremidades compatíveis são unidas para reconstruir falhas no plantio sem fechar ciclos.",
            "camadas": [
                "grafo_final",
                "lacunas",
                "pontes_curvas",
                "pontes_curvas_rejeitadas",
                "pontos",
            ],
            "metricas": [
                _metrica("Lacunas unidas", len(diagnostico.conexoes_lacunas)),
                _metrica("Pontes avaliadas", len(diagnostico.pontes_candidatas)),
                _metrica("Pontes curvas", len(diagnostico.pontes_lacunas)),
                _metrica("Pontes rejeitadas", len(diagnostico.pontes_rejeitadas)),
                _metrica("Conexões finais", len(arestas_finais)),
            ],
        },
        {
            "id": "componentes",
            "titulo": "Componentes e splines",
            "descricao": "Os componentes são ordenados; grupos com quatro ou mais pontos recebem uma spline suavizada.",
            "camadas": ["componentes_validos", "componentes_descartados", "fileiras_finais", "pontos"],
            "metricas": [
                _metrica("Componentes válidos", componentes_validos),
                _metrica("Descartados", componentes_descartados),
                _metrica("Splines", len(diagnostico.fileiras)),
            ],
        },
        {
            "id": "resultado",
            "titulo": "Fileiras finais",
            "descricao": "As linhas ajustadas são classificadas como retas ou curvas e preparadas para exportação.",
            "camadas": ["fileiras_finais", "pontos"],
            "metricas": [
                _metrica("Fileiras", len(diagnostico.fileiras)),
                _metrica("Retas", retas),
                _metrica("Curvas", curvas),
                _metrica(
                    "Comprimento total",
                    round(sum(float(fileira[0].length) for fileira in diagnostico.fileiras), 2),
                    "m",
                ),
            ],
        },
    ]

    componentes_aproveitados = [
        grupo
        for grupo in diagnostico.componentes_ordenados
        if len(grupo) >= diagnostico.parametros.min_pontos_fileira
    ]
    pontos_aproveitados = len({indice for grupo in componentes_aproveitados for indice in grupo})
    comprimento_total = round(
        sum(float(fileira[0].length) for fileira in diagnostico.fileiras), 2
    )
    cruzamentos = sum(
        geometria.crosses(outra)
        for indice, (geometria, _, _) in enumerate(diagnostico.fileiras)
        for outra, _, _ in diagnostico.fileiras[indice + 1 :]
    )
    resumo = {
        "fileiras": len(diagnostico.fileiras),
        "pontos_aproveitados": pontos_aproveitados,
        "pontos_descartados": len(coordenadas) - pontos_aproveitados,
        "lacunas_normais": len(diagnostico.conexoes_lacunas) - len(diagnostico.pontes_lacunas),
        "lacunas_curvas": len(diagnostico.pontes_lacunas),
        "comprimento_total_m": comprimento_total,
        "cruzamentos": cruzamentos,
    }
    if duracao_ms is not None:
        resumo["duracao_ms"] = round(float(duracao_ms), 1)

    nome_saida = f"{Path(nome_arquivo).stem}.geojson"
    return {
        "arquivo": {
            "nome": Path(nome_arquivo).name,
            "nome_saida": nome_saida,
            "camada": dados_pontos.camada,
            "crs_original": str(dados_pontos.crs_original),
            "crs_processamento": str(crs_utm),
        },
        "camadas": camadas,
        "etapas": etapas,
        "parametros": diagnostico.parametros.como_dict(),
        "resumo": resumo,
        "resultado": {"nome": nome_saida, "geojson": geojson_final},
    }
