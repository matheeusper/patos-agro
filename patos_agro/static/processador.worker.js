/* Processamento Python local para a versao estatica do GitHub Pages. */

let pyodide = null;
let browserApi = null;
let inicializacao = null;

function urlRelativa(caminho) {
  return new URL(caminho, self.location.href);
}

async function inicializar() {
  if (browserApi) return;
  if (inicializacao) return inicializacao;
  inicializacao = (async () => {
    const indexURL = urlRelativa("../pyodide/").href;
    importScripts(`${indexURL}pyodide.js`);
    pyodide = await loadPyodide({ indexURL });
    await pyodide.loadPackage(["numpy", "scipy", "shapely", "pyproj", "pandas", "geopandas", "fiona"]);
    const resposta = await fetch(urlRelativa("../python/patos_agro.zip"));
    if (!resposta.ok) throw new Error("não foi possível carregar o código do PatosAgro");
    pyodide.unpackArchive(await resposta.arrayBuffer(), "zip");
    browserApi = pyodide.pyimport("patos_agro.browser_api");
  })();
  try {
    await inicializacao;
  } catch (erro) {
    inicializacao = null;
    throw erro;
  }
}

function interpretarResposta(texto) {
  const envelope = JSON.parse(texto);
  if (!envelope.ok) throw new Error(envelope.erro || "não foi possível concluir o processamento");
  return envelope.resultado;
}

function caminhoTemporario(nome) {
  const extensao = String(nome || "").toLowerCase().endsWith(".gpkg") ? ".gpkg" : ".geojson";
  return `/tmp/patos-agro-${crypto.randomUUID()}${extensao}`;
}

async function comArquivo(payload, operacao) {
  const caminho = caminhoTemporario(payload.nome);
  pyodide.FS.writeFile(caminho, new Uint8Array(payload.conteudo));
  try {
    return await operacao(caminho);
  } finally {
    try { pyodide.FS.unlink(caminho); } catch (_erro) { /* arquivo já removido */ }
  }
}

async function executar(tipo, payload = {}) {
  await inicializar();
  if (tipo === "init") return interpretarResposta(browserApi.obter_parametros());
  if (tipo === "camadas") {
    return comArquivo(payload, (caminho) => interpretarResposta(browserApi.listar_camadas(caminho)));
  }
  if (tipo === "processar") {
    return comArquivo(payload, (caminho) => interpretarResposta(browserApi.processar(
      caminho,
      payload.nome,
      payload.camada || "",
      payload.parametros ? JSON.stringify(payload.parametros) : "",
    )));
  }
  if (tipo === "reprocessar") {
    return interpretarResposta(browserApi.reprocessar(
      payload.sessao_id,
      JSON.stringify(payload.parametros || {}),
    ));
  }
  if (tipo === "descartar") {
    return interpretarResposta(browserApi.descartar(payload.sessao_id || ""));
  }
  throw new Error("operação desconhecida");
}

self.onmessage = async (evento) => {
  const { id, tipo, payload } = evento.data;
  try {
    const resultado = await executar(tipo, payload);
    self.postMessage({ id, ok: true, resultado });
  } catch (erro) {
    self.postMessage({
      id,
      ok: false,
      erro: erro?.message || "não foi possível concluir o processamento",
    });
  }
};
