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

O terminal informa o número de nós, arestas, arquivos de receitas carregados,
variantes e receitas ignoradas. Cada entrada ignorada é listada com seu motivo.

## Modelo do grafo

O projeto utiliza um `networkx.DiGraph`, com arestas na direção:

```text
ingrediente → produto
```

Existem três tipos de nós:

- **Item específico:** por exemplo, `minecraft:stick`.
- **Tag genérica:** por exemplo, `minecraft:planks(any)`.
- **Receita não resolvida:** placeholder isolado, como
  `unresolved_recipe:minecraft:repair_item`.

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

Tipos não suportados, como receitas especiais e `smithing_trim`, geram apenas
placeholders isolados, sem inventar ingredientes ou resultados.

## Visualização

O layout de forças é calculado uma vez no Python, com semente fixa. O grafo
completo permanece visível e os nós não têm física, animação ou arraste individual.

- **Azul:** itens específicos.
- **Amarelo:** tags `(any)`.
- **Vermelho:** receitas não resolvidas.
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

## Limitações

- Tags `(any)` não são expandidas nem conectadas aos itens específicos que aceitam.
  Isso pode interromper cadeias de dependência.
- Caminhos no grafo não equivalem a planos completos de fabricação: uma receita
  pode exigir vários ingredientes ao mesmo tempo.
- Combustíveis, tempo, experiência, componentes de itens e sobras de recipientes
  não são modelados.
- Expandir listas de alternativas pode gerar muitas variantes de uma receita.
- Placeholders isolados devem ser tratados separadamente em análises de itens.
- O grafo fica em memória; não há exportação persistente dos dados no fluxo atual.

## Estrutura

```text
graph
├── read_recipes.py       Leitura, normalização e construção do grafo
├── plot_graph.py         Figura Plotly e interações no navegador
├── recipe\               Arquivos JSON de entrada
├── requirements.txt      Dependências
├── test_read_recipes.py  Testes do leitor e da deduplicação
└── test_plot_graph.py    Testes da página e da abertura única
```

## Testes

```powershell
python -m unittest -v test_read_recipes test_plot_graph
```

Os testes cobrem contagem de ingredientes, alternativas, métodos, deduplicação,
geração da página interativa e entrega por servidor de requisição única.
