from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np

from patos_agro.erros import ErroEntrada, ErroSaida


@dataclass(frozen=True)
class DadosPontos:
    coordenadas: np.ndarray
    crs_utm: object
    crs_original: object
    quantidade_original: int
    quantidade_unica: int
    duplicatas_removidas: int
    coordenadas_duplicadas: np.ndarray
    camada: str | None = None


# Lê os pontos, remove duplicados e converte as coordenadas para UTM.
def carregar_dados_pontos(caminho_entrada, camada=None, engine=None):
    entrada = Path(caminho_entrada)
    if not entrada.is_file():
        raise ErroEntrada(f"arquivo de entrada não encontrado: {entrada}")

    try:
        argumentos = {"layer": camada} if camada else {}
        if engine:
            argumentos["engine"] = engine
        pontos = gpd.read_file(entrada, **argumentos)
    except Exception as erro:
        raise ErroEntrada(f"não foi possível ler o arquivo de entrada: {entrada}") from erro

    if pontos.empty:
        raise ErroEntrada("o arquivo de entrada não contém pontos")
    if pontos.crs is None:
        raise ErroEntrada("o arquivo de entrada não possui um CRS definido")
    crs_original = pontos.crs
    quantidade_original = len(pontos)
    if pontos.geometry.isna().any():
        raise ErroEntrada("o arquivo de entrada contém geometrias nulas")
    if pontos.geometry.is_empty.any():
        raise ErroEntrada("o arquivo de entrada contém geometrias vazias")

    tipos_invalidos = sorted(set(pontos.geom_type) - {"Point"})
    if tipos_invalidos:
        tipos = ", ".join(tipos_invalidos)
        raise ErroEntrada(f"a entrada deve conter somente geometrias Point; encontrados: {tipos}")

    coordenadas_origem = np.column_stack((pontos.geometry.x, pontos.geometry.y))
    if not np.isfinite(coordenadas_origem).all():
        raise ErroEntrada("a entrada contém coordenadas inválidas ou não finitas")

    pontos["_coordenada"] = pontos.geometry.apply(lambda ponto: (ponto.x, ponto.y))
    pontos_duplicados = pontos[pontos.duplicated("_coordenada", keep="first")]
    pontos = pontos.drop_duplicates("_coordenada").drop(columns="_coordenada")
    quantidade_unica = len(pontos)

    if len(pontos) < 4:
        raise ErroEntrada("a entrada deve conter pelo menos quatro pontos com coordenadas únicas")

    try:
        crs_utm = pontos.estimate_utm_crs()
    except Exception as erro:
        raise ErroEntrada("não foi possível determinar o CRS UTM da entrada") from erro
    if crs_utm is None:
        raise ErroEntrada("não foi possível determinar o CRS UTM da entrada")

    try:
        projetado = pontos.to_crs(crs_utm)
    except Exception as erro:
        raise ErroEntrada("não foi possível reprojetar os pontos para o CRS UTM") from erro

    coordenadas = np.column_stack((projetado.geometry.x, projetado.geometry.y))
    if not np.isfinite(coordenadas).all():
        raise ErroEntrada("a entrada contém coordenadas inválidas ou não finitas")
    if pontos_duplicados.empty:
        coordenadas_duplicadas = np.empty((0, 2), dtype=float)
    else:
        duplicados_projetados = pontos_duplicados.to_crs(crs_utm)
        coordenadas_duplicadas = np.column_stack(
            (duplicados_projetados.geometry.x, duplicados_projetados.geometry.y)
        )

    return DadosPontos(
        coordenadas=coordenadas,
        crs_utm=crs_utm,
        crs_original=crs_original,
        quantidade_original=quantidade_original,
        quantidade_unica=quantidade_unica,
        duplicatas_removidas=quantidade_original - quantidade_unica,
        coordenadas_duplicadas=coordenadas_duplicadas,
        camada=camada,
    )


def carregar_pontos(caminho_entrada):
    dados = carregar_dados_pontos(caminho_entrada)
    return dados.coordenadas, dados.crs_utm


def criar_resultado_fileiras(fileiras, crs_utm):
    return gpd.GeoDataFrame(
        {
            "fileira_id": np.arange(1, len(fileiras) + 1, dtype=int),
            "comprimento_m": [round(fileira[0].length, 2) for fileira in fileiras],
            "tipo": [fileira[1] for fileira in fileiras],
            "geometry": [fileira[0] for fileira in fileiras],
        },
        crs=crs_utm,
    ).to_crs("EPSG:4326")


# Calcula os atributos, reprojeta as linhas e salva o GeoJSON.
def salvar_fileiras(fileiras, crs_utm, caminho_saida):
    saida = Path(caminho_saida)
    try:
        resultado = criar_resultado_fileiras(fileiras, crs_utm)
        conteudo = resultado.to_json(drop_id=True)
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(conteudo, encoding="utf-8")
    except (OSError, ValueError) as erro:
        raise ErroSaida(f"não foi possível salvar o arquivo de saída: {saida}") from erro
