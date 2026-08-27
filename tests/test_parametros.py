import math
import unittest

from patos_agro.erros import ErroEntrada
from patos_agro.parametros import ParametrosReconstrucao, esquema_parametros, parametros_de_dict


class TestParametrosReconstrucao(unittest.TestCase):
    def test_valores_padrao_e_presets(self):
        esquema = esquema_parametros()
        self.assertEqual(esquema["versao"], 1)
        self.assertEqual(ParametrosReconstrucao().lacuna_curva_plantas, 18.0)
        self.assertEqual(ParametrosReconstrucao().angulo_lacuna_curva_graus, 55.0)
        self.assertEqual(
            set(esquema["presets"]),
            {"padrao", "conservador", "flexivel", "curvas_lacunas"},
        )

    def test_sobrescreve_espacamentos_manuais(self):
        parametros = parametros_de_dict(
            {"espacamento_plantas_manual": 0.55, "espacamento_fileiras_manual": 3.2}
        )
        self.assertEqual(parametros.espacamento_plantas_manual, 0.55)
        self.assertEqual(parametros.espacamento_fileiras_manual, 3.2)

    def test_rejeita_campos_desconhecidos_nao_finitos_e_fora_dos_limites(self):
        casos = [
            {"desconhecido": 1},
            {"lacuna_curva_plantas": math.inf},
            {"lacuna_curva_plantas": 1000},
        ]
        for valores in casos:
            with self.subTest(valores=valores), self.assertRaises(ErroEntrada):
                parametros_de_dict(valores)

    def test_round_trip_do_formato_de_configuracao(self):
        original = esquema_parametros()["presets"]["curvas_lacunas"]
        reconstruido = parametros_de_dict(original)
        self.assertEqual(reconstruido.como_dict(), original)


if __name__ == "__main__":
    unittest.main()
