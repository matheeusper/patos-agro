import json
import math
import tempfile
import unittest
from pathlib import Path

from patos_agro.io import carregar_pontos, salvar_fileiras
from patos_agro.reconstrucao import reconstruir_fileiras


RAIZ = Path(__file__).resolve().parents[1]
AMOSTRAS = {
    "amostra1.geojson": 20,
    "amostra2.geojson": 12,
    "amostra3.geojson": 31,
    "amostra4.geojson": 21,
    "amostra5.geojson": 31,
}
TOLERANCIA_GEOMETRICA_M = 0.0005


def distancia_metros(primeiro, segundo):
    lon_a, lat_a = primeiro
    lon_b, lat_b = segundo
    radiano = math.pi / 180
    delta_latitude = (lat_b - lat_a) * radiano
    delta_longitude = (lon_b - lon_a) * radiano
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat_a * radiano)
        * math.cos(lat_b * radiano)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 6_371_008.8 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def validar_equivalencia_geometrica(caso, atual, esperado):
    caso.assertEqual(atual["type"], esperado["type"])
    caso.assertEqual(len(atual["features"]), len(esperado["features"]))
    for indice, (feature_atual, feature_esperada) in enumerate(
        zip(atual["features"], esperado["features"]),
        start=1,
    ):
        caso.assertEqual(feature_atual["properties"], feature_esperada["properties"])
        caso.assertEqual(feature_atual["geometry"]["type"], feature_esperada["geometry"]["type"])
        coordenadas_atuais = feature_atual["geometry"]["coordinates"]
        coordenadas_esperadas = feature_esperada["geometry"]["coordinates"]
        caso.assertEqual(len(coordenadas_atuais), len(coordenadas_esperadas))
        maior_diferenca = max(
            (
                distancia_metros(coordenada_atual, coordenada_esperada)
                for coordenada_atual, coordenada_esperada in zip(
                    coordenadas_atuais,
                    coordenadas_esperadas,
                )
            ),
            default=0,
        )
        caso.assertLessEqual(
            maior_diferenca,
            TOLERANCIA_GEOMETRICA_M,
            f"fileira {indice} divergiu {maior_diferenca:.9f} m",
        )


class TestRegressaoAmostras(unittest.TestCase):
    def test_saidas_permanecem_geometricamente_equivalentes_aos_snapshots(self):
        with tempfile.TemporaryDirectory() as temporario:
            for nome, quantidade_esperada in AMOSTRAS.items():
                with self.subTest(amostra=nome):
                    entrada = RAIZ / "dataset" / nome
                    snapshot = RAIZ / "tests" / "snapshots" / nome
                    saida = Path(temporario) / nome

                    coordenadas, crs_utm = carregar_pontos(entrada)
                    fileiras = reconstruir_fileiras(coordenadas)
                    salvar_fileiras(fileiras, crs_utm, saida)

                    atual = json.loads(saida.read_text(encoding="utf-8"))
                    esperado = json.loads(snapshot.read_text(encoding="utf-8"))
                    self.assertEqual(len(fileiras), quantidade_esperada)
                    validar_equivalencia_geometrica(self, atual, esperado)


if __name__ == "__main__":
    unittest.main()
