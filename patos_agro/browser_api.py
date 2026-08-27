"""Ponte JSON usada pelo worker Pyodide da versao GitHub Pages."""

import json
import time
import uuid
from dataclasses import dataclass

import fiona

from patos_agro.erros import ErroPatosAgro, ErroEntrada, ErroProcessamento
from patos_agro.io import carregar_dados_pontos
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


def _tipo_geometria(caminho, camada):
    with fiona.open(caminho, layer=camada) as colecao:
        return str(colecao.schema.get("geometry") or "Unknown")


def listar_camadas(caminho):
    def operacao():
        try:
            nomes = fiona.listlayers(caminho)
            camadas = []
            for nome in nomes:
                tipo = _tipo_geometria(caminho, nome)
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
