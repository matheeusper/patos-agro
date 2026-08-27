import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_pages import montar


RAIZ = Path(__file__).resolve().parents[1]


class TestBuildPages(unittest.TestCase):
    def test_monta_site_estatico_com_caminhos_relativos(self):
        with tempfile.TemporaryDirectory(dir=RAIZ) as temporario:
            destino = Path(temporario) / "site"
            montar(destino)
            html = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="static/patos-pages.js?v=1"', html)
            self.assertIn('src="static/visualizador.js?v=9"', html)
            self.assertNotIn('src="/static/', html)
            self.assertNotIn('href="/static/', html)
            self.assertTrue((destino / ".nojekyll").is_file())
            self.assertTrue((destino / "static" / "processador.worker.js").is_file())

    def test_pacote_python_contem_apenas_modulos_do_runtime(self):
        with tempfile.TemporaryDirectory(dir=RAIZ) as temporario:
            destino = Path(temporario) / "site"
            montar(destino)
            with zipfile.ZipFile(destino / "python" / "patos_agro.zip") as arquivo:
                nomes = set(arquivo.namelist())
            self.assertIn("patos_agro/browser_api.py", nomes)
            self.assertIn("patos_agro/reconstrucao.py", nomes)
            self.assertNotIn("patos_agro/web.py", nomes)
            self.assertNotIn("patos_agro/cli.py", nomes)

    def test_worker_expoe_todas_as_operacoes_locais(self):
        worker = (RAIZ / "patos_agro" / "static" / "processador.worker.js").read_text(encoding="utf-8")
        adaptador = (RAIZ / "patos_agro" / "static" / "patos-pages.js").read_text(encoding="utf-8")
        for operacao in ("init", "camadas", "processar", "reprocessar", "descartar"):
            self.assertIn(f'"{operacao}"', worker)
        self.assertIn("window.PatosPagesApi", adaptador)
        self.assertIn("new Worker", adaptador)


if __name__ == "__main__":
    unittest.main()
