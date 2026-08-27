import math
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from patos_agro.geometria import diferenca_angular, media_axial_pares
from patos_agro.parametros import ParametrosReconstrucao


@dataclass
class PonteLacuna:
    primeiro: int
    segundo: int
    geometria: LineString
    folga_minima: float
    fator_curvatura: float
    tipo: str = "curva"


# Encontra os componentes conexos formados pelas arestas do grafo.
def componentes_conexos(adjacencias):
    componentes = []
    visitados = set()
    for inicio in range(len(adjacencias)):
        if inicio in visitados or not adjacencias[inicio]:
            continue
        pilha = [inicio]
        componente = []
        visitados.add(inicio)
        while pilha:
            atual = pilha.pop()
            componente.append(atual)
            for vizinho in adjacencias[atual]:
                if vizinho not in visitados:
                    visitados.add(vizinho)
                    pilha.append(vizinho)
        componentes.append(componente)
    return componentes


# Verifica se uma nova conexão criaria um ciclo no grafo.
def cria_ciclo(adjacencias, primeiro, segundo):
    pilha = [primeiro]
    visitados = {primeiro}
    while pilha:
        atual = pilha.pop()
        if atual == segundo:
            return True
        for vizinho in adjacencias[atual]:
            if vizinho not in visitados:
                visitados.add(vizinho)
                pilha.append(vizinho)
    return False


def adicionar_conexoes_sem_ciclo(adjacencias, conexoes):
    quantidade_adicionada = 0
    for primeiro, segundo in conexoes:
        if cria_ciclo(adjacencias, primeiro, segundo):
            continue
        adjacencias[primeiro].add(segundo)
        adjacencias[segundo].add(primeiro)
        quantidade_adicionada += 1
    return quantidade_adicionada


# Filtra as arestas candidatas e monta o grafo das fileiras.
def construir_grafo(
    coordenadas,
    arestas,
    comprimentos,
    angulos,
    direcoes,
    espacamento_plantas,
    espacamento_fileiras,
    diagnostico=None,
    parametros=None,
):
    parametros = parametros or ParametrosReconstrucao()
    candidatos = []
    estados = [None] * len(arestas)
    pontuacoes = [None] * len(arestas)
    indice_por_aresta = {tuple(map(int, aresta)): indice for indice, aresta in enumerate(arestas)}
    comprimento_maximo = parametros.comprimento_inicial_plantas * espacamento_plantas
    lateral_maxima = max(
        parametros.lateral_inicial_fileiras * espacamento_fileiras,
        parametros.lateral_inicial_plantas * espacamento_plantas,
    )
    for indice_aresta, (primeiro, segundo) in enumerate(arestas):
        direcao = angulos[indice_aresta]
        erro_primeiro = float(diferenca_angular(direcao, direcoes[primeiro]))
        erro_segundo = float(diferenca_angular(direcao, direcoes[segundo]))
        if max(erro_primeiro, erro_segundo) > math.radians(parametros.angulo_inicial_graus):
            estados[indice_aresta] = "rejeitada_angulo"
            continue
        if comprimentos[indice_aresta] > comprimento_maximo:
            estados[indice_aresta] = "rejeitada_comprimento"
            continue
        direcao_media = media_axial_pares(
            np.asarray([direcoes[primeiro]]), np.asarray([direcoes[segundo]])
        )[0]
        tangente = np.array([math.cos(direcao_media), math.sin(direcao_media)])
        vetor = coordenadas[segundo] - coordenadas[primeiro]
        lateral = abs(vetor[0] * tangente[1] - vetor[1] * tangente[0])
        if lateral > lateral_maxima:
            estados[indice_aresta] = "rejeitada_lateral"
            continue
        pontuacao = (
            comprimentos[indice_aresta] / espacamento_plantas
            + 1.5 * (erro_primeiro + erro_segundo) / math.radians(parametros.angulo_inicial_graus)
            + 2.0 * lateral / lateral_maxima
        )
        estados[indice_aresta] = "candidata"
        pontuacoes[indice_aresta] = float(pontuacao)
        candidatos.append((pontuacao, int(primeiro), int(segundo)))

    adjacencias = [set() for _ in coordenadas]
    lados_ocupados = [set() for _ in coordenadas]
    for _, primeiro, segundo in sorted(candidatos):
        indice_aresta = indice_por_aresta[(primeiro, segundo)]
        vetor = coordenadas[segundo] - coordenadas[primeiro]
        tangente_primeiro = np.array([math.cos(direcoes[primeiro]), math.sin(direcoes[primeiro])])
        tangente_segundo = np.array([math.cos(direcoes[segundo]), math.sin(direcoes[segundo])])
        lado_primeiro = 1 if np.dot(vetor, tangente_primeiro) >= 0 else -1
        lado_segundo = 1 if np.dot(-vetor, tangente_segundo) >= 0 else -1
        if lado_primeiro in lados_ocupados[primeiro] or lado_segundo in lados_ocupados[segundo]:
            estados[indice_aresta] = "rejeitada_lado"
            continue
        if len(adjacencias[primeiro]) >= 2 or len(adjacencias[segundo]) >= 2:
            estados[indice_aresta] = "rejeitada_grau"
            continue
        if cria_ciclo(adjacencias, primeiro, segundo):
            estados[indice_aresta] = "rejeitada_ciclo"
            continue
        adjacencias[primeiro].add(segundo)
        adjacencias[segundo].add(primeiro)
        lados_ocupados[primeiro].add(lado_primeiro)
        lados_ocupados[segundo].add(lado_segundo)
        estados[indice_aresta] = "selecionada"
    if diagnostico is not None:
        diagnostico.update(estados=estados, pontuacoes=pontuacoes)
    return adjacencias


# Calcula o vetor que aponta para fora de uma extremidade.
def vetor_externo_extremidade(extremidade, adjacencias, coordenadas, direcao_local):
    if adjacencias[extremidade]:
        vizinho = next(iter(adjacencias[extremidade]))
        vetor = coordenadas[extremidade] - coordenadas[vizinho]
        norma = np.linalg.norm(vetor)
        if norma > 0:
            return vetor / norma
    tangente = np.array([math.cos(direcao_local), math.sin(direcao_local)])
    return tangente


def _tangente_externa_robusta(extremidade, ordenados, coordenadas, quantidade_pontos):
    if len(ordenados) < 2:
        return np.array([1.0, 0.0])
    if extremidade == ordenados[0]:
        locais = ordenados[:quantidade_pontos]
        referencia = coordenadas[ordenados[0]] - coordenadas[ordenados[1]]
    else:
        locais = ordenados[-quantidade_pontos:]
        referencia = coordenadas[ordenados[-1]] - coordenadas[ordenados[-2]]
    pontos = coordenadas[locais]
    centralizados = pontos - pontos.mean(axis=0)
    _, _, vetores = np.linalg.svd(centralizados, full_matrices=False)
    tangente = vetores[0]
    if np.dot(tangente, referencia) < 0:
        tangente = -tangente
    norma = np.linalg.norm(tangente)
    return tangente / norma if norma > 0 else referencia / np.linalg.norm(referencia)


def _amostrar_ponte_curva(inicio, fim, tangente_inicio, tangente_fim, fator, espacamento_plantas):
    distancia = float(np.linalg.norm(fim - inicio))
    controle_inicio = inicio + tangente_inicio * distancia * fator
    controle_fim = fim + tangente_fim * distancia * fator
    quantidade = max(24, int(math.ceil(distancia / max(0.25 * espacamento_plantas, 0.05))) + 1)
    parametros = np.linspace(0.0, 1.0, quantidade)
    complemento = 1.0 - parametros
    pontos = (
        (complemento**3)[:, None] * inicio
        + (3 * complemento**2 * parametros)[:, None] * controle_inicio
        + (3 * complemento * parametros**2)[:, None] * controle_fim
        + (parametros**3)[:, None] * fim
    )
    return LineString(pontos)


def _indice_obstaculos(adjacencias, coordenadas):
    geometrias = []
    metadados = []
    for indice, coordenada in enumerate(coordenadas):
        geometrias.append(Point(coordenada))
        metadados.append(("ponto", indice))
    for primeiro, vizinhos in enumerate(adjacencias):
        for segundo in vizinhos:
            if primeiro < segundo:
                geometrias.append(LineString([coordenadas[primeiro], coordenadas[segundo]]))
                metadados.append(("aresta", primeiro, segundo))
    return STRtree(geometrias), geometrias, metadados


def _avaliar_seguranca_ponte(
    ponte,
    indice_obstaculos,
    geometrias_obstaculos,
    metadados_obstaculos,
    ignorados,
    corredor,
    espacamento_fileiras,
):
    if not ponte.is_simple:
        return False, 0.0, "auto_intersecao"
    alcance = max(corredor, 2.0 * espacamento_fileiras)
    indices = indice_obstaculos.query(ponte, predicate="dwithin", distance=alcance)
    folga = alcance
    for indice in indices:
        metadado = metadados_obstaculos[int(indice)]
        if metadado[0] == "ponto":
            if metadado[1] in ignorados:
                continue
        elif metadado[1] in ignorados or metadado[2] in ignorados:
            continue
        obstaculo = geometrias_obstaculos[int(indice)]
        if metadado[0] == "aresta" and ponte.crosses(obstaculo):
            return False, 0.0, "cruzamento"
        folga = min(folga, float(ponte.distance(obstaculo)))
    if folga + 1e-9 < corredor:
        return False, folga, "corredor"
    return True, folga, None


def _melhor_ponte_curva(
    primeiro,
    segundo,
    ordem_primeiro,
    ordem_segundo,
    coordenadas,
    espacamento_plantas,
    espacamento_fileiras,
    parametros,
    indice_obstaculos,
    geometrias_obstaculos,
    metadados_obstaculos,
):
    tangente_primeiro = _tangente_externa_robusta(
        primeiro, ordem_primeiro, coordenadas, parametros.pontos_tangente
    )
    tangente_segundo = _tangente_externa_robusta(
        segundo, ordem_segundo, coordenadas, parametros.pontos_tangente
    )
    ignorados = set()
    if primeiro == ordem_primeiro[0]:
        ignorados.update(ordem_primeiro[: parametros.pontos_tangente])
    else:
        ignorados.update(ordem_primeiro[-parametros.pontos_tangente :])
    if segundo == ordem_segundo[0]:
        ignorados.update(ordem_segundo[: parametros.pontos_tangente])
    else:
        ignorados.update(ordem_segundo[-parametros.pontos_tangente :])

    corredor = parametros.corredor_seguranca_fileiras * espacamento_fileiras
    melhor = None
    melhor_rejeitada = None
    for fator in np.arange(0.20, 0.7001, 0.05):
        ponte = _amostrar_ponte_curva(
            coordenadas[primeiro],
            coordenadas[segundo],
            tangente_primeiro,
            tangente_segundo,
            float(fator),
            espacamento_plantas,
        )
        segura, folga, motivo = _avaliar_seguranca_ponte(
            ponte,
            indice_obstaculos,
            geometrias_obstaculos,
            metadados_obstaculos,
            ignorados,
            corredor,
            espacamento_fileiras,
        )
        registro = PonteLacuna(
            int(primeiro), int(segundo), ponte, float(folga), round(float(fator), 2)
        )
        if segura and (melhor is None or (registro.folga_minima, -ponte.length) > (melhor.folga_minima, -melhor.geometria.length)):
            melhor = registro
        if not segura and (melhor_rejeitada is None or folga > melhor_rejeitada[0].folga_minima):
            melhor_rejeitada = (registro, motivo)
    return melhor, melhor_rejeitada


def _conectar_lacunas_legado(
    adjacencias,
    coordenadas,
    direcoes,
    espacamento_plantas,
    espacamento_fileiras,
    parametros,
):
    lacuna_maxima = max(
        min(parametros.lacuna_curva_plantas, 15.0) * espacamento_plantas,
        min(parametros.lacuna_fileiras, 3.0) * espacamento_fileiras,
    )
    lacuna_normal = max(
        min(parametros.lacuna_normal_plantas, 10.0) * espacamento_plantas,
        min(parametros.lacuna_fileiras, 3.0) * espacamento_fileiras,
    )
    lateral_normal = max(
        min(parametros.lateral_lacuna_normal_fileiras, 0.8) * espacamento_fileiras,
        min(parametros.lateral_lacuna_normal_plantas, 0.4) * espacamento_plantas,
    )
    limite_angulo = math.radians(min(parametros.angulo_lacuna_normal_graus, 40.0))
    conexoes = []
    for _ in range(parametros.iteracoes_lacunas):
        componentes = componentes_conexos(adjacencias)
        componente_de = {ponto: numero for numero, grupo in enumerate(componentes) for ponto in grupo}
        extremidades = [ponto for ponto in componente_de if len(adjacencias[ponto]) <= 1]
        candidatos = []
        for posicao, primeiro in enumerate(extremidades):
            externo_primeiro = vetor_externo_extremidade(
                primeiro, adjacencias, coordenadas, direcoes[primeiro]
            )
            for segundo in extremidades[posicao + 1 :]:
                if componente_de[primeiro] == componente_de[segundo]:
                    continue
                vetor = coordenadas[segundo] - coordenadas[primeiro]
                distancia = np.linalg.norm(vetor)
                if distancia <= 0 or distancia > lacuna_maxima:
                    continue
                unitario = vetor / distancia
                externo_segundo = vetor_externo_extremidade(
                    segundo, adjacencias, coordenadas, direcoes[segundo]
                )
                angulo_primeiro = math.acos(np.clip(np.dot(externo_primeiro, unitario), -1, 1))
                angulo_segundo = math.acos(np.clip(np.dot(externo_segundo, -unitario), -1, 1))
                if max(angulo_primeiro, angulo_segundo) > limite_angulo:
                    continue
                tangente = externo_primeiro
                lateral = abs(vetor[0] * tangente[1] - vetor[1] * tangente[0])
                erro_direcao = float(diferenca_angular(direcoes[primeiro], direcoes[segundo]))
                if erro_direcao > limite_angulo:
                    continue
                lacuna_curva = (
                    erro_direcao >= math.radians(parametros.limiar_lacuna_curva_graus)
                    and max(angulo_primeiro, angulo_segundo)
                    <= math.radians(min(parametros.angulo_extremidade_curva_graus, 30.0))
                )
                lacuna_permitida = lacuna_maxima if lacuna_curva else lacuna_normal
                lateral_permitida = (
                    min(parametros.lateral_lacuna_curva_fileiras, 3.0) * espacamento_fileiras
                    if lacuna_curva
                    else lateral_normal
                )
                if distancia > lacuna_permitida or lateral > lateral_permitida:
                    continue
                pontuacao = (
                    distancia / espacamento_plantas
                    + 2 * (angulo_primeiro + angulo_segundo) / limite_angulo
                    + 2 * lateral / lateral_permitida
                    + erro_direcao / limite_angulo
                )
                candidatos.append((pontuacao, int(primeiro), int(segundo)))
        if not candidatos:
            break
        melhor_por_extremidade = {}
        for candidato in sorted(candidatos):
            _, primeiro, segundo = candidato
            melhor_por_extremidade.setdefault(primeiro, candidato)
            melhor_por_extremidade.setdefault(segundo, candidato)
        adicoes = []
        usados = set()
        for candidato in sorted(candidatos):
            _, primeiro, segundo = candidato
            if melhor_por_extremidade.get(primeiro) != candidato or melhor_por_extremidade.get(segundo) != candidato:
                continue
            if primeiro in usados or segundo in usados:
                continue
            adicoes.append((primeiro, segundo))
            usados.update((primeiro, segundo))
        adicionadas = 0
        for primeiro, segundo in adicoes:
            if cria_ciclo(adjacencias, primeiro, segundo):
                continue
            adjacencias[primeiro].add(segundo)
            adjacencias[segundo].add(primeiro)
            conexoes.append(tuple(sorted((primeiro, segundo))))
            adicionadas += 1
        if adicionadas == 0:
            break
    return conexoes


# Conecta fragmentos compatíveis separados por lacunas no plantio.
def conectar_lacunas(
    adjacencias,
    coordenadas,
    direcoes,
    espacamento_plantas,
    espacamento_fileiras,
    diagnostico=None,
    parametros=None,
):
    parametros = parametros or ParametrosReconstrucao()
    conexoes = _conectar_lacunas_legado(
        adjacencias,
        coordenadas,
        direcoes,
        espacamento_plantas,
        espacamento_fileiras,
        parametros,
    )
    lacuna_maxima = max(
        parametros.lacuna_curva_plantas * espacamento_plantas,
        parametros.lacuna_fileiras * espacamento_fileiras,
    )
    lacuna_legada = max(15.0 * espacamento_plantas, 3.0 * espacamento_fileiras)
    pontes_aceitas = []
    pontes_candidatas = []
    pontes_rejeitadas = []
    for _ in range(parametros.iteracoes_lacunas):
        componentes = componentes_conexos(adjacencias)
        componente_de = {ponto: numero for numero, grupo in enumerate(componentes) for ponto in grupo}
        ordens = {numero: ordenar_componente(grupo, adjacencias) for numero, grupo in enumerate(componentes)}
        extremidades = [ponto for ponto in componente_de if len(adjacencias[ponto]) <= 1]
        indice_obstaculos, geometrias_obstaculos, metadados_obstaculos = _indice_obstaculos(
            adjacencias, coordenadas
        )
        candidatos = []
        for posicao, primeiro in enumerate(extremidades):
            componente_primeiro = componente_de[primeiro]
            externo_primeiro = _tangente_externa_robusta(
                primeiro,
                ordens[componente_primeiro],
                coordenadas,
                parametros.pontos_tangente,
            )
            for segundo in extremidades[posicao + 1 :]:
                if componente_de[primeiro] == componente_de[segundo]:
                    continue
                vetor = coordenadas[segundo] - coordenadas[primeiro]
                distancia = np.linalg.norm(vetor)
                if distancia <= 0 or distancia > lacuna_maxima:
                    continue
                unitario = vetor / distancia
                componente_segundo = componente_de[segundo]
                externo_segundo = _tangente_externa_robusta(
                    segundo,
                    ordens[componente_segundo],
                    coordenadas,
                    parametros.pontos_tangente,
                )
                angulo_primeiro = math.acos(np.clip(np.dot(externo_primeiro, unitario), -1, 1))
                angulo_segundo = math.acos(np.clip(np.dot(externo_segundo, -unitario), -1, 1))
                erro_direcao = float(diferenca_angular(direcoes[primeiro], direcoes[segundo]))
                lacuna_curva = (
                    erro_direcao >= math.radians(parametros.limiar_lacuna_curva_graus)
                    and max(angulo_primeiro, angulo_segundo)
                    <= math.radians(parametros.angulo_extremidade_curva_graus)
                )
                if not lacuna_curva:
                    continue
                limite_angulo = parametros.angulo_lacuna_curva_graus
                if max(angulo_primeiro, angulo_segundo) > math.radians(limite_angulo):
                    continue
                if erro_direcao > math.radians(limite_angulo):
                    continue
                dentro_regra_legada = (
                    distancia <= lacuna_legada
                    and erro_direcao <= math.radians(40.0)
                    and max(angulo_primeiro, angulo_segundo) <= math.radians(30.0)
                )
                if dentro_regra_legada:
                    continue
                ponte, rejeitada = _melhor_ponte_curva(
                    primeiro,
                    segundo,
                    ordens[componente_primeiro],
                    ordens[componente_segundo],
                    coordenadas,
                    espacamento_plantas,
                    espacamento_fileiras,
                    parametros,
                    indice_obstaculos,
                    geometrias_obstaculos,
                    metadados_obstaculos,
                )
                if ponte is None:
                    if rejeitada is not None:
                        pontes_candidatas.append(rejeitada[0])
                        pontes_rejeitadas.append(
                            {"ponte": rejeitada[0], "motivo": rejeitada[1]}
                        )
                    continue
                pontes_candidatas.append(ponte)
                desvio_maximo = max(
                    Point(ponto).distance(LineString([coordenadas[primeiro], coordenadas[segundo]]))
                    for ponto in ponte.geometria.coords
                )
                if desvio_maximo > parametros.lateral_lacuna_curva_fileiras * espacamento_fileiras:
                    pontes_rejeitadas.append({"ponte": ponte, "motivo": "desvio_curva"})
                    continue
                pontuacao = (
                    distancia / espacamento_plantas
                    + 2 * (angulo_primeiro + angulo_segundo) / math.radians(limite_angulo)
                    + erro_direcao / math.radians(limite_angulo)
                    - min(ponte.folga_minima / espacamento_fileiras, 1.0)
                )
                candidatos.append((pontuacao, primeiro, segundo, ponte))

        if not candidatos:
            break
        melhor_por_extremidade = {}
        for candidato in sorted(candidatos):
            _, primeiro, segundo, _ = candidato
            melhor_por_extremidade.setdefault(primeiro, candidato)
            melhor_por_extremidade.setdefault(segundo, candidato)
        adicoes = []
        usados = set()
        for candidato in sorted(candidatos):
            _, primeiro, segundo, ponte = candidato
            if melhor_por_extremidade.get(primeiro) != candidato or melhor_por_extremidade.get(segundo) != candidato:
                continue
            if primeiro in usados or segundo in usados:
                continue
            adicoes.append((primeiro, segundo, ponte))
            usados.update((primeiro, segundo))
        if not adicoes:
            break
        quantidade_adicionada = 0
        for primeiro, segundo, ponte in adicoes:
            if cria_ciclo(adjacencias, primeiro, segundo):
                continue
            adjacencias[primeiro].add(segundo)
            adjacencias[segundo].add(primeiro)
            conexoes.append(tuple(sorted((primeiro, segundo))))
            if ponte is not None:
                pontes_aceitas.append(ponte)
            quantidade_adicionada += 1
        if quantidade_adicionada == 0:
            break
    if diagnostico is not None:
        if isinstance(diagnostico, dict):
            diagnostico.update(
                conexoes=conexoes,
                pontes_aceitas=pontes_aceitas,
                pontes_candidatas=pontes_candidatas,
                pontes_rejeitadas=pontes_rejeitadas,
            )
        else:
            diagnostico.extend(conexoes)
    return adjacencias


# Ordena os pontos de um componente percorrendo suas conexões.
def ordenar_componente(componente, adjacencias):
    extremidades = sorted(ponto for ponto in componente if len(adjacencias[ponto]) == 1)
    atual = extremidades[0] if extremidades else min(componente)
    ordenados = []
    anterior = None
    while atual is not None:
        ordenados.append(atual)
        proximos_pontos = sorted(vizinho for vizinho in adjacencias[atual] if vizinho != anterior)
        proximo_ponto = proximos_pontos[0] if proximos_pontos else None
        anterior, atual = atual, proximo_ponto
        if atual in ordenados:
            break
    return ordenados
