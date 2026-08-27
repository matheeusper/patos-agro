import unittest
from pathlib import Path

from patos_agro.io import carregar_dados_pontos
from patos_agro.reconstrucao import reconstruir_com_diagnostico, reconstruir_fileiras
from patos_agro.visualizacao import criar_resposta_visualizacao


RAIZ = Path(__file__).resolve().parents[1]


class TestPipelineVisualizacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entrada = RAIZ / "dataset" / "amostra2.geojson"
        cls.dados = carregar_dados_pontos(cls.entrada)
        cls.diagnostico = reconstruir_com_diagnostico(cls.dados.coordenadas)
        cls.resposta = criar_resposta_visualizacao(cls.dados, cls.diagnostico, cls.entrada.name)

    def test_pipeline_diagnosticado_preserva_resultado(self):
        esperado = reconstruir_fileiras(self.dados.coordenadas)
        atual = self.diagnostico.fileiras

        self.assertEqual([(tipo, indice) for _, tipo, indice in atual], [(tipo, indice) for _, tipo, indice in esperado])
        self.assertEqual([geometria.wkb for geometria, _, _ in atual], [geometria.wkb for geometria, _, _ in esperado])

    def test_expoe_nove_etapas_na_ordem_esperada(self):
        self.assertEqual(
            [etapa["id"] for etapa in self.resposta["etapas"]],
            ["pontos", "delaunay", "direcoes", "escalas", "classificacao", "grafo", "lacunas", "componentes", "resultado"],
        )

    def test_todas_as_camadas_sao_geojson(self):
        for identificador, camada in self.resposta["camadas"].items():
            with self.subTest(camada=identificador):
                self.assertEqual(camada["dados"]["type"], "FeatureCollection")
                self.assertIn("features", camada["dados"])

    def test_classificacao_cobre_todas_as_arestas(self):
        self.assertEqual(len(self.diagnostico.estados_arestas), len(self.diagnostico.arestas))
        self.assertNotIn(None, self.diagnostico.estados_arestas)

    def test_resultado_final_mantem_doze_fileiras(self):
        self.assertEqual(len(self.resposta["resultado"]["geojson"]["features"]), 12)
        self.assertEqual(self.resposta["resultado"]["nome"], "amostra2.geojson")

    def test_expoe_parametros_resumo_e_camadas_de_pontes(self):
        self.assertEqual(self.resposta["parametros"]["lacuna_curva_plantas"], 18.0)
        self.assertEqual(self.resposta["resumo"]["fileiras"], 12)
        self.assertIn("pontes_curvas", self.resposta["camadas"])
        self.assertIn("pontes_curvas_rejeitadas", self.resposta["camadas"])


if __name__ == "__main__":
    unittest.main()
