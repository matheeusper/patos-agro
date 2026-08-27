# PatosAgro — Reconstrução de fileiras de plantio

O PatosAgro é um projeto independente para receber pontos georreferenciados de plantas, identificar quais pontos pertencem à mesma fileira e gerar um GeoJSON com as fileiras reconstruídas como linhas. Cada linha é classificada como `reta` ou `curva`.

## Como funciona

O processamento segue estas etapas:

1. lê os pontos, remove coordenadas duplicadas e converte os dados para UTM;
2. cria conexões entre pontos próximos com a triangulação de Delaunay;
3. estima o espaçamento entre plantas, o espaçamento entre fileiras e a direção local;
4. filtra as conexões por distância, direção e deslocamento lateral;
5. reconecta trechos compatíveis separados por falhas no plantio;
6. ajusta uma linha para cada fileira e exporta o resultado em GeoJSON.

## Organização do código

O arquivo `main.py` é o ponto de entrada da aplicação. O processamento está dividido no pacote `patos_agro`:

- `cli.py`: argumentos da linha de comando e coordenação da execução;
- `io.py`: leitura, projeção e gravação dos dados geoespaciais;
- `geometria.py`: cálculos geométricos, direções e escalas;
- `grafo.py`: construção e conexão do grafo das fileiras;
- `reconstrucao.py`: ajuste e reconstrução final das fileiras.

## Preparando o ambiente

O projeto requer Python 3. Na pasta do repositório, execute:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Ao abrir um novo terminal, ative novamente o ambiente:

```bash
source .venv/bin/activate
```

## Executando

Informe o arquivo de entrada em `--input` e o diretório de saída em `--output`:

```bash
python3 main.py --input dataset/amostra2.geojson --output resultado
```

O diretório de saída é criado automaticamente. O arquivo mantém o nome da entrada e sempre usa a extensão `.geojson`; no exemplo, a saída será `resultado/amostra2.geojson`. Ao concluir, o programa informa o caminho salvo e a quantidade de fileiras reconstruídas.

### Entrada

A entrada pode usar os formatos geoespaciais aceitos pelo GeoPandas, incluindo GeoJSON e GeoPackage. A pasta `dataset/` contém atualmente cinco amostras GeoJSON.

Antes do processamento, o programa verifica se o arquivo:

- existe e pode ser lido;
- contém somente geometrias `Point`, sem valores nulos ou vazios;
- possui um sistema de referência de coordenadas (CRS) definido;
- contém coordenadas finitas e pelo menos quatro pontos únicos;
- pode ser reprojetado para um CRS UTM.

Quando uma dessas condições não é atendida, a execução termina com uma mensagem de erro objetiva.

### Saída

A saída é um GeoJSON em `EPSG:4326`, com geometrias `LineString` e os atributos:

- `fileira_id`: identificador da fileira;
- `comprimento_m`: comprimento aproximado em metros;
- `tipo`: classificação como `reta` ou `curva`.

Um resultado existente com o mesmo nome é sobrescrito. Para proteger os dados originais, o programa bloqueia a execução caso o caminho calculado para a saída seja o próprio arquivo de entrada.

## Testes

Execute a suíte automatizada a partir da raiz do projeto:

```bash
python3 -m unittest discover -s tests -v
```

Os testes cobrem validação da entrada, comportamento da CLI, prevenção de ciclos no grafo e regressão das cinco amostras. Os GeoJSON em `tests/snapshots/` registram as saídas esperadas e também podem ser abertos no geojson.io para inspeção visual.

## Visualizando o resultado

O projeto inclui um visualizador web local. Inicie o servidor na raiz do projeto:

```bash
python3 visualizador.py
```

Depois, abra [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador. O visualizador usa uma interface de estação de campo: abertura para upload, mapa central, trilho das nove etapas e inspetor lateral com abas para etapa, camadas e ajustes. Ele permite:

- enviar arquivos GeoJSON ou GeoPackage de até 25 MB;
- escolher a camada de pontos quando um GeoPackage possuir mais de uma;
- navegar ou reproduzir automaticamente as nove etapas do algoritmo;
- ativar e desativar camadas pela legenda;
- comparar os pontos originais e qualquer etapa em mapas sincronizados;
- ajustar parâmetros básicos e avançados com recálculo automático após 500 ms;
- aplicar presets, restaurar padrões e importar ou exportar configurações JSON;
- fixar um resultado como referência e comparar suas métricas e geometrias com o resultado atual;
- baixar o GeoJSON final sem manter o upload no servidor.

O logotipo completo, a marca compacta e o favicon do PatosAgro ficam em `patos_agro/static/brand/`. A interface usa uma identidade monocromática em preto, branco e cinzas; as cores são mantidas somente nas camadas técnicas do mapa para diferenciar diagnósticos. As fontes Barlow Condensed, Atkinson Hyperlegible e IBM Plex Mono são carregadas localmente a partir de `patos_agro/static/fonts/`, junto com suas licenças OFL, para que a identidade visual continue funcionando sem internet.

Os arquivos enviados são processados em uma pasta temporária e removidos ao final da requisição. Para permitir novos cálculos sem reenviar o arquivo, somente as coordenadas projetadas e seus metadados ficam em memória por até 30 minutos. O servidor mantém no máximo três sessões locais e permite encerrá-las pelo navegador. Ele escuta apenas em `127.0.0.1`, portanto não fica disponível para outros computadores da rede.

As configurações exportadas usam o formato `{ "versao": 1, "parametros": {...} }`. Campos desconhecidos e valores não finitos ou fora dos limites são rejeitados com uma mensagem clara. As preferências de parâmetros, tema e mapa-base são guardadas apenas no `localStorage` do navegador.

Na conexão de falhas longas em fileiras curvas, o algoritmo testa pontes cúbicas de Bézier alinhadas às tangentes dos fragmentos. Uma ponte só é aceita quando não fecha ciclos, não se cruza e mantém o corredor configurado em relação às fileiras vizinhas. Os pontos amostrados da ponte participam do ajuste final da spline.

O Leaflet é carregado a partir dos arquivos incluídos no projeto, então pontos, linhas e controles continuam funcionando sem internet. O seletor global permite usar ruas do OpenStreetMap, satélite Sentinel-2, satélite com rótulos, imagens aéreas abertas, terreno, mapa escuro ou fundo neutro. A escolha e o estado ativado/desativado ficam salvos separadamente no navegador e valem para os três mapas.

As camadas Sentinel-2, híbrida e topográfica são fornecidas pela EOX para uso não comercial. Elas possuem resolução aproximada de 10 m e servem principalmente como contexto territorial. O modo aéreo usa o OpenAerialMap a partir do zoom 14, mantendo o OpenStreetMap por baixo porque a cobertura de imagens varia conforme a região. Todos os mapas-base dependem de internet; quando um provedor falha, as geometrias continuam disponíveis sobre o mapa de ruas ou o fundo neutro.

## Valores heurísticos

O algoritmo utiliza alguns valores práticos para decidir quais pontos podem formar uma fileira. Esses valores foram avaliados com as cinco amostras disponíveis e acompanham o espaçamento estimado entre as plantas:

- `0.55` e `1.8 × espacamento_plantas` ajudam a selecionar vizinhos próximos para estimar a direção das fileiras;
- `0.75` ajuda a identificar conexões transversais e evita espaçamentos entre fileiras muito pequenos;
- `2.6 × espacamento_plantas` e `32°` limitam as conexões iniciais;
- `40°` limita o desalinhamento ao unir fragmentos;
- `18 × espacamento_plantas` e `55°` são os limites padrão para lacunas curvas; as conexões simples mantêm os limites anteriores;
- `0.35 × espacamento_fileiras` é o corredor mínimo padrão das pontes curvas em relação a pontos e segmentos vizinhos.

Esses valores não são regras agronômicas universais. Dados com outro espaçamento, nível de ruído ou padrão de plantio podem exigir novos ajustes.
