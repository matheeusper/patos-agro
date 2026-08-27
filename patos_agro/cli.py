import argparse
import os
from pathlib import Path

from patos_agro.erros import ErroPatosAgro, ErroSaida
from patos_agro.io import carregar_pontos, salvar_fileiras
from patos_agro.reconstrucao import reconstruir_fileiras


# Lê os caminhos de entrada e saída informados pela linha de comando.
def criar_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True, help="diretório onde o GeoJSON será salvo")
    return parser


def parse_args(argv=None):
    return criar_parser().parse_args(argv)


def montar_caminho_saida(caminho_entrada, diretorio_saida):
    nome_saida = Path(caminho_entrada).with_suffix(".geojson").name
    return Path(diretorio_saida) / nome_saida


def caminhos_representam_mesmo_arquivo(primeiro, segundo):
    primeiro_normalizado = os.path.normcase(os.path.realpath(primeiro))
    segundo_normalizado = os.path.normcase(os.path.realpath(segundo))
    return primeiro_normalizado == segundo_normalizado


# Executa a reconstrução das fileiras e salva o resultado.
def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)

    try:
        coordenadas, crs_utm = carregar_pontos(args.input)
        caminho_saida = montar_caminho_saida(args.input, args.output)
        if caminhos_representam_mesmo_arquivo(args.input, caminho_saida):
            raise ErroSaida("o arquivo de saída não pode sobrescrever o arquivo de entrada")
        fileiras = reconstruir_fileiras(coordenadas)
        salvar_fileiras(fileiras, crs_utm, caminho_saida)
    except ErroPatosAgro as erro:
        parser.exit(1, f"erro: {erro}\n")

    quantidade = len(fileiras)
    unidade = "fileira" if quantidade == 1 else "fileiras"
    print(f"Arquivo salvo em {caminho_saida} ({quantidade} {unidade}).")
