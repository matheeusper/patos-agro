import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point

from patos_agro.erros import ErroEntrada
from patos_agro.io import carregar_pontos, salvar_fileiras


class TestCarregarPontos(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.entrada = Path(self.temporario.name) / "entrada.geojson"
        self.entrada.touch()

    def tearDown(self):
        self.temporario.cleanup()

    @staticmethod
    def pontos_validos(crs="EPSG:4326"):
        return gpd.GeoDataFrame(
            geometry=[Point(-47, -15), Point(-47.001, -15), Point(-47, -15.001), Point(-47.001, -15.001)],
            crs=crs,
        )

    def test_rejeita_arquivo_inexistente(self):
        with self.assertRaisesRegex(ErroEntrada, "não encontrado"):
            carregar_pontos(Path(self.temporario.name) / "ausente.geojson")

    def test_rejeita_arquivo_vazio(self):
        vazio = gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs="EPSG:4326"))
        with patch("patos_agro.io.gpd.read_file", return_value=vazio):
            with self.assertRaisesRegex(ErroEntrada, "não contém pontos"):
                carregar_pontos(self.entrada)

    def test_converte_falha_de_leitura_em_erro_claro(self):
        with patch("patos_agro.io.gpd.read_file", side_effect=RuntimeError("falha interna")):
            with self.assertRaisesRegex(ErroEntrada, "não foi possível ler"):
                carregar_pontos(self.entrada)

    def test_rejeita_entrada_sem_crs(self):
        sem_crs = self.pontos_validos(crs=None)
        with patch("patos_agro.io.gpd.read_file", return_value=sem_crs):
            with self.assertRaisesRegex(ErroEntrada, "não possui um CRS"):
                carregar_pontos(self.entrada)

    def test_rejeita_geometria_nula(self):
        geometrias = [Point(-47, -15), Point(-47.001, -15), Point(-47, -15.001), None]
        pontos = gpd.GeoDataFrame(geometry=geometrias, crs="EPSG:4326")
        with patch("patos_agro.io.gpd.read_file", return_value=pontos):
            with self.assertRaisesRegex(ErroEntrada, "geometrias nulas"):
                carregar_pontos(self.entrada)

    def test_rejeita_geometria_vazia(self):
        geometrias = [Point(-47, -15), Point(-47.001, -15), Point(-47, -15.001), Point()]
        pontos = gpd.GeoDataFrame(geometry=geometrias, crs="EPSG:4326")
        with patch("patos_agro.io.gpd.read_file", return_value=pontos):
            with self.assertRaisesRegex(ErroEntrada, "geometrias vazias"):
                carregar_pontos(self.entrada)

    def test_rejeita_geometria_que_nao_seja_ponto(self):
        linhas = gpd.GeoDataFrame(
            geometry=[LineString([(0, 0), (1, 1)])],
            crs="EPSG:4326",
        )
        with patch("patos_agro.io.gpd.read_file", return_value=linhas):
            with self.assertRaisesRegex(ErroEntrada, "somente geometrias Point"):
                carregar_pontos(self.entrada)

    def test_rejeita_coordenada_nao_finita(self):
        geometrias = [Point(-47, -15), Point(-47.001, -15), Point(-47, -15.001), Point(np.nan, -15)]
        pontos = gpd.GeoDataFrame(geometry=geometrias, crs="EPSG:4326")
        with patch("patos_agro.io.gpd.read_file", return_value=pontos):
            with self.assertRaisesRegex(ErroEntrada, "não finitas"):
                carregar_pontos(self.entrada)

    def test_rejeita_menos_de_quatro_coordenadas_unicas(self):
        repetidos = gpd.GeoDataFrame(
            geometry=[Point(-47, -15), Point(-47, -15), Point(-47.001, -15), Point(-47.001, -15)],
            crs="EPSG:4326",
        )
        with patch("patos_agro.io.gpd.read_file", return_value=repetidos):
            with self.assertRaisesRegex(ErroEntrada, "quatro pontos"):
                carregar_pontos(self.entrada)

    def test_rejeita_quando_utm_nao_pode_ser_determinado(self):
        pontos = self.pontos_validos()
        with (
            patch("patos_agro.io.gpd.read_file", return_value=pontos),
            patch.object(gpd.GeoDataFrame, "estimate_utm_crs", return_value=None),
        ):
            with self.assertRaisesRegex(ErroEntrada, "determinar o CRS UTM"):
                carregar_pontos(self.entrada)

    def test_carrega_quatro_pontos_validos(self):
        pontos = self.pontos_validos()
        with patch("patos_agro.io.gpd.read_file", return_value=pontos):
            coordenadas, crs_utm = carregar_pontos(self.entrada)

        self.assertEqual(coordenadas.shape, (4, 2))
        self.assertTrue(np.isfinite(coordenadas).all())
        self.assertIsNotNone(crs_utm)


class TestSalvarFileiras(unittest.TestCase):
    def test_salva_geojson_vazio_e_permite_sobrescrita(self):
        with tempfile.TemporaryDirectory() as temporario:
            saida = Path(temporario) / "subdiretorio" / "saida.geojson"
            salvar_fileiras([], "EPSG:31983", saida)
            primeiro = saida.read_text(encoding="utf-8")
            salvar_fileiras([], "EPSG:31983", saida)

            self.assertEqual(saida.read_text(encoding="utf-8"), primeiro)
            self.assertIn('"FeatureCollection"', primeiro)


if __name__ == "__main__":
    unittest.main()
