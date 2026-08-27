import json
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


class TestRegressaoAmostras(unittest.TestCase):
    def test_saidas_permanecem_identicas_aos_snapshots(self):
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
                    self.assertEqual(atual, esperado)


if __name__ == "__main__":
    unittest.main()
