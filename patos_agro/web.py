import json
import tempfile
import time
from pathlib import Path

import pyogrio
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from patos_agro.erros import ErroPatosAgro, ErroEntrada, ErroProcessamento
from patos_agro.io import carregar_dados_pontos
from patos_agro.parametros import esquema_parametros, parametros_de_dict
from patos_agro.reconstrucao import reconstruir_com_diagnostico
from patos_agro.sessoes import ArmazenamentoSessoes
from patos_agro.visualizacao import criar_resposta_visualizacao


EXTENSOES_ACEITAS = {".geojson", ".gpkg"}
LIMITE_UPLOAD = 25 * 1024 * 1024


def _salvar_upload(arquivo, diretorio):
    if arquivo is None or not arquivo.filename:
        raise ErroEntrada("selecione um arquivo GeoJSON ou GeoPackage")
    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_ACEITAS:
        raise ErroEntrada("formato não suportado; envie um arquivo .geojson ou .gpkg")

    nome_seguro = secure_filename(arquivo.filename) or f"entrada{extensao}"
    caminho = Path(diretorio) / f"entrada{extensao}"
    arquivo.save(caminho)
    if caminho.stat().st_size == 0:
        raise ErroEntrada("o arquivo enviado está vazio")
    return caminho, nome_seguro, extensao


def _camadas_pontos_geopackage(caminho):
    try:
        camadas = pyogrio.list_layers(caminho)
    except Exception as erro:
        raise ErroEntrada("não foi possível inspecionar as camadas do GeoPackage") from erro
    return [
        {"nome": str(nome), "tipo": str(tipo)}
        for nome, tipo in camadas
        if str(tipo).lower().startswith("point")
    ]


def _executar_com_upload(operacao):
    arquivo = request.files.get("arquivo")
    with tempfile.TemporaryDirectory(prefix="patos-agro-upload-") as temporario:
        caminho, nome, extensao = _salvar_upload(arquivo, temporario)
        return operacao(caminho, nome, extensao)


def _ler_parametros_formulario():
    texto = request.form.get("parametros")
    if not texto:
        return parametros_de_dict()
    try:
        valores = json.loads(texto)
    except (TypeError, json.JSONDecodeError) as erro:
        raise ErroEntrada("os parâmetros enviados não formam um JSON válido") from erro
    return parametros_de_dict(valores)


def _resposta_processamento(dados, nome, parametros, sessao_id=None):
    inicio = time.perf_counter()
    diagnostico = reconstruir_com_diagnostico(dados.coordenadas, parametros)
    duracao_ms = (time.perf_counter() - inicio) * 1000
    resposta = criar_resposta_visualizacao(dados, diagnostico, nome, duracao_ms=duracao_ms)
    if sessao_id is not None:
        resposta["sessao_id"] = sessao_id
    return resposta


def criar_app(configuracao=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=LIMITE_UPLOAD)
    if configuracao:
        app.config.update(configuracao)
    app.json.ensure_ascii = False
    app.extensions["patos_agro_sessoes"] = app.config.get("ARMAZENAMENTO_SESSOES") or ArmazenamentoSessoes()

    @app.get("/")
    def pagina_inicial():
        return render_template("visualizador.html")

    @app.get("/api/parametros")
    def obter_parametros():
        return jsonify(esquema_parametros())

    @app.post("/api/camadas")
    def listar_camadas():
        def operacao(caminho, nome, extensao):
            if extensao == ".geojson":
                return jsonify({"arquivo": nome, "camadas": []})
            camadas = _camadas_pontos_geopackage(caminho)
            if not camadas:
                raise ErroEntrada("o GeoPackage não contém nenhuma camada de pontos")
            return jsonify({"arquivo": nome, "camadas": camadas})

        try:
            return _executar_com_upload(operacao)
        except RequestEntityTooLarge:
            raise
        except ErroPatosAgro as erro:
            return jsonify({"erro": str(erro)}), 400
        except Exception:
            app.logger.exception("Falha inesperada ao inspecionar upload")
            return jsonify({"erro": "não foi possível inspecionar o arquivo"}), 500

    @app.post("/api/processar")
    def processar():
        def operacao(caminho, nome, extensao):
            camada = request.form.get("camada") or None
            if extensao == ".gpkg":
                camadas = _camadas_pontos_geopackage(caminho)
                nomes_camadas = {item["nome"] for item in camadas}
                if not camadas:
                    raise ErroEntrada("o GeoPackage não contém nenhuma camada de pontos")
                if camada is None and len(camadas) == 1:
                    camada = camadas[0]["nome"]
                elif camada is None:
                    raise ErroEntrada("selecione uma camada de pontos do GeoPackage")
                elif camada not in nomes_camadas:
                    raise ErroEntrada("a camada selecionada não existe ou não contém pontos")
            else:
                camada = None

            dados = carregar_dados_pontos(caminho, camada=camada)
            parametros = _ler_parametros_formulario()
            resposta = _resposta_processamento(dados, nome, parametros)
            sessao_id = app.extensions["patos_agro_sessoes"].criar(dados, nome)
            resposta["sessao_id"] = sessao_id
            return jsonify(resposta)

        try:
            return _executar_com_upload(operacao)
        except RequestEntityTooLarge:
            raise
        except ErroEntrada as erro:
            return jsonify({"erro": str(erro)}), 400
        except ErroProcessamento as erro:
            return jsonify({"erro": str(erro)}), 422
        except Exception:
            app.logger.exception("Falha inesperada durante o processamento")
            return jsonify({"erro": "não foi possível concluir o processamento"}), 500

    @app.post("/api/reprocessar")
    def reprocessar():
        try:
            corpo = request.get_json(silent=True)
            if not isinstance(corpo, dict):
                raise ErroEntrada("envie a sessão e os parâmetros em um objeto JSON")
            sessao_id = corpo.get("sessao_id")
            if not isinstance(sessao_id, str) or not sessao_id:
                raise ErroEntrada("identificador de sessão ausente")
            sessao = app.extensions["patos_agro_sessoes"].obter(sessao_id)
            if sessao is None:
                return jsonify({"erro": "a sessão expirou; envie o arquivo novamente"}), 404
            parametros = parametros_de_dict(corpo.get("parametros"))
            return jsonify(
                _resposta_processamento(
                    sessao.dados,
                    sessao.nome_arquivo,
                    parametros,
                    sessao_id=sessao_id,
                )
            )
        except ErroEntrada as erro:
            return jsonify({"erro": str(erro)}), 400
        except ErroProcessamento as erro:
            return jsonify({"erro": str(erro)}), 422
        except Exception:
            app.logger.exception("Falha inesperada durante o reprocessamento")
            return jsonify({"erro": "não foi possível concluir o reprocessamento"}), 500

    @app.delete("/api/sessoes/<sessao_id>")
    def remover_sessao(sessao_id):
        app.extensions["patos_agro_sessoes"].remover(sessao_id)
        return "", 204

    @app.errorhandler(RequestEntityTooLarge)
    def upload_muito_grande(_erro):
        return jsonify({"erro": "o arquivo excede o limite de 25 MB"}), 413

    return app
