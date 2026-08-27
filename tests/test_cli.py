import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np

from patos_agro.cli import caminhos_representam_mesmo_arquivo, main, montar_caminho_saida
from patos_agro.erros import ErroEntrada


class TestCli(unittest.TestCase):
    def test_monta_nome_geojson_a_partir_de_geopackage(self):
        caminho = montar_caminho_saida("dados/amostra1.gpkg", "resultado")
        self.assertEqual(caminho, Path("resultado/amostra1.geojson"))

    def test_detecta_caminhos_equivalentes(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "entrada.geojson"
            self.assertTrue(caminhos_representam_mesmo_arquivo(caminho, caminho.parent / "." / caminho.name))

    def test_detecta_equivalencia_resolvida_por_link(self):
        with patch("patos_agro.cli.os.path.realpath", side_effect=["/dados/original", "/dados/original"]):
            self.assertTrue(caminhos_representam_mesmo_arquivo("link", "original"))

    def test_bloqueia_sobrescrita_do_arquivo_de_entrada(self):
        with tempfile.TemporaryDirectory() as temporario:
            entrada = Path(temporario) / "amostra.geojson"
            entrada.touch()
            erros = io.StringIO()
            with (
                patch("patos_agro.cli.carregar_pontos", return_value=(np.zeros((4, 2)), "EPSG:31983")),
                patch("patos_agro.cli.reconstruir_fileiras") as reconstruir,
                redirect_stderr(erros),
                self.assertRaises(SystemExit) as encerramento,
            ):
                main(["--input", str(entrada), "--output", temporario])

            self.assertEqual(encerramento.exception.code, 1)
            self.assertIn("não pode sobrescrever", erros.getvalue())
            reconstruir.assert_not_called()

    def test_exibe_erro_esperado_sem_traceback(self):
        erros = io.StringIO()
        with (
            patch("patos_agro.cli.carregar_pontos", side_effect=ErroEntrada("entrada inválida")),
            redirect_stderr(erros),
            self.assertRaises(SystemExit) as encerramento,
        ):
            main(["--input", "entrada.geojson", "--output", "resultado"])

        self.assertEqual(encerramento.exception.code, 1)
        self.assertEqual(erros.getvalue(), "erro: entrada inválida\n")

    def test_argumentos_ausentes_retornam_codigo_dois(self):
        erros = io.StringIO()
        with redirect_stderr(erros), self.assertRaises(SystemExit) as encerramento:
            main([])

        self.assertEqual(encerramento.exception.code, 2)
        self.assertIn("--input", erros.getvalue())
        self.assertIn("--output", erros.getvalue())

    def test_exibe_resumo_ao_concluir(self):
        saida_terminal = io.StringIO()
        with (
            patch("patos_agro.cli.carregar_pontos", return_value=(np.zeros((4, 2)), "EPSG:31983")),
            patch("patos_agro.cli.reconstruir_fileiras", return_value=[("linha", "reta", 0)]),
            patch("patos_agro.cli.salvar_fileiras") as salvar,
            redirect_stdout(saida_terminal),
        ):
            main(["--input", "dados/amostra.gpkg", "--output", "resultado"])

        salvar.assert_called_once()
        self.assertIn("resultado", saida_terminal.getvalue())
        self.assertIn("amostra.geojson", saida_terminal.getvalue())
        self.assertIn("1 fileira", saida_terminal.getvalue())


if __name__ == "__main__":
    unittest.main()
