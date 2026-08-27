"""Gera GeoPackages efemeros usados apenas pelos testes E2E."""

import argparse
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, Polygon


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    argumentos = parser.parse_args()
    argumentos.output.parent.mkdir(parents=True, exist_ok=True)

    pontos_a = gpd.GeoDataFrame(
        geometry=[
            Point(-47.0000, -15.0000),
            Point(-47.0010, -15.0000),
            Point(-47.0000, -15.0010),
            Point(-47.0010, -15.0010),
        ],
        crs="EPSG:4326",
    )
    pontos_b = pontos_a.set_geometry(pontos_a.geometry.translate(yoff=-0.001))
    limite = gpd.GeoDataFrame(
        geometry=[Polygon([(-47.01, -15.01), (-46.99, -15.01), (-46.99, -14.99), (-47.01, -14.99)])],
        crs="EPSG:4326",
    )
    pontos_a.to_file(argumentos.output, layer="plantas_a", driver="GPKG")
    pontos_b.to_file(argumentos.output, layer="plantas_b", driver="GPKG", append=True)
    limite.to_file(argumentos.output, layer="limite", driver="GPKG", append=True)


if __name__ == "__main__":
    main()
