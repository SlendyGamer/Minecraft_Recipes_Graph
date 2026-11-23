# Grafo de crafting do Minecraft

Projeto em Python para representar receitas do **Minecraft Java 1.21.1** como um
grafo dirigido, utilizando **NetworkX** para a estrutura e
**Plotly Graph Objects** para a visualização.

O objetivo é explorar dependências entre itens e fornecer uma base para análises
de algoritmos de grafos, como graus, PageRank, centralidade, comunidades e
fragilidade. O cálculo de materiais ainda não está implementado.

## Instalação

Recomendado: Python 3.12 e um navegador moderno com suporte a WebGL.

No PowerShell, a partir da pasta do projeto:

```powershell
python -m pip install -r .\requirements.txt
```

Use o mesmo interpretador para instalar as dependências e executar o projeto.
Se executar por uma IDE, selecione nela o mesmo ambiente Python.

## Dados de entrada

O leitor espera uma pasta com os arquivos JSON de receitas da versão 1.21.1.
Na instalação atual, essa pasta se chama `recipe` e fica ao lado do script.

Para obter os arquivos a partir do jogo:

1. Localize o JAR do cliente Minecraft Java 1.21.1 no seu launcher.
2. Abra o JAR como um arquivo ZIP, por exemplo, com 7-Zip.
3. Extraia o conteúdo de `data\minecraft\recipe` para a pasta `recipe` do projeto.

Não é necessário modificar o JAR nem extrair a pasta de tags: referências a tags
são preservadas como nós genéricos `(any)`.

O leitor atual usa o namespace `minecraft` nos identificadores das receitas.
Outras versões e receitas de mods não têm compatibilidade garantida.

## Execução

Ler as receitas e abrir a visualização:

```powershell
python .\read_recipes.py
```

Ler e imprimir as estatísticas sem abrir o navegador:

```powershell
python .\read_recipes.py --no-plot
```

Usar outra pasta de receitas:

```powershell
python .\read_recipes.py "C:\dados\minecraft\recipe" --no-plot
```

Abrir todos os gráficos em páginas separadas:

```powershell
python .\read_recipes.py --all-graphs
```

Abrir uma análise específica:

```powershell
python .\read_recipes.py --degree       # distribuição linear de graus
python .\read_recipes.py --degree-log   # distribuição log-log de graus
python .\read_recipes.py --clustering   # distribuição do clustering
python .\read_recipes.py --pagerank     # ranking dos principais nós
python .\read_recipes.py --fragility    # impacto da ausência de recursos
python .\read_recipes.py --communities  # comunidades e itens-ponte
python .\read_recipes.py --centrality   # betweenness e closeness
python .\read_recipes.py --questions    # difusão, preservação, robustez e navegação
```

Adicionar `--no-plot` quando as análises devem ser feitas apenas no terminal,
por exemplo `python .\read_recipes.py --all-graphs --no-plot`.

O terminal informa o número de nós, arestas, arquivos de receitas carregados,
variantes e receitas ignoradas. Cada entrada ignorada é listada com seu motivo.

## Modelo do grafo

O projeto utiliza um `networkx.DiGraph`, com arestas na direção:

```text
ingrediente → produto
```

Existem dois tipos de nós:

- **Item específico:** por exemplo, `minecraft:stick`.
- **Tag genérica:** por exemplo, `minecraft:planks(any)`.

Há uma única aresta por par ingrediente/produto. Cada aresta contém uma lista
`recipes`, permitindo representar diferentes receitas entre os mesmos itens:

```python
{
    "recipes": [
        {
            "recipe_id": "minecraft:stick",
            "input": 2,
            "output": 4,
            "crafting_method": "shaped"
        }
    ]
}
```

Nesse exemplo, a aresta `minecraft:planks(any) → minecraft:stick` representa o
consumo de duas tábuas para produzir quatro gravetos por execução da receita.

O identificador da receita é derivado do caminho do JSON. Alternativas explícitas,
como carvão ou carvão vegetal para tochas, são expandidas em variantes com sufixos
`#alternative_1`, `#alternative_2` etc. Combinações equivalentes dentro de uma
receita são consolidadas.

### Métodos suportados

| Tipo no JSON | `crafting_method` no grafo |
|---|---|
| `crafting_shaped` | `shaped` |
| `crafting_shapeless` | `shaped` |
| `smelting` | `furnace` |
| `blasting` | `blast_furnace` |
| `smoking` | `smoker` |
| `campfire_cooking` | `campfire` |
| `stonecutting` | `stonecutter` |
| `smithing_transform` | `smithing_table` |

Para receitas shaped, o leitor conta as ocorrências dos símbolos de `pattern`,
ignorando espaços e consultando `key`. Para shapeless, conta os ingredientes.
Ambas recebem o método `shaped`, pois a disposição na bancada não é representada.

Receitas com os mesmos ingredientes e quantidades, produto, quantidade produzida
e estação são deduplicadas, independentemente da disposição. Shaped e shapeless
compartilham a mesma estação para essa comparação. A primeira variante encontrada
é mantida; as seguintes entram no contador e na lista de ignorados.

Tipos não suportados, como receitas especiais e `smithing_trim`, são ignorados:
não geram nós, arestas nem entram nos contadores.

## Visualização

O layout de forças é calculado uma vez no Python, com semente fixa. O grafo
completo permanece visível e os nós não têm física, animação ou arraste individual.

- **Azul:** itens específicos.
- **Amarelo:** tags `(any)`.
- **Hover em um nó:** destaca seus vizinhos diretos e esmaece o restante.
- **Clique em um nó:** colore por `recipe_id` as receitas que produzem aquele item.
- **Hover nas conexões:** permite consultar métodos e quantidades.
- **Limpar selecao:** remove o destaque fixado pelo clique.

As receitas do item selecionado recebem cores distintas entre si. Conexões
compartilhadas são separadas por curvas com pontas nos itens. Zoom e navegação
pela tela continuam disponíveis.

A abertura usa um servidor local temporário que atende uma única requisição.
Depois de entregar a página, o Python pode encerrar: as interações rodam em
JavaScript no navegador, sem Dash e sem servidor permanente. O Plotly é embutido
na página, sem necessidade de CDN.

**F5 não reabre a figura:** o servidor já encerrou. Execute o script novamente
para abrir outra visualização. Nenhum arquivo HTML é salvo pelo fluxo padrão.

O código de interação e abertura está delimitado por `# JsBegin` e `# JsEnd`.

## Uso com NetworkX

```python
from pathlib import Path

from read_recipes import build_graph

graph = build_graph(Path("recipe"))

print(graph.number_of_nodes())
print(graph.number_of_edges())
print(graph["minecraft:planks(any)"]["minecraft:stick"]["recipes"])

most_used = sorted(graph.out_degree, key=lambda pair: pair[1], reverse=True)
print(most_used[:10])
```

O grau de saída conta **produtos distintos**, não o número de receitas. Já o
grau de entrada inclui todos os ingredientes possíveis, inclusive alternativas:
não significa que todos sejam obrigatórios simultaneamente.

## Distribuição de grau, clustering e PageRank

### Distribuição de grau

O gráfico linear mostra quantos nós possuem cada grau de entrada ou saída.
O gráfico log-log conserva apenas graus maiores que zero e ajuda a examinar a
cauda da distribuição. Uma aparência aproximada de reta é apenas uma pista; ela
não prova por si só que o grafo seja livre de escala.

### Clustering local

O clustering local mede quanto os vizinhos de um nó estão conectados entre si.
Como o grafo é dirigido, ele é calculado na projeção não dirigida. Um coeficiente
próximo de 1 indica uma vizinhança bastante fechada, enquanto 0 indica que os
vizinhos não formam arestas entre si. O gráfico compara a quantidade de nós em
cada faixa do coeficiente.

### PageRank

O PageRank mede influência estrutural no grafo dirigido. Ao longo das arestas
`ingrediente → produto`, um nó recebe influência dos itens que apontam para ele
e de nós apontadores que já têm importância própria.

PageRank não é apenas o número de entradas. Ele responde quais nós ocupam posições
mais influentes no fluxo do grafo e pode ser usado para ranquear os vértices mais
importantes. O gráfico apresenta os maiores valores em barras horizontais, nos dois
sentidos das arestas (normal e reverso, detalhados na seção "PageRank nos dois sentidos").

```powershell
python .\read_recipes.py --degree
python .\read_recipes.py --degree-log
python .\read_recipes.py --clustering
python .\read_recipes.py --pagerank
```

## Análise de fragilidade por recurso

`analytics.py` responde: *se um recurso base deixar de existir, quantos itens
deixam de ser fabricáveis?*

```powershell
python .\read_recipes.py --fragility          # imprime a tabela e abre o gráfico
python .\read_recipes.py --fragility --no-plot
```

No gráfico, clicar em uma barra mostra no painel lateral a lista completa dos
itens que deixam de ser fabricáveis sem aquele recurso.

Método: as receitas são reconstruídas pelo `recipe_id` das arestas (todos os
ingredientes são necessários ao mesmo tempo, ao contrário de um caminho no grafo).
Parte-se dos recursos base, repetem-se as receitas possíveis até estabilizar e
remove-se um recurso por vez. Recursos base são os grupos sem entrada externa na
condensação do grafo, então ciclos como bruto ⇄ bloco bruto contam como um só.
Tags `(any)` são tratadas como sempre disponíveis. Itens inalcançáveis mesmo com
todos os recursos (modelos de armadura, netherite, mel) formam a linha de base
e não entram na contagem de perdas.

O modelo ignora Nether, End, saque e progressão: mede apenas dependência entre receitas.

## Comunidades e itens-ponte

`analytics.py` também responde: *o grafo separa os itens em famílias, e quais
itens ligam uma família à outra?*

```powershell
python .\read_recipes.py --communities          # imprime a tabela e abre a figura
python .\read_recipes.py --communities --no-plot
```

Método: Louvain (semente fixa) no grafo não dirigido, sem placeholders e sem
laços. Cada comunidade é descrita pelos itens de maior grau. Item-ponte é um item
com vizinhos em outras comunidades; o número é quantas comunidades distintas ele toca.

A modularidade é comparada com um modelo nulo (mesmos graus, ligações sorteadas,
média de 5 amostras). Em grafos esparsos o modelo nulo já tem modularidade alta
(≈ 0,54 contra ≈ 0,78 no grafo real), então apenas a diferença indica famílias de
itens. Arestas múltiplas do modelo nulo são colapsadas.

Na figura, as 12 maiores comunidades têm cor própria, as demais ficam em cinza e
os itens-ponte são circulados com o número de comunidades vizinhas.
Como as tags `(any)` não são ligadas aos itens que representam, a comunidade
de `planks(any)` e das camas reflete essa limitação do modelo.

## Comparação com grafos sintéticos

`compare_synthetic.py` compara o grafo de receitas com três modelos equivalentes
(mesmo número de nós e aproximadamente de arestas): **ER** (aleatório),
**BA** (livre de escala) e **Watts-Strogatz** (small world).

```powershell
python .\compare_synthetic.py                 # tabela, CSV e gráficos em .\figures_synthetic
python .\compare_synthetic.py --samples 30    # mais sorteios por modelo
python .\compare_synthetic.py --ws-p 0.05     # outra probabilidade de religação
python .\compare_synthetic.py --no-plot       # só a tabela
```

Método: os modelos são não dirigidos, então o grafo é convertido para não dirigido
e sem laços. Caminho médio e diâmetro exigem grafo conexo, por isso real e sintéticos
são comparados na **maior componente conexa**. Cada modelo é sorteado várias vezes
(semente fixa) e reportam-se média e desvio padrão. Parâmetros: ER com as mesmas
arestas; BA com `round(m/n)` arestas por nó novo; WS com `k = 2·round(m/n)`.

Métricas: grau médio e máximo, clustering, transitividade, caminho médio, diâmetro,
assortatividade, distância KS entre as distribuições de grau e o índice small world
σ = (C/C_ER)/(L/L_ER). Gráficos gerados: CCDF do grau (log-log), barras das métricas
e o mapa C/C_ER × L/L_ER.

## PageRank nos dois sentidos

`analytics.py` também responde: *quais itens concentram mais importância nas
cadeias de receitas?*

```powershell
python .\read_recipes.py --pagerank          # imprime os rankings e abre o gráfico
python .\read_recipes.py --pagerank --no-plot
```

O gráfico mostra, lado a lado, os maiores valores do PageRank normal e do reverso.

O PageRank (α = 0,85) é calculado duas vezes, sobre as arestas `ingrediente → produto`:

- **Normal:** a importância flui dos ingredientes para os produtos. Destaca itens
  no fim de cadeias de dependência (nuggets, esmeralda, camas e tapetes).
- **Reverso** (grafo invertido, produto → ingrediente): destaca os recursos dos quais
  muitos itens dependem (`stick`, `planks(any)`, `iron_ingot`). É o mais indicado
  para apontar os itens mais importantes.

Ciclos de conversão (nugget ⇄ lingote, bruto ⇄ bloco bruto) inflam alguns valores,
como `raw_iron` e `emerald`. A tabela mostra também os graus de entrada e saída.

## Betweenness e closeness

`analytics.py` também responde: *quais itens ficam no meio dos caminhos e quais
ficam mais perto de todos os outros?*

```powershell
python .\read_recipes.py --centrality          # imprime os rankings e abre o gráfico
python .\read_recipes.py --centrality --no-plot
```

Método: caminhos mínimos só existem entre nós conectados, então o cálculo usa o
**maior componente** do grafo não dirigido, sem laços (o mesmo `analysis_graph`
das comunidades). Na versão 1.21.1 são 938 dos 1013 nós. Tags `(any)` ficam no grafo.
Betweenness e closeness são as normalizadas do NetworkX.

O terminal imprime os 15 maiores de cada métrica e um **perfil dos candidatos**
(por padrão, os 6 maiores do PageRank reverso) com grau, PageRank reverso,
betweenness, closeness e número de comunidades vizinhas (item-ponte). Para itens
específicos, passe `candidates=("minecraft:diamond", ...)` a `centrality_report`;
`candidate_count` muda a quantidade do padrão.

Leitura: a closeness só é informativa nas primeiras posições, pois depois delas lidera
quem está no meio de grupos densos (camas, ferramentas de diamante). Em um grafo
dirigido quase acíclico, a betweenness dirigida fica muito pequena e favorece
conversões curtas (corantes, nuggets), por isso não é usada aqui.

## Vértices mais importantes

Escolha do grupo: **`stick`, `planks(any)` e `iron_ingot`**. Como `planks(any)` é um
conjunto de itens (uma tag), e não um item, se ele for desconsiderado o top 3 passa a
ser **`stick`, `iron_ingot` e `cobblestone`**.

| Item | Grau de saída | PageRank reverso | Betweenness | Closeness | Comunidades vizinhas | Itens perdidos sem ele |
|---|---|---|---|---|---|---|
| `stick` | 94 | 0,01659 | 0,440 | 0,275 | 9 | 105 (10,7%) |
| `planks(any)` | 39 | 0,01460 | 0,225 | 0,277 | 8 | 59 (6,0%) |
| `iron_ingot` | 35 | 0,01241 | 0,122 | 0,219 | 4 | 53 (5,4%) |
| `cobblestone` | 15 | 0,01011 | 0,071 | 0,225 | 3 | 60 (6,1%) |

"Itens perdidos" são os itens que deixam de ser fabricáveis (de 983) se o item e a
receita que o produz forem removidos, usando `craftable_items`, o mesmo ponto fixo da
fragilidade. Os demais valores vêm de `--pagerank` e `--centrality`.

**Critério:** o número de itens perdidos não decide sozinho; pesa o quanto cada item
perdido é essencial para progredir. O `string` perde 90 itens, o segundo maior valor do
grafo, mas 64 deles são variantes de cor (16 de lã, cama, tapete e bandeira) e outros 17
são velas. Ele não sustenta nada indispensável, por isso não entra no top 3.

**`stick`:** é a base de todas as ferramentas (picaretas, pás, machados, enxadas e
espadas), de armas como arco, besta e flecha, e de muitos itens de construção usados em
abundância: cercas, portões, placas e bandeiras. Lidera em quase todas as métricas:
maior grau (94 itens dependem dele), maior betweenness (44% dos caminhos mais curtos
passam por ele), maior PageRank reverso e a maior perda (105 itens). Liga 9
comunidades, então é o item que mais conecta as famílias do grafo.

**`planks(any)`:** concentra a madeira. Tem a maior closeness (0,277), ou seja, é o nó
mais próximo de todos os outros, e a segunda maior betweenness e PageRank reverso. Um
detalhe de modelagem: as tags `(any)` são tratadas como sempre disponíveis na análise de
fragilidade, então o valor de 59 itens perdidos remove a tag de propósito, para medir sua
influência. Por ser um conjunto de itens, ele é a exceção do top 3 alternativo.

**`iron_ingot`:** é o principal material intermediário: 35 itens dependem dele, entre
ferramentas e armaduras de ferro, trilhos, balde, funil, tesoura, bússola, êmbolo e
bigorna. Tem o terceiro maior PageRank reverso e 4 comunidades vizinhas. Sem ele, o
jogador fica sem a picareta de ferro, a única capaz de minerar o primeiro diamante: as
picaretas de diamante e de netherita exigem diamante para serem fabricadas (regra do
jogo, fora do grafo, já que o modelo não representa a ferramenta exigida para minerar).
Sem diamante, e sem fontes externas como saque, o progresso trava no início do jogo:
nada de ferramentas de diamante nem de netherita. Também deixam de existir o balde, a
tesoura, o funil, a bigorna e a mesa de ferraria. Sua fonte é redundante (minério,
minério de deepslate, `raw_iron` e blocos), por isso remover o `raw_iron` não faz
perder nenhum item na fragilidade (0). Já faltar o lingote em si custa 53 itens: o item
é essencial, mas o suprimento é robusto.

**`cobblestone`:** é o segundo recurso base mais frágil (60 itens perdidos, atrás apenas
de `string`, com 90). Sem ele deixam de ser fabricáveis as pedras e tijolos de pedra, os
degraus, lajes e muros, o granito, o diorito e o andesito (inclusive polidos) e o
`stonecutter`. Perdem-se também os itens de redstone, como êmbolo, êmbolo pegajoso,
observador, dispensador, liberador, repetidor, comparador, alavanca, botão de pedra,
placa de pressão e trilho detector. O `blast_furnace`, o `grindstone` e o `lodestone`
também deixam de ser fabricáveis. O forno comum **não** é afetado no modelo, pois a
receita dele usa a tag `stone_crafting_materials(any)`, tratada como sempre disponível.
Por ser recurso base, perde para o `iron_ingot` em centralidade (grau 15, betweenness
0,071) e em importância dos itens que sustenta: o `cobblestone` bloqueia construção e
redstone, mas não impede o jogador de avançar, enquanto a falta de ferro o corta da
mineração de diamante. Por isso fica em terceiro, mesmo perdendo mais itens (60 contra
53).

Ressalvas: o PageRank reverso de `raw_iron` (0,00985) e `emerald` é inflado pelos ciclos
de conversão bruto ⇄ bloco, por isso não entram no top 3. A betweenness dirigida,
muito baixa em um grafo quase acíclico, destaca conversões curtas (corantes e nuggets)
e também não foi usada.

## Perguntas finais

```powershell
python .\read_recipes.py --questions            # imprime as respostas e abre o gráfico de robustez
python .\read_recipes.py --questions --no-plot
```

Todas as medidas usam o maior componente do grafo não dirigido (938 nós, o mesmo
`analysis_graph`). Os sorteios usam semente fixa (1), então o resultado se repete.

**Robustez: alta contra falhas aleatórias, baixa contra ataques a hubs.** Removendo nós
e acompanhando o maior componente restante, o grafo só cai abaixo de 50% depois de
**45,9%** dos nós sorteados serem removidos (média de 20 execuções). Removendo os hubs
(maior grau primeiro), isso acontece com apenas **8,0%** (com 10% removido, o componente
tem 28,2% dos nós restantes contra 90,7% no caso aleatório). A rede suporta falhas
aleatórias, mas depende de poucos nós, como `stick` e `planks(any)`.

**Difusão: fácil.** O caminho médio é **L = 6,00** com diâmetro 17 e grau médio 3,92.
Como `ln N = 6,84`, L fica abaixo de `ln N`, então qualquer item alcança outro em cerca
de 6 passos. A informação se espalha rápido, mas passa pelos hubs (SIR não foi simulado).

**Preservação: moderada.** Só **22,9%** dos itens fabricáveis (192 de 837) têm receita
alternativa, contando como alternativa apenas um conjunto de ingredientes diferente; trocar
a estação (forno × alto-forno) não conta. O **k-core máximo é 16** (49 nós), mas é um
artefato: reúne as 16 cores de lã, cama e tapete (que compartilham os mesmos corantes) e
`planks(any)`. Não indica redundância real do restante do grafo.

**Navegação: difícil só com informação local.** Na busca gulosa por grau (vai ao
vizinho ainda não visitado de maior grau, sem retrocesso), **17,1%** dos 1000 pares
sorteados chegam ao destino. Nos que chegam, são 15,2 passos em média contra 4,4 do
caminho mínimo (alongamento de **3,13x**). O caminho curto existe, mas achá-lo exige
conhecer o grafo; ir sempre ao maior grau leva a becos sem saída.

## Limitações

- Tags `(any)` não são expandidas nem conectadas aos itens específicos que aceitam.
  Isso pode interromper cadeias de dependência.
- Caminhos no grafo não equivalem a planos completos de fabricação: uma receita
  pode exigir vários ingredientes ao mesmo tempo.
- Combustíveis, tempo, experiência, componentes de itens e sobras de recipientes
  não são modelados.
- Expandir listas de alternativas pode gerar muitas variantes de uma receita.
- Receitas especiais e `smithing_trim` não são modeladas.
- O grafo fica em memória; não há exportação persistente dos dados no fluxo atual.

## Estrutura

```text
graph
├── read_recipes.py       Leitura, normalização e construção do grafo
├── plot_graph.py         Figura Plotly e interações no navegador
├── analytics.py          Fragilidade, comunidades (Louvain), PageRank, centralidade e perguntas finais
├── compare_synthetic.py  Comparação com ER, BA e Watts-Strogatz
├── figures_synthetic\    Gráficos e CSV gerados pela comparação sintética
├── recipe\               Arquivos JSON de entrada
└── requirements.txt      Dependências
```
