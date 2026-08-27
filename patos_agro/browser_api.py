"""Ponte JSON usada pelo worker Pyodide da versao GitHub Pages."""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass

import geopandas as gpd
from shapely import wkb

from patos_agro.erros import ErroPatosAgro, ErroEntrada, ErroProcessamento
from patos_agro.io import carregar_dados_pontos, preparar_dados_pontos
from patos_agro.parametros import esquema_parametros, parametros_de_dict
from patos_agro.reconstrucao import reconstruir_com_diagnostico
from patos_agro.visualizacao import criar_resposta_visualizacao


@dataclass
class _Sessao:
    dados: object
    nome_arquivo: str


_sessoes = {}


def _resposta_sucesso(resultado):
    return json.dumps({"ok": True, "resultado": resultado}, ensure_ascii=False)


def _resposta_erro(mensagem):
    return json.dumps({"ok": False, "erro": mensagem}, ensure_ascii=False)


def _executar(operacao):
    try:
        return _resposta_sucesso(operacao())
    except (ErroPatosAgro, ValueError, OSError) as erro:
        return _resposta_erro(str(erro))
    except Exception:
        return _resposta_erro("não foi possível concluir o processamento")


def obter_parametros():
    return _executar(esquema_parametros)


def _identificador_sql(nome):
    return '"' + str(nome).replace('"', '""') + '"'


def _camadas_geopackage(caminho):
    with sqlite3.connect(caminho) as banco:
        return banco.execute(
            "SELECT table_name, column_name, geometry_type_name, srs_id "
            "FROM gpkg_geometry_columns ORDER BY rowid"
        ).fetchall()


def _geometria_geopackage(valor):
    conteudo = bytes(valor)
    if len(conteudo) < 8 or conteudo[:2] != b"GP":
        raise ValueError("cabeçalho GeoPackage inválido")
    indicador_envelope = (conteudo[3] >> 1) & 0b111
    tamanhos_envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    if indicador_envelope not in tamanhos_envelope:
        raise ValueError("envelope GeoPackage inválido")
    inicio_wkb = 8 + tamanhos_envelope[indicador_envelope]
    return wkb.loads(conteudo[inicio_wkb:])


def _crs_geopackage(banco, srs_id):
    linha = banco.execute(
        "SELECT organization, organization_coordsys_id, definition "
        "FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
        (srs_id,),
    ).fetchone()
    if linha is None:
        return None
    organizacao, codigo, definicao = linha
    if str(organizacao).upper() == "EPSG" and int(codigo) > 0:
        return f"EPSG:{codigo}"
    if definicao and str(definicao).lower() != "undefined":
        return definicao
    return None


def _ler_geopackage(caminho, camada):
    camadas = _camadas_geopackage(caminho)
    selecionada = next((dados for dados in camadas if dados[0] == camada), None)
    if selecionada is None:
        raise ErroEntrada("a camada selecionada não existe no GeoPackage")
    tabela, coluna_geometria, _tipo, srs_id = selecionada
    consulta = f"SELECT {_identificador_sql(coluna_geometria)} FROM {_identificador_sql(tabela)}"
    with sqlite3.connect(caminho) as banco:
        geometrias = [
            None if linha[0] is None else _geometria_geopackage(linha[0])
            for linha in banco.execute(consulta)
        ]
        crs = _crs_geopackage(banco, srs_id)
    return gpd.GeoDataFrame(geometry=geometrias, crs=crs)


def listar_camadas(caminho):
    def operacao():
        try:
            camadas = []
            for nome, _coluna, tipo, _srs_id in _camadas_geopackage(caminho):
                tipo = str(tipo or "Unknown")
                tipo_normalizado = tipo.lower().replace("3d ", "")
                if tipo_normalizado.startswith("point"):
                    camadas.append({"nome": str(nome), "tipo": tipo})
            if not camadas:
                raise ErroEntrada("o GeoPackage não contém nenhuma camada de pontos")
            return {"camadas": camadas}
        except ErroEntrada:
            raise
        except Exception as erro:
            raise ErroEntrada("não foi possível inspecionar as camadas do GeoPackage") from erro

    return _executar(operacao)


def _processar_dados(dados, nome, parametros, sessao_id=None):
    inicio = time.perf_counter()
    diagnostico = reconstruir_com_diagnostico(dados.coordenadas, parametros)
    duracao_ms = (time.perf_counter() - inicio) * 1000
    resposta = criar_resposta_visualizacao(dados, diagnostico, nome, duracao_ms=duracao_ms)
    if sessao_id is not None:
        resposta["sessao_id"] = sessao_id
    return resposta


def processar(caminho, nome, camada, parametros_json):
    def operacao():
        parametros = parametros_de_dict(json.loads(parametros_json) if parametros_json else None)
        if str(nome).lower().endswith(".gpkg"):
            pontos = _ler_geopackage(caminho, camada)
            dados = preparar_dados_pontos(pontos, camada=camada)
        else:
            dados = carregar_dados_pontos(caminho, camada=camada or None, engine="fiona")
        sessao_id = uuid.uuid4().hex
        _sessoes.clear()
        _sessoes[sessao_id] = _Sessao(dados, nome)
        resposta = _processar_dados(dados, nome, parametros, sessao_id=sessao_id)
        return resposta

    return _executar(operacao)


def reprocessar(sessao_id, parametros_json):
    def operacao():
        sessao = _sessoes.get(sessao_id)
        if sessao is None:
            raise ErroEntrada("a sessão expirou; envie o arquivo novamente")
        parametros = parametros_de_dict(json.loads(parametros_json) if parametros_json else None)
        return _processar_dados(
            sessao.dados,
            sessao.nome_arquivo,
            parametros,
            sessao_id=sessao_id,
        )

    return _executar(operacao)


def descartar(sessao_id):
    _sessoes.pop(sessao_id, None)
    return _resposta_sucesso(None)
