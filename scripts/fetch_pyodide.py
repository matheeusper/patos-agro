"""Baixa e valida uma distribuicao Pyodide fixa para o artefato Pages."""

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


VERSAO = "314.0.6"
BASE = f"https://github.com/pyodide/pyodide/releases/download/{VERSAO}"
NOME = f"pyodide-{VERSAO}.tar.bz2"
SHA256_ESPERADO = "fd25b21567f83f83b0b8bb1780a5458c6d4dd10bb07a22004424194022037f00"


def baixar(url, destino):
    with urllib.request.urlopen(url) as resposta, destino.open("wb") as arquivo:
        shutil.copyfileobj(resposta, arquivo)


def sha256(caminho):
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def extrair_seguro(arquivo, destino):
    destino_resolvido = destino.resolve()
    with tarfile.open(arquivo, "r:bz2") as pacote:
        for membro in pacote.getmembers():
            alvo = (destino / membro.name).resolve()
            if alvo != destino_resolvido and destino_resolvido not in alvo.parents:
                raise ValueError("arquivo Pyodide contém caminho inseguro")
        pacote.extractall(destino, filter="data")


def preparar(destino):
    destino = destino.resolve()
    with tempfile.TemporaryDirectory(prefix="patos-pyodide-") as temporario:
        temporario = Path(temporario)
        pacote = temporario / NOME
        baixar(f"{BASE}/{NOME}", pacote)
        obtido = sha256(pacote)
        if obtido != SHA256_ESPERADO:
            raise ValueError(
                f"checksum Pyodide inválido: esperado {SHA256_ESPERADO}, obtido {obtido}"
            )
        extraido = temporario / "extraido"
        extraido.mkdir()
        extrair_seguro(pacote, extraido)
        candidatos = list(extraido.rglob("pyodide.js"))
        if len(candidatos) != 1:
            raise ValueError("não foi possível localizar a distribuição Pyodide")
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(candidatos[0].parent, destino)
    print(f"Pyodide {VERSAO} preparado em {destino}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    argumentos = parser.parse_args()
    preparar(argumentos.output)


if __name__ == "__main__":
    main()
