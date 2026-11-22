# Grafo de crafting do Minecraft

Projeto em Python para representar receitas do **Minecraft Java 1.21.1** como um
grafo dirigido, utilizando **NetworkX** para a estrutura e
**Plotly Graph Objects** para a visualização.

O objetivo é explorar dependências entre itens e fornecer uma base para análises
de algoritmos de grafos, como graus, PageRank, alcance e componentes conexas.
Essas análises e o cálculo de materiais ainda não estão implementados.

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
importantes. O gráfico apresenta os maiores valores em barras horizontais.

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
├── analytics.py          Fragilidade por recurso e comunidades (Louvain)
├── recipe\               Arquivos JSON de entrada
├── requirements.txt      Dependências
├── test_read_recipes.py  Testes do leitor e da deduplicação
├── test_analytics.py     Testes de fragilidade e comunidades
└── test_plot_graph.py    Testes da página e da abertura única
```

## Testes

```powershell
python -m unittest -v test_read_recipes test_plot_graph test_analytics
```

Os testes cobrem contagem de ingredientes, alternativas, métodos, deduplicação,
geração da página interativa e entrega por servidor de requisição única.
