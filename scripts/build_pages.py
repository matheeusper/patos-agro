"""Monta o artefato estatico publicado pelo GitHub Pages."""

import argparse
import json
import shutil
import urllib.parse
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


RAIZ = Path(__file__).resolve().parents[1]
PACOTE = RAIZ / "patos_agro"
MODULOS_BROWSER = (
    "__init__.py",
    "browser_api.py",
    "erros.py",
    "geometria.py",
    "grafo.py",
    "io.py",
    "parametros.py",
    "reconstrucao.py",
    "visualizacao.py",
)
PACOTES_PYODIDE = ("numpy", "scipy", "shapely", "pyproj", "pandas", "geopandas", "fiona")


def url_estatica(endpoint, filename, **valores):
    if endpoint != "static":
        raise ValueError(f"endpoint não suportado no Pages: {endpoint}")
    consulta = urllib.parse.urlencode(valores)
    caminho = f"static/{filename}"
    return f"{caminho}?{consulta}" if consulta else caminho


def empacotar_python(destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as arquivo:
        for nome in MODULOS_BROWSER:
            arquivo.write(PACOTE / nome, f"patos_agro/{nome}")


def copiar_runtime(runtime, destino):
    manifesto = json.loads((runtime / "pyodide-lock.json").read_text(encoding="utf-8"))
    pacotes = manifesto["packages"]
    selecionados = set()
    pendentes = list(PACOTES_PYODIDE)
    while pendentes:
        nome = pendentes.pop()
        if nome in selecionados:
            continue
        if nome not in pacotes:
            raise ValueError(f"pacote ausente no runtime Pyodide: {nome}")
        selecionados.add(nome)
        pendentes.extend(pacotes[nome].get("depends", ()))

    arquivos_pacotes = {dados["file_name"] for dados in pacotes.values()}
    arquivos_necessarios = {pacotes[nome]["file_name"] for nome in selecionados}
    destino.mkdir(parents=True)
    for origem in runtime.iterdir():
        if not origem.is_file():
            continue
        if origem.name in arquivos_pacotes and origem.name not in arquivos_necessarios:
            continue
        shutil.copy2(origem, destino / origem.name)


def montar(destino, runtime=None):
    destino = destino.resolve()
    if destino == RAIZ or RAIZ not in destino.parents:
        raise ValueError("o destino do build deve ficar dentro do repositório")
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    ambiente = Environment(
        loader=FileSystemLoader(PACOTE / "templates"),
        autoescape=select_autoescape(("html", "xml")),
    )
    pagina = ambiente.get_template("visualizador.html").render(
        pages_mode=True,
        url_for=url_estatica,
    )
    (destino / "index.html").write_text(pagina, encoding="utf-8")
    (destino / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copytree(PACOTE / "static", destino / "static")
    empacotar_python(destino / "python" / "patos_agro.zip")

    if runtime:
        runtime = runtime.resolve()
        if not (runtime / "pyodide.js").is_file():
            raise ValueError(f"runtime Pyodide inválido: {runtime}")
        copiar_runtime(runtime, destino / "pyodide")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RAIZ / "_site")
    parser.add_argument("--runtime", type=Path)
    argumentos = parser.parse_args()
    montar(argumentos.output, argumentos.runtime)
    print(f"Site estático criado em {argumentos.output.resolve()}")


if __name__ == "__main__":
    main()
