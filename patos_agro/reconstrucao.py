import math
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import make_splprep
from scipy.spatial import QhullError, cKDTree
from shapely.geometry import LineString

from patos_agro.erros import ErroProcessamento
from patos_agro.geometria import (
    arestas_delaunay,
    dados_basicos_arestas,
    estimar_direcoes_locais,
    estimar_escalas,
)
from patos_agro.grafo import componentes_conexos, conectar_lacunas, construir_grafo, ordenar_componente
from patos_agro.parametros import ParametrosReconstrucao, parametros_de_dict


@dataclass
class ResultadoReconstrucao:
    fileiras: list
    arestas: np.ndarray
    vetores: np.ndarray
    comprimentos: np.ndarray
    angulos: np.ndarray
    pontos_medios: np.ndarray
    direcoes: np.ndarray
    espacamento_plantas: float
    espacamento_fileiras: float
    longitudinal: np.ndarray
    lateral: np.ndarray
    estados_arestas: list
    pontuacoes_arestas: list
    adjacencias_iniciais: list
    adjacencias_finais: list
    conexoes_lacunas: list
    componentes: list
    componentes_ordenados: list
    pontes_lacunas: list
    pontes_candidatas: list
    pontes_rejeitadas: list
    parametros: ParametrosReconstrucao


# Calcula o RMSE ortogonal da melhor reta ajustada aos pontos.
def ajustar_reta_e_residuo(pontos):
    centralizadas = pontos - pontos.mean(axis=0)
    covariancia = centralizadas.T @ centralizadas
    valores, vetores = np.linalg.eigh(covariancia)
    direcao = vetores[:, np.argmax(valores)]
    normal = np.array([-direcao[1], direcao[0]])
    residuos = centralizadas @ normal
    return float(np.sqrt(np.mean(residuos**2)))


# Ajusta uma spline aos pontos e classifica a fileira como reta ou curva.
def ajustar_fileira(pontos, espacamento_plantas, parametros=None):
    parametros = parametros or ParametrosReconstrucao()
    grau = min(3, len(pontos) - 1)
    if len(pontos) > 2:
        rugosidade = np.linalg.norm(pontos[1:-1] - (pontos[:-2] + pontos[2:]) / 2, axis=1)
        sigma = float(np.median(rugosidade)) if len(rugosidade) else 0.0
    else:
        sigma = 0.0
    sigma = float(np.clip(sigma, max(0.03, 0.03 * espacamento_plantas), 0.35 * espacamento_plantas))
    pesos = np.full(len(pontos), 1 / sigma)

    spline, parametros_spline = make_splprep(
        [pontos[:, 0], pontos[:, 1]], w=pesos, k=grau, s=len(pontos)
    )
    comprimento_origem = np.linalg.norm(np.diff(pontos, axis=0), axis=1).sum()
    quantidade_amostras = int(np.clip(math.ceil(comprimento_origem / (espacamento_plantas / 2)) + 1, 50, 2000))
    parametros_amostra = np.linspace(0, 1, quantidade_amostras)
    amostrados = np.asarray(spline(parametros_amostra)).T
    ajustados_nos_pontos = np.asarray(spline(parametros_spline)).T
    rmse_spline = float(np.sqrt(np.mean(np.sum((ajustados_nos_pontos - pontos) ** 2, axis=1))))
    derivadas = np.asarray(spline.derivative()(parametros_amostra)).T
    direcoes_spline = np.unwrap(np.arctan2(derivadas[:, 1], derivadas[:, 0]))
    mudanca_direcao = float(np.sum(np.abs(np.diff(direcoes_spline))))

    rmse_reta = ajustar_reta_e_residuo(pontos)
    melhoria = 0.0 if rmse_reta <= 1e-9 else 1 - rmse_spline / rmse_reta
    tipo_fileira = (
        "curva"
        if melhoria >= parametros.melhoria_minima_curva
        and mudanca_direcao >= math.radians(parametros.mudanca_direcao_curva_graus)
        else "reta"
    )
    return LineString(amostrados), tipo_fileira


def _coordenadas_com_pontes(ordenados, coordenadas, pontes_por_aresta):
    combinadas = [coordenadas[ordenados[0]]]
    for primeiro, segundo in zip(ordenados, ordenados[1:]):
        ponte = pontes_por_aresta.get(tuple(sorted((primeiro, segundo))))
        if ponte is not None:
            pontos_ponte = np.asarray(ponte.geometria.coords)
            if ponte.primeiro != primeiro:
                pontos_ponte = pontos_ponte[::-1]
            combinadas.extend(pontos_ponte[1:-1])
        combinadas.append(coordenadas[segundo])
    return np.asarray(combinadas)


# Executa o agrupamento completo e cria as geometrias das fileiras.
def reconstruir_com_diagnostico(coordenadas, parametros=None):
    if isinstance(parametros, dict) or parametros is None:
        parametros = parametros_de_dict(parametros)
    try:
        arestas = arestas_delaunay(coordenadas)
    except QhullError as erro:
        raise ErroProcessamento(
            "não foi possível triangular os pontos; verifique a distribuição das coordenadas"
        ) from erro
    vetores, comprimentos, angulos, pontos_medios = dados_basicos_arestas(coordenadas, arestas)
    distancias_vizinhos = cKDTree(coordenadas).query(coordenadas, k=2)[0][:, 1]
    espacamento_plantas = float(np.median(distancias_vizinhos))
    if parametros.espacamento_plantas_manual is not None:
        espacamento_plantas = parametros.espacamento_plantas_manual
    direcoes = estimar_direcoes_locais(
        coordenadas,
        arestas,
        comprimentos,
        angulos,
        pontos_medios,
        espacamento_plantas,
        parametros,
    )
    espacamento_plantas, espacamento_fileiras, longitudinal, lateral = estimar_escalas(
        coordenadas, arestas, vetores, comprimentos, direcoes, parametros
    )
    diagnostico_grafo = {}
    adjacencias = construir_grafo(
        coordenadas,
        arestas,
        comprimentos,
        angulos,
        direcoes,
        espacamento_plantas,
        espacamento_fileiras,
        diagnostico=diagnostico_grafo,
        parametros=parametros,
    )
    adjacencias_iniciais = [set(vizinhos) for vizinhos in adjacencias]
    diagnostico_lacunas = {}
    adjacencias = conectar_lacunas(
        adjacencias,
        coordenadas,
        direcoes,
        espacamento_plantas,
        espacamento_fileiras,
        diagnostico=diagnostico_lacunas,
        parametros=parametros,
    )
    conexoes_lacunas = diagnostico_lacunas["conexoes"]
    pontes_lacunas = diagnostico_lacunas["pontes_aceitas"]
    pontes_candidatas = diagnostico_lacunas["pontes_candidatas"]
    pontes_rejeitadas = diagnostico_lacunas["pontes_rejeitadas"]
    pontes_por_aresta = {
        tuple(sorted((ponte.primeiro, ponte.segundo))): ponte for ponte in pontes_lacunas
    }

    fileiras = []
    componentes = componentes_conexos(adjacencias)
    componentes_ordenados = []
    for componente in componentes:
        ordenados = ordenar_componente(componente, adjacencias)
        componentes_ordenados.append(ordenados)
        if len(ordenados) < parametros.min_pontos_fileira:
            continue
        pontos_ajuste = _coordenadas_com_pontes(ordenados, coordenadas, pontes_por_aresta)
        geometria, tipo_fileira = ajustar_fileira(pontos_ajuste, espacamento_plantas, parametros)
        fileiras.append((geometria, tipo_fileira, min(ordenados)))
    fileiras.sort(key=lambda item: item[2])
    return ResultadoReconstrucao(
        fileiras=fileiras,
        arestas=arestas,
        vetores=vetores,
        comprimentos=comprimentos,
        angulos=angulos,
        pontos_medios=pontos_medios,
        direcoes=direcoes,
        espacamento_plantas=espacamento_plantas,
        espacamento_fileiras=espacamento_fileiras,
        longitudinal=longitudinal,
        lateral=lateral,
        estados_arestas=diagnostico_grafo["estados"],
        pontuacoes_arestas=diagnostico_grafo["pontuacoes"],
        adjacencias_iniciais=adjacencias_iniciais,
        adjacencias_finais=[set(vizinhos) for vizinhos in adjacencias],
        conexoes_lacunas=conexoes_lacunas,
        componentes=componentes,
        componentes_ordenados=componentes_ordenados,
        pontes_lacunas=pontes_lacunas,
        pontes_candidatas=pontes_candidatas,
        pontes_rejeitadas=pontes_rejeitadas,
        parametros=parametros,
    )


def reconstruir_fileiras(coordenadas, parametros=None):
    return reconstruir_com_diagnostico(coordenadas, parametros).fileiras
