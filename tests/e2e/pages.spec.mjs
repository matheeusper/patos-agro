import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const raiz = path.resolve(import.meta.dirname, "../..");

function distanciaMetros([lonA, latA], [lonB, latB]) {
  const rad = Math.PI / 180;
  const dLat = (latB - latA) * rad;
  const dLon = (lonB - lonA) * rad;
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(latA * rad) * Math.cos(latB * rad) * Math.sin(dLon / 2) ** 2;
  return 6371008.8 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function conferirEquivalencia(atual, esperado) {
  expect(atual.features).toHaveLength(esperado.features.length);
  let maiorDiferenca = 0;
  atual.features.forEach((feature, indice) => {
    const referencia = esperado.features[indice];
    expect(feature.properties).toEqual(referencia.properties);
    expect(feature.geometry.type).toBe(referencia.geometry.type);
    expect(feature.geometry.coordinates).toHaveLength(referencia.geometry.coordinates.length);
    feature.geometry.coordinates.forEach((coordenada, ponto) => {
      maiorDiferenca = Math.max(
        maiorDiferenca,
        distanciaMetros(coordenada, referencia.geometry.coordinates[ponto]),
      );
    });
  });
  expect(maiorDiferenca).toBeLessThanOrEqual(0.0005);
}

async function baixarResultado(page) {
  const downloadPromise = page.waitForEvent("download");
  await page.locator("#download-button").click();
  const download = await downloadPromise;
  return JSON.parse(await fs.readFile(await download.path(), "utf8"));
}

async function aguardarResultado(page, seletor) {
  const resultado = await page.waitForFunction((alvo) => {
    const elemento = document.querySelector(alvo);
    if (elemento && !elemento.classList.contains("is-hidden")) return { ok: true };
    const toast = document.querySelector("#toast");
    if (toast && toast.classList.contains("is-error") && !toast.classList.contains("is-hidden")) {
      return { ok: false, erro: toast.textContent };
    }
    return null;
  }, seletor, { timeout: 90_000 });
  const estado = await resultado.jsonValue();
  if (!estado.ok) throw new Error(`Erro da aplicação: ${estado.erro}`);
}

async function abrirArquivo(page, arquivo) {
  await page.locator("#file-input").setInputFiles(arquivo);
  await aguardarResultado(page, "#analysis-panel");
  await expect(page.locator("#loading-overlay")).toHaveClass(/is-hidden/);
}

test("processa GeoJSON, recalcula e baixa sem chamar API", async ({ page }) => {
  const chamadasApi = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.includes("/api/")) chamadasApi.push(request.url());
  });
  await page.goto(".");
  await abrirArquivo(page, path.join(raiz, "dataset/amostra2.geojson"));
  await expect(page.locator("#stage-menu button")).toHaveCount(9);
  const resultado = await baixarResultado(page);
  expect(resultado.features).toHaveLength(12);

  await page.locator("#parameters-button").click();
  await page.locator("#parameters-panel details summary").click();
  await page.locator("#parameter-min_pontos_fileira").fill("5");
  await expect(page.locator("#parameters-status")).toContainText("Atualizado em");
  await page.locator("#inspector-tab-stage").click();
  await page.locator("#pin-reference-button").click();
  await expect(page.locator("#reference-mode-button")).toBeEnabled();
  expect(chamadasApi).toEqual([]);
});

test("mantém equivalência geométrica das cinco amostras", async ({ page }) => {
  await page.goto(".");
  for (let numero = 1; numero <= 5; numero += 1) {
    const nome = `amostra${numero}.geojson`;
    await abrirArquivo(page, path.join(raiz, "dataset", nome));
    const atual = await baixarResultado(page);
    const esperado = JSON.parse(await fs.readFile(path.join(raiz, "tests/snapshots", nome), "utf8"));
    conferirEquivalencia(atual, esperado);
  }
});

test("lista somente camadas de pontos do GeoPackage", async ({ page }) => {
  await page.goto(".");
  await page.locator("#file-input").setInputFiles(path.join(raiz, ".cache/pages-tests/camadas.gpkg"));
  await aguardarResultado(page, "#layer-modal");
  await expect(page.locator("#layer-select option")).toHaveCount(2);
  await page.locator("#layer-select").selectOption("plantas_b");
  await page.locator("#layer-confirm-button").click();
  await expect(page.locator("#analysis-panel")).not.toHaveClass(/is-hidden/);
});

test("rejeita arquivo acima de 25 MB antes do WebAssembly", async ({ page }) => {
  await page.goto(".");
  await page.locator("#file-input").setInputFiles({
    name: "grande.geojson",
    mimeType: "application/geo+json",
    buffer: Buffer.alloc(25 * 1024 * 1024 + 1),
  });
  await expect(page.locator("#toast")).toContainText("25 MB");
});
