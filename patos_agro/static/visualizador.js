const stageNames = [
  "Pontos recebidos",
  "Triangulação Delaunay",
  "Direções locais",
  "Estimativa de escalas",
  "Classificação de arestas",
  "Grafo inicial",
  "Conexão de lacunas",
  "Componentes e splines",
  "Fileiras finais",
];

const STORAGE_KEYS = {
  theme: "patos-agro-tema",
  basemap: "patos-agro-mapa-base",
  basemapStyle: "patos-agro-estilo-mapa-base",
  parameters: "patos-agro-parametros-v1",
};

const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const EOX_ATTRIBUTION = '<a href="https://cloudless.eox.at/">EOX Cloudless</a> (uso n\u00e3o comercial)';
const OAM_ATTRIBUTION = '<a href="https://openaerialmap.org/">OpenAerialMap</a> / Open Imagery Network, CC BY 4.0';

const BASEMAP_PROVIDERS = {
  streets: {
    label: "Ruas",
    note: "Ruas do OpenStreetMap.",
    layers: [{
      url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      options: { maxNativeZoom: 19, maxZoom: 22, className: "basemap-cartographic", attribution: OSM_ATTRIBUTION },
    }],
  },
  satellite: {
    label: "Sat\u00e9lite global",
    note: "Sentinel-2 global, cerca de 10 m por pixel. Uso n\u00e3o comercial.",
    layers: [{
      url: "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
      options: { maxNativeZoom: 14, maxZoom: 22, className: "basemap-imagery", attribution: EOX_ATTRIBUTION },
    }],
  },
  hybrid: {
    label: "Sat\u00e9lite com r\u00f3tulos",
    note: "Sentinel-2 com nomes, limites e vias. Uso n\u00e3o comercial.",
    layers: [
      {
        url: "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
        options: { maxNativeZoom: 14, maxZoom: 22, className: "basemap-imagery", attribution: EOX_ATTRIBUTION },
      },
      {
        url: "https://tiles.maps.eox.at/wmts/1.0.0/overlay_bright_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.png",
        options: { maxNativeZoom: 20, maxZoom: 22, className: "basemap-labels", attribution: OSM_ATTRIBUTION },
      },
    ],
  },
  aerial: {
    label: "A\u00e9reo aberto",
    note: "OpenAerialMap em zoom 14 ou maior; a cobertura varia por regi\u00e3o.",
    missingCoverageMessage: "N\u00e3o foi encontrada cobertura a\u00e9rea nessa \u00e1rea. O mapa de ruas permanece vis\u00edvel.",
    layers: [
      {
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        options: { maxNativeZoom: 19, maxZoom: 22, className: "basemap-cartographic", attribution: OSM_ATTRIBUTION },
      },
      {
        url: "https://global.imagery.hotosm.org/{z}/{x}/{y}.png",
        options: { minZoom: 14, maxZoom: 22, className: "basemap-imagery basemap-aerial", attribution: OAM_ATTRIBUTION },
        coverageLayer: true,
      },
    ],
  },
  topographic: {
    label: "Topogr\u00e1fico",
    note: "Relevo e terreno da EOX. Uso n\u00e3o comercial.",
    layers: [{
      url: "https://tiles.maps.eox.at/wmts/1.0.0/terrain_3857/default/g/{z}/{y}/{x}.jpg",
      options: { maxNativeZoom: 20, maxZoom: 22, className: "basemap-terrain", attribution: EOX_ATTRIBUTION },
    }],
  },
  dark: {
    label: "Escuro",
    note: "Mapa de ruas com apar\u00eancia escura.",
    layers: [{
      url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      options: { maxNativeZoom: 19, maxZoom: 22, className: "basemap-dark", attribution: OSM_ATTRIBUTION },
    }],
  },
  neutral: {
    label: "Neutro",
    note: "Fundo neutro, sem tiles externos.",
    layers: [],
  },
};

function storedBaseMapStyle() {
  const stored = readPreference(STORAGE_KEYS.basemapStyle);
  return Object.hasOwn(BASEMAP_PROVIDERS, stored) ? stored : "streets";
}

function readPreference(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (_error) {
    return null;
  }
}

function savePreference(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (_error) {
    // O visualizador continua funcionando quando o armazenamento está bloqueado.
  }
}

const state = {
  payload: null,
  file: null,
  layer: null,
  stageIndex: 0,
  mode: "single",
  playing: false,
  playTimer: null,
  requestController: null,
  hiddenLayers: new Set(),
  maps: {},
  baseLayers: {},
  mapGroups: {},
  syncingMaps: false,
  theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  baseMapEnabled: readPreference(STORAGE_KEYS.basemap) !== "false",
  baseMapStyle: storedBaseMapStyle(),
  baseMapWarnings: new Set(),
  parameterSchema: null,
  parameters: null,
  sessionId: null,
  referencePayload: null,
  parameterTimer: null,
  reprocessing: false,
  pendingReprocess: false,
  inspectorTab: "stage",
  inspectorOpen: false,
};

const elements = {
  fileInput: document.getElementById("file-input"),
  basemapToggle: document.getElementById("basemap-toggle"),
  basemapToggleIcon: document.getElementById("basemap-toggle-icon"),
  basemapToggleLabel: document.getElementById("basemap-toggle-label"),
  basemapSelect: document.getElementById("basemap-select"),
  basemapNote: document.getElementById("basemap-note"),
  themeToggle: document.getElementById("theme-toggle"),
  themeToggleIcon: document.getElementById("theme-toggle-icon"),
  themeToggleLabel: document.getElementById("theme-toggle-label"),
  downloadButton: document.getElementById("download-button"),
  reprocessButton: document.getElementById("reprocess-button"),
  parametersButton: document.getElementById("parameters-button"),
  parametersPanel: document.getElementById("parameters-panel"),
  parametersBackdrop: document.getElementById("parameters-backdrop"),
  parametersClose: document.getElementById("parameters-close"),
  parametersStatus: document.getElementById("parameters-status"),
  parametersBasic: document.getElementById("parameters-basic"),
  parametersAdvanced: document.getElementById("parameters-advanced"),
  parametersReset: document.getElementById("parameters-reset"),
  parametersExport: document.getElementById("parameters-export"),
  parametersImport: document.getElementById("parameters-import"),
  presetSelect: document.getElementById("preset-select"),
  inspector: document.getElementById("inspector"),
  inspectorToggle: document.getElementById("inspector-toggle"),
  inspectorClose: document.getElementById("inspector-close"),
  inspectorTabs: document.querySelectorAll("[data-inspector-tab]"),
  inspectorPanels: document.querySelectorAll("[data-inspector-panel]"),
  pinReferenceButton: document.getElementById("pin-reference-button"),
  referenceModeButton: document.getElementById("reference-mode-button"),
  referenceSummary: document.getElementById("reference-summary"),
  stageMenu: document.getElementById("stage-menu"),
  fileCard: document.getElementById("file-card"),
  dropzone: document.getElementById("dropzone"),
  emptyState: document.getElementById("empty-state"),
  analysisPanel: document.getElementById("analysis-panel"),
  stageKicker: document.getElementById("stage-kicker"),
  stageTitle: document.getElementById("stage-title"),
  stageDescription: document.getElementById("stage-description"),
  metrics: document.getElementById("metrics"),
  legend: document.getElementById("legend"),
  mapLayout: document.getElementById("map-layout"),
  singleMapLabel: document.getElementById("single-map-label"),
  compareRightLabel: document.getElementById("compare-right-label"),
  compareLeftLabel: document.getElementById("compare-left-label"),
  restartButton: document.getElementById("restart-button"),
  previousButton: document.getElementById("previous-button"),
  playButton: document.getElementById("play-button"),
  nextButton: document.getElementById("next-button"),
  transportPosition: document.getElementById("transport-position"),
  loadingOverlay: document.getElementById("loading-overlay"),
  loadingTitle: document.getElementById("loading-title"),
  loadingDetail: document.getElementById("loading-detail"),
  layerModal: document.getElementById("layer-modal"),
  layerSelect: document.getElementById("layer-select"),
  layerCancelButton: document.getElementById("layer-cancel-button"),
  layerConfirmButton: document.getElementById("layer-confirm-button"),
  toast: document.getElementById("toast"),
};

let toastTimer = null;

function updateDisplayControls() {
  const mapAction = state.baseMapEnabled ? "Desativar mapa-base" : "Ativar mapa-base";
  elements.basemapToggle.setAttribute("aria-pressed", String(state.baseMapEnabled));
  elements.basemapToggle.setAttribute("aria-label", mapAction);
  elements.basemapToggle.title = mapAction;
  elements.basemapToggleIcon.textContent = state.baseMapEnabled ? "▦" : "□";
  elements.basemapToggleLabel.textContent = state.baseMapEnabled ? "Ocultar mapa" : "Mostrar mapa";

  const provider = BASEMAP_PROVIDERS[state.baseMapStyle];
  elements.basemapSelect.value = state.baseMapStyle;
  elements.basemapSelect.setAttribute("aria-label", `Mapa-base: ${provider.label}`);
  if (elements.basemapNote) {
    elements.basemapNote.textContent = state.baseMapEnabled
      ? provider.note
      : "Mapa-base desativado. As geometrias continuam vis\u00edveis.";
  }

  const dark = state.theme === "dark";
  const themeAction = dark ? "Ativar modo claro" : "Ativar modo escuro";
  elements.themeToggle.setAttribute("aria-pressed", String(dark));
  elements.themeToggle.setAttribute("aria-label", themeAction);
  elements.themeToggle.title = themeAction;
  elements.themeToggleIcon.textContent = dark ? "☀" : "☾";
  elements.themeToggleLabel.textContent = dark ? "Modo claro" : "Modo escuro";
}

function setBaseMapEnabled(enabled, persist = true) {
  state.baseMapEnabled = enabled;
  Object.entries(state.baseLayers).forEach(([mapKey, layers]) => {
    const map = state.maps[mapKey];
    if (!map) return;
    layers.forEach((layer) => {
      if (enabled && !map.hasLayer(layer)) layer.addTo(map);
      if (!enabled && map.hasLayer(layer)) map.removeLayer(layer);
    });
  });
  if (persist) savePreference(STORAGE_KEYS.basemap, String(enabled));
  updateDisplayControls();
}

function setBaseMapStyle(style, persist = true) {
  if (!Object.hasOwn(BASEMAP_PROVIDERS, style)) return;
  state.baseMapStyle = style;
  state.baseMapWarnings.clear();
  Object.entries(state.maps).forEach(([mapKey, map]) => replaceBaseMap(map, mapKey));
  if (persist) savePreference(STORAGE_KEYS.basemapStyle, style);
  updateDisplayControls();
}

function setTheme(theme, persist = true) {
  state.theme = theme === "dark" ? "dark" : "light";
  if (state.theme === "dark") document.documentElement.dataset.theme = "dark";
  else delete document.documentElement.dataset.theme;
  if (persist) savePreference(STORAGE_KEYS.theme, state.theme);
  updateDisplayControls();
  if (state.payload && state.maps.single) renderMaps();
}

function refreshLayoutState() {
  if (!isCompactLayout()) {
    elements.parametersBackdrop.classList.add("is-hidden");
    elements.inspector.classList.remove("is-mobile-open");
    elements.inspectorToggle.setAttribute("aria-expanded", "false");
    return;
  }
  elements.inspector.classList.toggle("is-mobile-open", state.inspectorOpen);
  elements.parametersBackdrop.classList.toggle("is-hidden", !state.inspectorOpen);
  elements.inspectorToggle.setAttribute("aria-expanded", String(state.inspectorOpen));
}

function isCompactLayout() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setInspectorTab(tab) {
  state.inspectorTab = tab;
  elements.parametersButton.setAttribute("aria-expanded", String(tab === "settings" && (!isCompactLayout() || state.inspectorOpen)));
  elements.inspectorTabs.forEach((button) => {
    const selected = button.dataset.inspectorTab === tab;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.setAttribute("tabindex", selected ? "0" : "-1");
  });
  elements.inspectorPanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.inspectorPanel === tab);
  });
}

function setInspectorOpen(open) {
  state.inspectorOpen = open;
  elements.inspector.classList.toggle("is-mobile-open", open);
  elements.inspectorToggle.setAttribute("aria-expanded", String(open));
  elements.parametersButton.setAttribute("aria-expanded", String(open && state.inspectorTab === "settings"));
  elements.parametersBackdrop.classList.toggle("is-hidden", !(open && isCompactLayout()));
  if (open && isCompactLayout()) {
    const activeTab = [...elements.inspectorTabs].find((button) => button.dataset.inspectorTab === state.inspectorTab);
    activeTab?.focus();
  }
}

function openInspectorTab(tab) {
  setInspectorTab(tab);
  setInspectorOpen(true);
}

function createStageMenu() {
  stageNames.forEach((name, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "stage-item";
    button.disabled = true;
    button.dataset.stageIndex = String(index);

    const number = document.createElement("span");
    number.className = "stage-number";
    number.textContent = String(index + 1).padStart(2, "0");
    const label = document.createElement("span");
    label.className = "stage-name";
    label.textContent = name;
    button.append(number, label);
    button.addEventListener("click", () => {
      stopPlayback();
      selectStage(index);
      if (isCompactLayout()) openInspectorTab("stage");
    });
    elements.stageMenu.append(button);
  });
}

function showToast(message, isError = false) {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", isError);
  elements.toast.classList.remove("is-hidden");
  toastTimer = window.setTimeout(() => elements.toast.classList.add("is-hidden"), 5200);
}

function showLoading(title, detail) {
  elements.loadingTitle.textContent = title;
  elements.loadingDetail.textContent = detail;
  elements.loadingOverlay.classList.remove("is-hidden");
}

function hideLoading() {
  elements.loadingOverlay.classList.add("is-hidden");
}

function extensionOf(file) {
  const dot = file.name.lastIndexOf(".");
  return dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
}

function validateFile(file) {
  if (!file) throw new Error("Selecione um arquivo para continuar.");
  if (![".geojson", ".gpkg"].includes(extensionOf(file))) {
    throw new Error("Envie um arquivo GeoJSON ou GeoPackage.");
  }
  if (file.size > 25 * 1024 * 1024) {
    throw new Error("O arquivo excede o limite de 25 MB.");
  }
}

function updateFileCard(file, layer = null) {
  elements.fileCard.replaceChildren();
  const icon = document.createElement("span");
  icon.className = "file-icon";
  icon.textContent = "✓";
  const copy = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = file.name;
  const detail = document.createElement("small");
  detail.textContent = layer ? `Camada: ${layer}` : `${(file.size / 1024).toFixed(1)} KB`;
  copy.append(name, detail);
  elements.fileCard.append(icon, copy);
}

async function requestJson(url, formData) {
  if (state.requestController) state.requestController.abort();
  state.requestController = new AbortController();
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
      signal: state.requestController.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Não foi possível conectar ao servidor local.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.erro || "Não foi possível processar o arquivo.");
  return data;
}

async function requestJsonBody(url, body) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (_error) {
    throw new Error("Não foi possível conectar ao servidor local.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.erro || "Não foi possível recalcular o resultado.");
  return data;
}

async function inspectPackage(file) {
  showLoading("Lendo o GeoPackage", "Identificando as camadas de pontos disponíveis…");
  const formData = new FormData();
  formData.append("arquivo", file);
  const data = await requestJson("/api/camadas", formData);
  hideLoading();
  return data.camadas;
}

function openLayerModal(layers) {
  elements.layerSelect.replaceChildren();
  layers.forEach((layer) => {
    const option = document.createElement("option");
    option.value = layer.nome;
    option.textContent = `${layer.nome} · ${layer.tipo}`;
    elements.layerSelect.append(option);
  });
  elements.layerModal.classList.remove("is-hidden");
  elements.layerSelect.focus();
}

function closeLayerModal() {
  elements.layerModal.classList.add("is-hidden");
}

async function acceptFile(file) {
  try {
    validateFile(file);
    stopPlayback();
    state.file = file;
    state.layer = null;
    updateFileCard(file);
    if (extensionOf(file) === ".gpkg") {
      const layers = await inspectPackage(file);
      if (layers.length > 1) {
        openLayerModal(layers);
        return;
      }
      state.layer = layers[0]?.nome || null;
    }
    await processFile();
  } catch (error) {
    hideLoading();
    if (error.name !== "AbortError") showToast(error.message, true);
  }
}

async function processFile() {
  if (!state.file) return;
  try {
    showLoading("Processando o campo", "Calculando pontos, conexões, componentes e fileiras…");
    const formData = new FormData();
    formData.append("arquivo", state.file);
    if (state.layer) formData.append("camada", state.layer);
    if (state.parameters) formData.append("parametros", JSON.stringify(state.parameters));
    const previousSession = state.sessionId;
    const payload = await requestJson("/api/processar", formData);
    state.payload = payload;
    state.sessionId = payload.sessao_id;
    state.parameters = payload.parametros;
    renderParameterFields();
    if (previousSession && previousSession !== state.sessionId) {
      fetch(`/api/sessoes/${encodeURIComponent(previousSession)}`, { method: "DELETE" }).catch(() => {});
    }
    state.stageIndex = 0;
    state.hiddenLayers.clear();
    updateFileCard(state.file, payload.arquivo.camada);
    presentAnalysis();
    showToast(`${payload.resultado.geojson.features.length} fileiras reconstruídas.`);
  } catch (error) {
    if (error.name !== "AbortError") showToast(error.message, true);
  } finally {
    hideLoading();
  }
}

function watchBaseMapFailures(layer, provider, definition) {
  let failures = 0;
  layer.on("tileload", () => { failures = 0; });
  layer.on("tileerror", () => {
    failures += 1;
    if (failures < 8 || state.baseMapWarnings.has(provider)) return;
    state.baseMapWarnings.add(provider);
    const message = definition.coverageLayer
      ? BASEMAP_PROVIDERS[provider].missingCoverageMessage
      : `${BASEMAP_PROVIDERS[provider].label} indispon\u00edvel. As geometrias continuam vis\u00edveis.`;
    showToast(message, false);
  });
}

function buildBaseMapLayers(provider) {
  return BASEMAP_PROVIDERS[provider].layers.map((definition) => {
    const layer = L.tileLayer(definition.url, {
      keepBuffer: 4,
      crossOrigin: true,
      ...definition.options,
    });
    watchBaseMapFailures(layer, provider, definition);
    return layer;
  });
}

function replaceBaseMap(map, mapKey) {
  (state.baseLayers[mapKey] || []).forEach((layer) => {
    if (map.hasLayer(layer)) map.removeLayer(layer);
  });
  const layers = buildBaseMapLayers(state.baseMapStyle);
  state.baseLayers[mapKey] = layers;
  if (state.baseMapEnabled) layers.forEach((layer) => layer.addTo(map));
}

function createMap(id, mapKey) {
  const map = L.map(id, {
    preferCanvas: true,
    zoomControl: true,
    attributionControl: true,
  });
  replaceBaseMap(map, mapKey);
  return map;
}

function initializeMaps() {
  if (state.maps.single) return;
  state.maps.single = createMap("single-map", "single");
  state.maps.left = createMap("compare-left-map", "left");
  state.maps.right = createMap("compare-right-map", "right");

  const synchronize = (source, target) => {
    source.on("moveend", () => {
      if (state.syncingMaps || !["compare", "reference"].includes(state.mode)) return;
      state.syncingMaps = true;
      target.setView(source.getCenter(), source.getZoom(), { animate: false });
      state.syncingMaps = false;
    });
  };
  synchronize(state.maps.left, state.maps.right);
  synchronize(state.maps.right, state.maps.left);
}

function popupContent(properties) {
  const wrapper = document.createElement("div");
  Object.entries(properties || {}).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const row = document.createElement("div");
    const label = document.createElement("strong");
    label.textContent = `${key.replaceAll("_", " ")}: `;
    row.append(label, document.createTextNode(String(value)));
    wrapper.append(row);
  });
  return wrapper;
}

function createLeafletLayer(layerId, payload = state.payload) {
  const descriptor = payload.camadas[layerId];
  const markerStroke = getComputedStyle(document.documentElement).getPropertyValue("--marker-stroke").trim() || "#fffef8";
  const lineStyle = (feature) => ({
    color: descriptor.cores_por_tipo?.[feature.properties?.tipo] || descriptor.cor,
    weight: descriptor.espessura || 2,
    opacity: 0.88,
    dashArray: descriptor.tracejado || null,
  });
  return L.geoJSON(descriptor.dados, {
    style: lineStyle,
    pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
      radius: layerId === "duplicatas" ? 5 : 3.5,
      color: markerStroke,
      weight: 1,
      fillColor: descriptor.cor,
      fillOpacity: 0.9,
    }),
    onEachFeature: (feature, layer) => {
      if (feature.properties && Object.keys(feature.properties).length) {
        layer.bindPopup(popupContent(feature.properties));
      }
    },
  });
}

function clearMapGroup(mapKey) {
  const group = state.mapGroups[mapKey];
  if (group && state.maps[mapKey].hasLayer(group)) state.maps[mapKey].removeLayer(group);
  state.mapGroups[mapKey] = L.layerGroup().addTo(state.maps[mapKey]);
}

function renderStageLayers(mapKey, layerIds, ignoreHidden = false, payload = state.payload) {
  clearMapGroup(mapKey);
  layerIds.forEach((layerId) => {
    if (!ignoreHidden && state.hiddenLayers.has(layerId)) return;
    createLeafletLayer(layerId, payload).addTo(state.mapGroups[mapKey]);
  });
}

function renderMaps() {
  if (!state.payload || !state.maps.single) return;
  const stage = state.payload.etapas[state.stageIndex];
  renderStageLayers("single", stage.camadas);
  if (state.mode === "reference" && state.referencePayload) {
    renderStageLayers("left", ["fileiras_finais", "pontos"], true, state.referencePayload);
    renderStageLayers("right", ["fileiras_finais", "pontos"], true);
  } else {
    renderStageLayers("left", ["pontos"], true);
    renderStageLayers("right", stage.camadas);
  }

  window.setTimeout(() => {
    Object.values(state.maps).forEach((map) => map.invalidateSize());
  }, 0);
}

function fitAllMaps() {
  const points = L.geoJSON(state.payload.camadas.pontos.dados);
  const bounds = points.getBounds();
  if (!bounds.isValid()) return;
  Object.values(state.maps).forEach((map) => map.fitBounds(bounds.pad(0.08), { animate: false }));
}

function renderMetrics(stage) {
  elements.metrics.replaceChildren();
  stage.metricas.forEach((metric) => {
    const item = document.createElement("div");
    item.className = "metric";
    const value = document.createElement("strong");
    value.textContent = metric.unidade ? `${metric.valor} ${metric.unidade}` : String(metric.valor);
    const label = document.createElement("small");
    label.textContent = metric.rotulo;
    item.append(value, label);
    elements.metrics.append(item);
  });
}

function renderLegend(stage) {
  elements.legend.replaceChildren();
  stage.camadas.forEach((layerId) => {
    const descriptor = state.payload.camadas[layerId];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "legend-item";
    button.classList.toggle("is-off", state.hiddenLayers.has(layerId));
    button.setAttribute("aria-pressed", String(!state.hiddenLayers.has(layerId)));
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.setProperty("--swatch", descriptor.cor);
    const label = document.createElement("span");
    label.textContent = descriptor.rotulo;
    button.append(swatch, label);
    button.addEventListener("click", () => {
      if (state.hiddenLayers.has(layerId)) state.hiddenLayers.delete(layerId);
      else state.hiddenLayers.add(layerId);
      renderLegend(stage);
      renderMaps();
    });
    elements.legend.append(button);
  });
}

function selectStage(index, resetHidden = true) {
  if (!state.payload) return;
  state.stageIndex = Math.max(0, Math.min(index, state.payload.etapas.length - 1));
  if (resetHidden) state.hiddenLayers.clear();
  const stage = state.payload.etapas[state.stageIndex];
  elements.stageKicker.textContent = `Etapa ${state.stageIndex + 1} de ${state.payload.etapas.length}`;
  elements.stageTitle.textContent = stage.titulo;
  elements.stageDescription.textContent = stage.descricao;
  elements.singleMapLabel.textContent = stage.titulo;
  elements.compareRightLabel.textContent = stage.titulo;
  elements.compareLeftLabel.textContent = state.mode === "reference" ? "Referência" : "Pontos originais";
  if (state.mode === "reference") elements.compareRightLabel.textContent = "Resultado atual";
  renderMetrics(stage);
  renderLegend(stage);
  if (elements.transportPosition) {
    elements.transportPosition.textContent = `${String(state.stageIndex + 1).padStart(2, "0")} / ${String(state.payload.etapas.length).padStart(2, "0")}`;
  }
  [...elements.stageMenu.children].forEach((button, buttonIndex) => {
    button.classList.toggle("is-active", buttonIndex === state.stageIndex);
    button.setAttribute("aria-current", buttonIndex === state.stageIndex ? "step" : "false");
  });
  elements.previousButton.disabled = state.stageIndex === 0;
  elements.nextButton.disabled = state.stageIndex === state.payload.etapas.length - 1;
  renderMaps();
}

function presentAnalysis() {
  elements.emptyState.classList.add("is-hidden");
  elements.analysisPanel.classList.remove("is-hidden");
  elements.downloadButton.disabled = false;
  elements.reprocessButton.disabled = false;
  [...elements.stageMenu.children].forEach((button) => { button.disabled = false; });
  setInspectorTab("stage");
  setInspectorOpen(false);
  initializeMaps();
  selectStage(0);
  window.setTimeout(fitAllMaps, 50);
}

function setMode(mode) {
  if (mode === "reference" && !state.referencePayload) return;
  state.mode = mode;
  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });
  elements.mapLayout.classList.toggle("is-compare", ["compare", "reference"].includes(mode));
  if (["compare", "reference"].includes(mode) && state.payload) selectStage(state.payload.etapas.length - 1);
  else renderMaps();
}

function stopPlayback() {
  window.clearInterval(state.playTimer);
  state.playTimer = null;
  state.playing = false;
  elements.playButton.textContent = "▶ Reproduzir";
}

function togglePlayback() {
  if (!state.payload) return;
  if (state.playing) {
    stopPlayback();
    return;
  }
  if (state.stageIndex === state.payload.etapas.length - 1) selectStage(0);
  state.playing = true;
  elements.playButton.textContent = "Ⅱ Pausar";
  state.playTimer = window.setInterval(() => {
    if (state.stageIndex >= state.payload.etapas.length - 1) {
      stopPlayback();
      return;
    }
    selectStage(state.stageIndex + 1);
  }, 1800);
}

function downloadResult() {
  if (!state.payload) return;
  const content = JSON.stringify(state.payload.resultado.geojson);
  const url = URL.createObjectURL(new Blob([content], { type: "application/geo+json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = state.payload.resultado.nome;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function setParametersPanel(open) {
  if (open) {
    openInspectorTab("settings");
    if (isCompactLayout()) elements.parametersClose.focus();
    return;
  }
  if (isCompactLayout()) setInspectorOpen(false);
  else setInspectorTab("stage");
}

function validateParameterObject(values) {
  if (!state.parameterSchema || !values || typeof values !== "object" || Array.isArray(values)) {
    throw new Error("Configuração de parâmetros inválida.");
  }
  const fields = new Map(state.parameterSchema.campos.map((field) => [field.nome, field]));
  const unknown = Object.keys(values).filter((name) => !fields.has(name));
  if (unknown.length) throw new Error(`Parâmetros desconhecidos: ${unknown.join(", ")}.`);
  const result = { ...state.parameterSchema.padrao };
  Object.entries(values).forEach(([name, value]) => {
    const field = fields.get(name);
    if (field.opcional && value === null) {
      result[name] = null;
      return;
    }
    if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${field.rotulo}: informe um número finito.`);
    if (value < field.minimo || value > field.maximo) throw new Error(`${field.rotulo}: valor fora dos limites.`);
    result[name] = value;
  });
  return result;
}

function persistParameters() {
  if (state.parameters) savePreference(STORAGE_KEYS.parameters, JSON.stringify({ versao: 1, parametros: state.parameters }));
}

function fieldValueChanged(field, numberInput, rangeInput) {
  const value = ["pontos_tangente", "iteracoes_lacunas", "min_pontos_fileira"].includes(field.nome)
    ? Number.parseInt(numberInput.value, 10)
    : Number.parseFloat(numberInput.value);
  state.parameters[field.nome] = value;
  if (rangeInput && rangeInput.value !== numberInput.value) rangeInput.value = numberInput.value;
  elements.presetSelect.value = "";
  persistParameters();
  scheduleReprocess();
}

function createParameterField(field) {
  const wrapper = document.createElement("div");
  wrapper.className = "parameter-field";
  const label = document.createElement("label");
  label.htmlFor = `parameter-${field.nome}`;
  label.textContent = field.rotulo;
  const unit = document.createElement("small");
  unit.textContent = field.unidade || `${field.minimo} a ${field.maximo}`;
  label.append(unit);
  const numberInput = document.createElement("input");
  numberInput.type = "number";
  numberInput.id = `parameter-${field.nome}`;
  numberInput.min = field.minimo;
  numberInput.max = field.maximo;
  numberInput.step = field.passo;
  const current = state.parameters[field.nome];
  numberInput.value = current === null ? "" : current;
  const rangeInput = document.createElement("input");
  rangeInput.type = "range";
  rangeInput.min = field.minimo;
  rangeInput.max = field.maximo;
  rangeInput.step = field.passo;
  rangeInput.value = current === null ? field.minimo : current;
  const update = () => fieldValueChanged(field, numberInput, rangeInput);
  numberInput.addEventListener("input", update);
  rangeInput.addEventListener("input", () => {
    numberInput.value = rangeInput.value;
    update();
  });
  wrapper.append(label, numberInput, rangeInput);
  if (field.opcional) {
    const autoLabel = document.createElement("label");
    autoLabel.className = "parameter-auto";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = current === null;
    numberInput.disabled = checkbox.checked;
    rangeInput.disabled = checkbox.checked;
    autoLabel.append(checkbox, document.createTextNode("Estimar automaticamente"));
    checkbox.addEventListener("change", () => {
      numberInput.disabled = checkbox.checked;
      rangeInput.disabled = checkbox.checked;
      if (checkbox.checked) state.parameters[field.nome] = null;
      else {
        const estimated = field.nome.includes("plantas")
          ? state.payload?.etapas?.[3]?.metricas?.[0]?.valor
          : state.payload?.etapas?.[3]?.metricas?.[1]?.valor;
        numberInput.value = estimated || field.minimo;
        rangeInput.value = numberInput.value;
        fieldValueChanged(field, numberInput, rangeInput);
      }
      persistParameters();
      scheduleReprocess();
    });
    wrapper.append(autoLabel);
  }
  return wrapper;
}

function renderParameterFields() {
  if (!state.parameterSchema || !state.parameters) return;
  elements.parametersBasic.replaceChildren();
  elements.parametersAdvanced.replaceChildren();
  state.parameterSchema.campos.forEach((field) => {
    const target = field.grupo === "avancado" ? elements.parametersAdvanced : elements.parametersBasic;
    target.append(createParameterField(field));
  });
}

function applyParameters(values, preset = "") {
  state.parameters = validateParameterObject(values);
  elements.presetSelect.value = preset;
  renderParameterFields();
  persistParameters();
  scheduleReprocess();
}

function scheduleReprocess() {
  window.clearTimeout(state.parameterTimer);
  if (!state.sessionId) {
    elements.parametersStatus.textContent = "Parâmetros prontos para o próximo arquivo";
    return;
  }
  elements.parametersStatus.textContent = "Aguardando ajustes…";
  state.parameterTimer = window.setTimeout(reprocessParameters, 500);
}

async function reprocessParameters() {
  if (!state.sessionId || !state.parameters) return;
  if (state.reprocessing) {
    state.pendingReprocess = true;
    return;
  }
  state.reprocessing = true;
  state.pendingReprocess = false;
  const requested = JSON.stringify(state.parameters);
  elements.parametersStatus.textContent = "Recalculando…";
  elements.parametersStatus.classList.add("is-processing");
  try {
    const payload = await requestJsonBody("/api/reprocessar", {
      sessao_id: state.sessionId,
      parametros: JSON.parse(requested),
    });
    state.payload = payload;
    state.sessionId = payload.sessao_id;
    const index = Math.min(state.stageIndex, payload.etapas.length - 1);
    selectStage(index, false);
    updateReferenceSummary();
    elements.parametersStatus.textContent = `Atualizado em ${payload.resumo?.duracao_ms ?? "—"} ms`;
  } catch (error) {
    elements.parametersStatus.textContent = "O último resultado válido foi preservado";
    showToast(error.message, true);
  } finally {
    state.reprocessing = false;
    elements.parametersStatus.classList.remove("is-processing");
    if (state.pendingReprocess || requested !== JSON.stringify(state.parameters)) {
      state.pendingReprocess = false;
      reprocessParameters();
    }
  }
}

function updateReferenceSummary() {
  if (!state.referencePayload || !state.payload) {
    elements.referenceSummary.textContent = "Nenhuma referência fixada.";
    return;
  }
  const before = state.referencePayload.resumo;
  const current = state.payload.resumo;
  const rowDelta = current.fileiras - before.fileiras;
  const lengthDelta = (current.comprimento_total_m - before.comprimento_total_m).toFixed(1);
  elements.referenceSummary.textContent = `Fileiras ${rowDelta >= 0 ? "+" : ""}${rowDelta} · comprimento ${lengthDelta >= 0 ? "+" : ""}${lengthDelta} m`;
}

function pinReference() {
  if (!state.payload) return;
  state.referencePayload = state.payload;
  elements.referenceModeButton.disabled = false;
  elements.pinReferenceButton.textContent = "Atualizar referência";
  updateReferenceSummary();
  showToast("Resultado atual fixado como referência.");
}

function exportParameters() {
  if (!state.parameters) return;
  const content = JSON.stringify({ versao: 1, parametros: state.parameters }, null, 2);
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "parametros-patos-agro.json";
  link.click();
  URL.revokeObjectURL(url);
}

async function importParameters(file) {
  try {
    const configuration = JSON.parse(await file.text());
    if (configuration.versao !== 1) throw new Error("A versão da configuração não é compatível.");
    applyParameters(configuration.parametros);
    showToast("Parâmetros importados.");
  } catch (error) {
    showToast(error.message || "Não foi possível importar a configuração.", true);
  }
}

async function initializeParameters() {
  try {
    const response = await fetch("/api/parametros");
    if (!response.ok) throw new Error();
    state.parameterSchema = await response.json();
    let stored = null;
    try { stored = JSON.parse(readPreference(STORAGE_KEYS.parameters)); } catch (_error) { stored = null; }
    state.parameters = validateParameterObject(stored?.versao === 1 ? stored.parametros : state.parameterSchema.padrao);
    renderParameterFields();
  } catch (_error) {
    elements.parametersStatus.textContent = "Não foi possível carregar o esquema de parâmetros";
  }
}

updateDisplayControls();
createStageMenu();
initializeParameters();

elements.fileInput.addEventListener("change", () => {
  const [file] = elements.fileInput.files;
  elements.fileInput.value = "";
  acceptFile(file);
});

["dragenter", "dragover"].forEach((eventName) => elements.dropzone.addEventListener(eventName, (event) => {
  event.preventDefault();
  elements.dropzone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach((eventName) => elements.dropzone.addEventListener(eventName, (event) => {
  event.preventDefault();
  elements.dropzone.classList.remove("is-dragging");
}));
elements.dropzone.addEventListener("drop", (event) => acceptFile(event.dataTransfer.files[0]));
elements.reprocessButton.addEventListener("click", processFile);
elements.downloadButton.addEventListener("click", downloadResult);
elements.basemapToggle.addEventListener("click", () => setBaseMapEnabled(!state.baseMapEnabled));
elements.basemapSelect.addEventListener("change", () => setBaseMapStyle(elements.basemapSelect.value));
elements.themeToggle.addEventListener("click", () => setTheme(state.theme === "dark" ? "light" : "dark"));
elements.parametersButton.addEventListener("click", () => setParametersPanel(true));
elements.parametersClose.addEventListener("click", () => setParametersPanel(false));
elements.parametersBackdrop.addEventListener("click", () => setInspectorOpen(false));
elements.inspectorToggle.addEventListener("click", () => setInspectorOpen(!state.inspectorOpen));
elements.inspectorClose.addEventListener("click", () => setInspectorOpen(false));
elements.inspectorTabs.forEach((button) => {
  button.addEventListener("click", () => {
    setInspectorTab(button.dataset.inspectorTab);
    setInspectorOpen(true);
  });
  button.addEventListener("keydown", (event) => {
    const tabs = [...elements.inspectorTabs];
    const currentIndex = tabs.indexOf(button);
    let nextIndex = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    setInspectorTab(tabs[nextIndex].dataset.inspectorTab);
    tabs[nextIndex].focus();
  });
});
document.querySelectorAll('label[role="button"][for]').forEach((label) => {
  label.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    document.getElementById(label.htmlFor)?.click();
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!elements.layerModal.classList.contains("is-hidden")) {
    closeLayerModal();
    return;
  }
  if (state.inspectorOpen && isCompactLayout()) setInspectorOpen(false);
});
elements.parametersReset.addEventListener("click", () => applyParameters(state.parameterSchema.padrao, "padrao"));
elements.parametersExport.addEventListener("click", exportParameters);
elements.parametersImport.addEventListener("change", () => {
  const [file] = elements.parametersImport.files;
  elements.parametersImport.value = "";
  if (file) importParameters(file);
});
elements.presetSelect.addEventListener("change", () => {
  const preset = elements.presetSelect.value;
  if (preset && state.parameterSchema?.presets[preset]) applyParameters(state.parameterSchema.presets[preset], preset);
});
elements.pinReferenceButton.addEventListener("click", pinReference);
elements.restartButton.addEventListener("click", () => { stopPlayback(); selectStage(0); });
elements.previousButton.addEventListener("click", () => { stopPlayback(); selectStage(state.stageIndex - 1); });
elements.nextButton.addEventListener("click", () => { stopPlayback(); selectStage(state.stageIndex + 1); });
elements.playButton.addEventListener("click", togglePlayback);
document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
elements.layerCancelButton.addEventListener("click", closeLayerModal);
elements.layerConfirmButton.addEventListener("click", () => {
  state.layer = elements.layerSelect.value;
  closeLayerModal();
  processFile();
});
window.addEventListener("beforeunload", () => {
  if (state.sessionId) fetch(`/api/sessoes/${encodeURIComponent(state.sessionId)}`, { method: "DELETE", keepalive: true }).catch(() => {});
});
window.addEventListener("resize", refreshLayoutState);
