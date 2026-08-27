import unittest

from patos_agro.sessoes import ArmazenamentoSessoes


class TestArmazenamentoSessoes(unittest.TestCase):
    def setUp(self):
        self.agora = 100.0
        self.sessoes = ArmazenamentoSessoes(
            limite=3, validade_segundos=30, relogio=lambda: self.agora
        )

    def test_cria_reutiliza_e_remove_sessao(self):
        identificador = self.sessoes.criar("dados", "campo.geojson")
        self.assertEqual(self.sessoes.obter(identificador).dados, "dados")
        self.assertTrue(self.sessoes.remover(identificador))
        self.assertIsNone(self.sessoes.obter(identificador))

    def test_expira_sessao(self):
        identificador = self.sessoes.criar("dados", "campo.geojson")
        self.agora += 31
        self.assertIsNone(self.sessoes.obter(identificador))

    def test_limita_a_tres_sessoes_e_remove_a_mais_antiga(self):
        primeira = self.sessoes.criar(1, "1.geojson")
        self.sessoes.criar(2, "2.geojson")
        self.sessoes.criar(3, "3.geojson")
        self.sessoes.criar(4, "4.geojson")
        self.assertIsNone(self.sessoes.obter(primeira))
        self.assertEqual(self.sessoes.quantidade(), 3)


if __name__ == "__main__":
    unittest.main()
