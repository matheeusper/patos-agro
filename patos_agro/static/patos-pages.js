/* Adaptador das rotas Flask para processamento local em um Web Worker. */

(() => {
  const scriptBase = new URL(".", document.currentScript.src);
  let worker = null;
  let sequencia = 0;
  let operacaoPesada = null;
  const pendentes = new Map();

  function erroAbortado() {
    return new DOMException("Operação substituída por um novo arquivo.", "AbortError");
  }

  function criarWorker() {
    const instancia = new Worker(new URL("processador.worker.js", scriptBase), { type: "module" });
    instancia.onmessage = (evento) => {
      const chamada = pendentes.get(evento.data.id);
      if (!chamada) return;
      pendentes.delete(evento.data.id);
      if (operacaoPesada === evento.data.id) operacaoPesada = null;
      if (evento.data.ok) chamada.resolve(evento.data.resultado);
      else chamada.reject(new Error(evento.data.erro));
    };
    instancia.onerror = (evento) => {
      const detalhe = evento.message ? ` (${evento.message})` : "";
      const erro = new Error(`Não foi possível iniciar o processamento local. Tente novamente.${detalhe}`);
      pendentes.forEach(({ reject }) => reject(erro));
      pendentes.clear();
      operacaoPesada = null;
    };
    return instancia;
  }

  function reiniciarWorker() {
    if (worker) worker.terminate();
    pendentes.forEach(({ reject }) => reject(erroAbortado()));
    pendentes.clear();
    operacaoPesada = null;
    worker = criarWorker();
  }

  function chamar(tipo, payload = {}, transferiveis = [], pesada = false) {
    if (!worker) worker = criarWorker();
    if (pesada && operacaoPesada !== null) reiniciarWorker();
    const id = ++sequencia;
    if (pesada) operacaoPesada = id;
    return new Promise((resolve, reject) => {
      pendentes.set(id, { resolve, reject });
      worker.postMessage({ id, tipo, payload }, transferiveis);
    });
  }

  async function dadosArquivo(arquivo) {
    const conteudo = await arquivo.arrayBuffer();
    return { nome: arquivo.name, conteudo };
  }

  async function enviarFormulario(url, formulario) {
    const arquivo = formulario.get("arquivo");
    if (!(arquivo instanceof File)) throw new Error("selecione um arquivo GeoJSON ou GeoPackage");
    const payload = await dadosArquivo(arquivo);
    if (url === "/api/camadas") {
      return chamar("camadas", payload, [payload.conteudo], true);
    }
    if (url === "/api/processar") {
      payload.camada = formulario.get("camada") || "";
      const parametros = formulario.get("parametros");
      payload.parametros = parametros ? JSON.parse(parametros) : null;
      return chamar("processar", payload, [payload.conteudo], true);
    }
    throw new Error("operação não suportada");
  }

  window.PatosPagesApi = {
    enviarFormulario,
    obterParametros: () => chamar("init"),
    reprocessar: (corpo) => chamar("reprocessar", corpo, [], true),
    descartar: (sessaoId) => chamar("descartar", { sessao_id: sessaoId }).catch(() => null),
  };
})();
