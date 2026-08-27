import math

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from patos_agro.parametros import ParametrosReconstrucao


# Calcula a menor diferença entre duas direções axiais.
def diferenca_angular(angulo_a, angulo_b):
    return np.abs((angulo_a - angulo_b + np.pi / 2) % np.pi - np.pi / 2)


# Calcula a direção axial média, considerando pesos opcionais.
def media_axial(angulos, pesos=None):
    if len(angulos) == 0:
        return 0.0
    if pesos is None:
        pesos = np.ones(len(angulos))
    x = np.sum(pesos * np.cos(2 * angulos))
    y = np.sum(pesos * np.sin(2 * angulos))
    return 0.5 * math.atan2(y, x) % np.pi


# Cria as arestas únicas da triangulação de Delaunay.
def arestas_delaunay(coordenadas):
    centralizadas = coordenadas - coordenadas.mean(axis=0)
    triangulacao = Delaunay(centralizadas, qhull_options="Qbb Qc QJ Q12")

    arestas = set()
    quantidade_pontos = len(coordenadas)
    for triangulo in triangulacao.simplices:
        indices_validos = sorted(int(indice) for indice in triangulo if indice < quantidade_pontos)
        for posicao, primeiro in enumerate(indices_validos):
            for segundo in indices_validos[posicao + 1 :]:
                arestas.add((primeiro, segundo))
    return np.asarray(sorted(arestas), dtype=int)


# Calcula vetores, comprimentos, ângulos e pontos médios das arestas.
def dados_basicos_arestas(coordenadas, arestas):
    vetores = coordenadas[arestas[:, 1]] - coordenadas[arestas[:, 0]]
    comprimentos = np.linalg.norm(vetores, axis=1)
    angulos = np.mod(np.arctan2(vetores[:, 1], vetores[:, 0]), np.pi)
    pontos_medios = (coordenadas[arestas[:, 0]] + coordenadas[arestas[:, 1]]) / 2
    return vetores, comprimentos, angulos, pontos_medios


# Estima a direção das fileiras em blocos locais sobrepostos.
def estimar_direcoes_locais(
    coordenadas,
    arestas,
    comprimentos,
    angulos,
    pontos_medios,
    espacamento_plantas,
    parametros=None,
):
    parametros = parametros or ParametrosReconstrucao()
    limite_curto = min(
        np.quantile(comprimentos, parametros.quantil_arestas_curtas),
        parametros.fator_aresta_curta_plantas * espacamento_plantas,
    )
    mascara_curta = comprimentos <= max(limite_curto, 1.05 * espacamento_plantas)
    if np.count_nonzero(mascara_curta) < 3:
        mascara_curta = comprimentos <= np.quantile(comprimentos, 0.7)

    minimo = coordenadas.min(axis=0)
    maximo = coordenadas.max(axis=0)
    diagonal = np.linalg.norm(maximo - minimo)
    tamanho_bloco = max(
        parametros.tamanho_bloco_plantas * espacamento_plantas,
        diagonal * parametros.tamanho_bloco_diagonal,
    )
    passo = tamanho_bloco / 2
    inicio = minimo - 0.01
    centros_blocos_x = np.arange(inicio[0], maximo[0] + passo, passo)
    centros_blocos_y = np.arange(inicio[1], maximo[1] + passo, passo)

    vetores_duplicados = np.zeros((len(coordenadas), 2), dtype=float)
    pesos_por_ponto = np.zeros(len(coordenadas), dtype=float)
    for centro_x in centros_blocos_x:
        for centro_y in centros_blocos_y:
            arestas_internas = (
                mascara_curta
                & (np.abs(pontos_medios[:, 0] - centro_x) <= tamanho_bloco / 2)
                & (np.abs(pontos_medios[:, 1] - centro_y) <= tamanho_bloco / 2)
            )
            if np.count_nonzero(arestas_internas) < 3:
                continue
            angulos_locais = angulos[arestas_internas]
            comprimentos_locais = comprimentos[arestas_internas]
            direcao_local = media_axial(angulos_locais, 1 / np.maximum(comprimentos_locais, 1e-9))
            pontos_internos = (
                (np.abs(coordenadas[:, 0] - centro_x) <= tamanho_bloco / 2)
                & (np.abs(coordenadas[:, 1] - centro_y) <= tamanho_bloco / 2)
            )
            distancia = np.linalg.norm(coordenadas[pontos_internos] - [centro_x, centro_y], axis=1)
            pesos_pontos = np.maximum(0.05, 1 - distancia / (tamanho_bloco / math.sqrt(2)))
            vetores_duplicados[pontos_internos, 0] += pesos_pontos * math.cos(2 * direcao_local)
            vetores_duplicados[pontos_internos, 1] += pesos_pontos * math.sin(2 * direcao_local)
            pesos_por_ponto[pontos_internos] += pesos_pontos

    direcao_global = media_axial(angulos[mascara_curta], 1 / np.maximum(comprimentos[mascara_curta], 1e-9))
    direcoes = np.full(len(coordenadas), direcao_global, dtype=float)
    disponiveis = pesos_por_ponto > 0
    direcoes[disponiveis] = (
        0.5 * np.arctan2(vetores_duplicados[disponiveis, 1], vetores_duplicados[disponiveis, 0])
    ) % np.pi
    return direcoes


# Estima os espaçamentos entre plantas e entre fileiras.
def estimar_escalas(coordenadas, arestas, vetores, comprimentos, direcoes, parametros=None):
    parametros = parametros or ParametrosReconstrucao()
    distancias_vizinhos = cKDTree(coordenadas).query(coordenadas, k=2)[0][:, 1]
    espacamento_plantas = float(np.median(distancias_vizinhos))
    if parametros.espacamento_plantas_manual is not None:
        espacamento_plantas = parametros.espacamento_plantas_manual

    direcoes_medias = media_axial_pares(direcoes[arestas[:, 0]], direcoes[arestas[:, 1]])
    tangentes = np.column_stack((np.cos(direcoes_medias), np.sin(direcoes_medias)))
    longitudinal = np.abs(np.sum(vetores * tangentes, axis=1))
    lateral = np.abs(vetores[:, 0] * tangentes[:, 1] - vetores[:, 1] * tangentes[:, 0])
    mascara_transversal = (
        (lateral > 0.75 * comprimentos)
        & (lateral > 0.45 * espacamento_plantas)
        & (comprimentos < np.quantile(comprimentos, 0.8))
    )
    if np.count_nonzero(mascara_transversal) >= 3:
        espacamento_fileiras = float(np.median(lateral[mascara_transversal]))
    else:
        espacamento_fileiras = 2.5 * espacamento_plantas
    espacamento_fileiras = max(espacamento_fileiras, 0.75 * espacamento_plantas)
    if parametros.espacamento_fileiras_manual is not None:
        espacamento_fileiras = parametros.espacamento_fileiras_manual
    return espacamento_plantas, espacamento_fileiras, longitudinal, lateral


# Calcula a direção axial média de cada par de ângulos.
def media_axial_pares(primeiro, segundo):
    x = np.cos(2 * primeiro) + np.cos(2 * segundo)
    y = np.sin(2 * primeiro) + np.sin(2 * segundo)
    return (0.5 * np.arctan2(y, x)) % np.pi
