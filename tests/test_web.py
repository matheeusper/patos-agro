import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Point

from patos_agro.web import criar_app


RAIZ = Path(__file__).resolve().parents[1]


class TestAplicacaoWeb(unittest.TestCase):
    def setUp(self):
        self.app = criar_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_pagina_inicial_e_recursos_locais(self):
        pagina = self.client.get("/")
        javascript = self.client.get("/static/visualizador.js")
        estilos = self.client.get("/static/visualizador.css")
        leaflet = self.client.get("/static/vendor/leaflet/leaflet.js")
        fonte = self.client.get("/static/fonts/BarlowCondensed-SemiBold.ttf")
        licenca_fonte = self.client.get("/static/fonts/OFL-BarlowCondensed.txt")
        logo = self.client.get("/static/brand/patosagro-logo.svg")
        marca = self.client.get("/static/brand/patosagro-mark.svg")
        favicon = self.client.get("/static/brand/favicon.svg")

        self.assertEqual(pagina.status_code, 200)
        self.assertIn("Do ponto bruto", pagina.get_data(as_text=True))
        self.assertIn("PatosAgro", pagina.get_data(as_text=True))
        self.assertIn("patosagro-logo.svg", pagina.get_data(as_text=True))
        self.assertIn("patosagro-mark.svg", pagina.get_data(as_text=True))
        self.assertIn("favicon.svg", pagina.get_data(as_text=True))
        self.assertIn("Estação de reconstrução", pagina.get_data(as_text=True))
        self.assertIn('id="inspector"', pagina.get_data(as_text=True))
        self.assertIn('data-inspector-tab="stage"', pagina.get_data(as_text=True))
        self.assertIn('data-inspector-tab="layers"', pagina.get_data(as_text=True))
        self.assertIn('data-inspector-tab="settings"', pagina.get_data(as_text=True))
        self.assertIn('role="tabpanel"', pagina.get_data(as_text=True))
        self.assertIn('aria-controls="inspector-panel-stage"', pagina.get_data(as_text=True))
        self.assertIn('role="button" tabindex="0">Abrir dados', pagina.get_data(as_text=True))
        self.assertIn('id="basemap-toggle"', pagina.get_data(as_text=True))
        self.assertIn('id="basemap-select"', pagina.get_data(as_text=True))
        self.assertIn('value="satellite"', pagina.get_data(as_text=True))
        self.assertIn('value="hybrid"', pagina.get_data(as_text=True))
        self.assertIn('value="aerial"', pagina.get_data(as_text=True))
        self.assertIn('value="topographic"', pagina.get_data(as_text=True))
        self.assertIn('value="dark"', pagina.get_data(as_text=True))
        self.assertIn('value="neutral"', pagina.get_data(as_text=True))
        self.assertIn('id="basemap-note"', pagina.get_data(as_text=True))
        self.assertIn('id="theme-toggle"', pagina.get_data(as_text=True))
        self.assertIn('id="parameters-button"', pagina.get_data(as_text=True))
        self.assertIn('id="pin-reference-button"', pagina.get_data(as_text=True))
        self.assertIn('aria-pressed="true"', pagina.get_data(as_text=True))
        self.assertEqual(javascript.status_code, 200)
        self.assertIn("patos-agro-tema", javascript.get_data(as_text=True))
        self.assertIn("patos-agro-mapa-base", javascript.get_data(as_text=True))
        self.assertIn("patos-agro-estilo-mapa-base", javascript.get_data(as_text=True))
        self.assertIn("setBaseMapEnabled", javascript.get_data(as_text=True))
        self.assertIn("setBaseMapStyle", javascript.get_data(as_text=True))
        self.assertIn("s2cloudless-2025_3857", javascript.get_data(as_text=True))
        self.assertIn("overlay_bright_3857", javascript.get_data(as_text=True))
        self.assertIn("terrain_3857", javascript.get_data(as_text=True))
        self.assertIn("global.imagery.hotosm.org", javascript.get_data(as_text=True))
        self.assertNotIn("arcgis", javascript.get_data(as_text=True).lower())
        self.assertIn("scheduleReprocess", javascript.get_data(as_text=True))
        self.assertIn('event.key === "ArrowRight"', javascript.get_data(as_text=True))
        self.assertIn('event.key !== "Escape"', javascript.get_data(as_text=True))
        self.assertEqual(estilos.status_code, 200)
        self.assertIn('font-family: "Barlow Condensed"', estilos.get_data(as_text=True))
        self.assertIn("survey-window", estilos.get_data(as_text=True))
        self.assertIn("command-bar", estilos.get_data(as_text=True))
        self.assertIn("inspector-panel", estilos.get_data(as_text=True))
        self.assertIn('html[data-theme="dark"]', estilos.get_data(as_text=True))
        self.assertIn(".leaflet-tile-pane", estilos.get_data(as_text=True))
        self.assertIn(".basemap-imagery", estilos.get_data(as_text=True))
        self.assertIn(".basemap-dark", estilos.get_data(as_text=True))
        self.assertNotIn('html[data-theme="dark"] .leaflet-tile-pane', estilos.get_data(as_text=True))
        self.assertEqual(leaflet.status_code, 200)
        self.assertEqual(fonte.status_code, 200)
        self.assertGreater(len(fonte.data), 1000)
        self.assertEqual(licenca_fonte.status_code, 200)
        self.assertIn("SIL OPEN FONT LICENSE", licenca_fonte.get_data(as_text=True))
        for recurso in (logo, marca, favicon):
            self.assertEqual(recurso.status_code, 200)
            self.assertIn("<svg", recurso.get_data(as_text=True))
        pagina.close()
        javascript.close()
        estilos.close()
        leaflet.close()
        fonte.close()
        licenca_fonte.close()
        logo.close()
        marca.close()
        favicon.close()

    def test_rejeita_upload_ausente(self):
        resposta = self.client.post("/api/processar", data={}, content_type="multipart/form-data")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("selecione", resposta.get_json()["erro"])

    def test_rejeita_extensao_nao_suportada(self):
        resposta = self.client.post(
            "/api/processar",
            data={"arquivo": (io.BytesIO(b"texto"), "pontos.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("formato", resposta.get_json()["erro"])

    def test_rejeita_upload_acima_do_limite(self):
        app = criar_app({"TESTING": True, "MAX_CONTENT_LENGTH": 32})
        cliente = app.test_client()
        resposta = cliente.post(
            "/api/processar",
            data={"arquivo": (io.BytesIO(b"x" * 128), "pontos.geojson")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 413)
        self.assertIn("25 MB", resposta.get_json()["erro"])

    def test_processa_geojson_e_limpa_upload_temporario(self):
        conteudo = (RAIZ / "dataset" / "amostra2.geojson").read_bytes()
        caminho_temporario = None

        from patos_agro import web

        salvar_original = web._salvar_upload

        def registrar_caminho(arquivo, diretorio):
            nonlocal caminho_temporario
            resultado = salvar_original(arquivo, diretorio)
            caminho_temporario = resultado[0]
            return resultado

        with patch("patos_agro.web._salvar_upload", side_effect=registrar_caminho):
            resposta = self.client.post(
                "/api/processar",
                data={"arquivo": (io.BytesIO(conteudo), "amostra2.geojson")},
                content_type="multipart/form-data",
            )

        payload = resposta.get_json()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(payload["etapas"]), 9)
        self.assertEqual(len(payload["resultado"]["geojson"]["features"]), 12)
        self.assertIsNotNone(caminho_temporario)
        self.assertFalse(caminho_temporario.exists())
        self.assertIn("sessao_id", payload)

    def test_esquema_reprocessamento_e_remocao_da_sessao(self):
        esquema = self.client.get("/api/parametros")
        self.assertEqual(esquema.status_code, 200)
        self.assertEqual(esquema.get_json()["versao"], 1)

        conteudo = (RAIZ / "dataset" / "amostra2.geojson").read_bytes()
        inicial = self.client.post(
            "/api/processar",
            data={"arquivo": (io.BytesIO(conteudo), "amostra2.geojson")},
            content_type="multipart/form-data",
        ).get_json()
        sessao_id = inicial["sessao_id"]
        parametros = inicial["parametros"]
        parametros["min_pontos_fileira"] = 5
        resposta = self.client.post(
            "/api/reprocessar",
            json={"sessao_id": sessao_id, "parametros": parametros},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["parametros"]["min_pontos_fileira"], 5)

        removida = self.client.delete(f"/api/sessoes/{sessao_id}")
        self.assertEqual(removida.status_code, 204)
        expirada = self.client.post(
            "/api/reprocessar",
            json={"sessao_id": sessao_id, "parametros": parametros},
        )
        self.assertEqual(expirada.status_code, 404)

    def test_rejeita_configuracao_de_parametros_invalida(self):
        conteudo = (RAIZ / "dataset" / "amostra2.geojson").read_bytes()
        resposta = self.client.post(
            "/api/processar",
            data={
                "arquivo": (io.BytesIO(conteudo), "amostra2.geojson"),
                "parametros": '{"campo_desconhecido": 1}',
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("desconhecidos", resposta.get_json()["erro"])

    def test_geojson_nao_exige_selecao_de_camada(self):
        conteudo = (RAIZ / "dataset" / "amostra2.geojson").read_bytes()
        resposta = self.client.post(
            "/api/camadas",
            data={"arquivo": (io.BytesIO(conteudo), "amostra2.geojson")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["camadas"], [])

    def test_lista_multiplas_camadas_de_pontos(self):
        camadas = [["talhao_a", "Point"], ["talhao_b", "Point"], ["limite", "Polygon"]]
        with patch("patos_agro.web.pyogrio.list_layers", return_value=camadas):
            resposta = self.client.post(
                "/api/camadas",
                data={"arquivo": (io.BytesIO(b"gpkg"), "camadas.gpkg")},
                content_type="multipart/form-data",
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([item["nome"] for item in resposta.get_json()["camadas"]], ["talhao_a", "talhao_b"])

    def test_processa_geopackage_com_uma_camada(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "pontos.gpkg"
            pontos = gpd.GeoDataFrame(
                geometry=[Point(-47, -15), Point(-47.001, -15), Point(-47, -15.001), Point(-47.001, -15.001)],
                crs="EPSG:4326",
            )
            pontos.to_file(caminho, layer="plantas", driver="GPKG")
            conteudo = caminho.read_bytes()

        resposta = self.client.post(
            "/api/processar",
            data={"arquivo": (io.BytesIO(conteudo), "pontos.gpkg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["arquivo"]["camada"], "plantas")


if __name__ == "__main__":
    unittest.main()
