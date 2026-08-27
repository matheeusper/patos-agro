import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.spatial import QhullError

from patos_agro.erros import ErroProcessamento
from patos_agro.io import carregar_dados_pontos
from patos_agro.reconstrucao import reconstruir_com_diagnostico, reconstruir_fileiras


RAIZ = Path(__file__).resolve().parents[1]


class TestReconstrucao(unittest.TestCase):
    def test_converte_falha_da_triangulacao_em_erro_claro(self):
        coordenadas = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], dtype=float)
        with patch(
            "patos_agro.reconstrucao.arestas_delaunay",
            side_effect=QhullError("falha interna"),
        ):
            with self.assertRaisesRegex(ErroProcessamento, "triangular os pontos"):
                reconstruir_fileiras(coordenadas)

    def test_amostra4_usa_ponte_curva_segura_entre_41_e_299(self):
        dados = carregar_dados_pontos(RAIZ / "dataset" / "amostra4.geojson")
        diagnostico = reconstruir_com_diagnostico(dados.coordenadas)

        pontes = {
            tuple(sorted((ponte.primeiro, ponte.segundo))): ponte
            for ponte in diagnostico.pontes_lacunas
        }
        self.assertIn((41, 299), pontes)
        self.assertEqual(len(diagnostico.fileiras), 21)
        self.assertGreaterEqual(
            pontes[(41, 299)].folga_minima,
            0.35 * diagnostico.espacamento_fileiras,
        )
        self.assertTrue(pontes[(41, 299)].geometria.is_simple)
        self.assertTrue(
            np.allclose(pontes[(41, 299)].geometria.coords[0], dados.coordenadas[41])
        )
        self.assertTrue(
            np.allclose(pontes[(41, 299)].geometria.coords[-1], dados.coordenadas[299])
        )


if __name__ == "__main__":
    unittest.main()
