import argparse
import json
from collections import Counter
from itertools import product
from pathlib import Path

import networkx as nx


# Dicionario para mapear as estações de crafting suportadas pelo código
CRAFTING_METHODS = {
    "minecraft:crafting_shaped": "shaped",
    "minecraft:crafting_shapeless": "shaped",
    "minecraft:smelting": "furnace",
    "minecraft:blasting": "blast_furnace",
    "minecraft:smoking": "smoker",
    "minecraft:campfire_cooking": "campfire",
    "minecraft:stonecutting": "stonecutter",
    "minecraft:smithing_transform": "smithing_table",
}


# Retorna se o crafting pede por um item específico ou uma "tag" de item
# Ex: Plank(any) -> qualquer material com tag plank
def ingredient_options(ingredient):
    if isinstance(ingredient, list):
        return tuple(dict.fromkeys(
            node
            for alternative in ingredient
            for node in ingredient_options(alternative)
        ))
    if "item" in ingredient:
        return (ingredient["item"],)
    if "tag" in ingredient:
        return (f"{ingredient['tag']}(any)",)
    raise ValueError(f"Unsupported ingredient: {ingredient!r}")


# Faz a tratativa para "normalizar" as arestas para métodos diferentes de crafting
# Ex: Shaped (Crafting Table) conta a quantidade de items na pattern (espaço 3x3 da mesa)
def recipe_inputs(recipe):
    if recipe["type"] == "minecraft:crafting_shaped":
        ingredients = [
            recipe["key"][symbol]
            for row in recipe["pattern"]
            for symbol in row
            if symbol != " "
        ]
    elif recipe["type"] == "minecraft:crafting_shapeless":
        ingredients = recipe["ingredients"]
    elif recipe["type"] == "minecraft:smithing_transform":
        ingredients = [recipe[key] for key in ("template", "base", "addition")]
    else:
        ingredients = [recipe["ingredient"]]

    # Trata casos onde variantes existem para um mesmo crafting e não são classificadas por tags
    # Ex: Coal e Charcoal para fazer uma tocha
    variants = {}
    for combination in product(*(ingredient_options(item) for item in ingredients)):
        counts = Counter(combination)
        signature = tuple(sorted(counts.items()))
        variants.setdefault(signature, counts)
    return list(variants.values())


# Percorre a pasta do jogo e le cada Json, fazendo a interpretação de cada arquivo de crafting em /recipe
def build_graph(recipe_directory):
    recipe_directory = Path(recipe_directory)
    if not recipe_directory.is_dir():
        raise ValueError(f"Recipe directory does not exist: {recipe_directory}")

    graph = nx.DiGraph()
    files = sorted(recipe_directory.rglob("*.json"))
    if not files:
        raise ValueError(f"No JSON recipes found in: {recipe_directory}")

    # Contadores para logs
    crafting_count = 0
    variant_count = 0
    skipped_count = 0
    ignored_recipes = []
    seen_recipes = {}
    duplicate_count = 0

    # além de abrir cada arquivo, salva o nome dele, já que ele representa o resultado do craft
    for path in files:
        with path.open(encoding="utf-8") as source:
            recipe = json.load(source)
        recipe_id = "minecraft:" + path.relative_to(recipe_directory).with_suffix("").as_posix()
        crafting_method = CRAFTING_METHODS.get(recipe.get("type"))
        # Tipos sem suporte (receitas especiais, smithing_trim...) não entram no grafo.
        if crafting_method is None:
            continue

        output_item = recipe["result"]["id"]
        output_count = recipe["result"].get("count", 1)
        variants = recipe_inputs(recipe)
        graph.add_node(output_item)

        loaded_variants = 0
        for index, inputs in enumerate(variants, start=1):
            variant_id = (
                recipe_id if len(variants) == 1
                else f"{recipe_id}#alternative_{index}"
            )
            station = (
                "crafting_table" if crafting_method in {"shaped", "shapeless"}
                else crafting_method
            )
            signature = (
                station, output_item, output_count, tuple(sorted(inputs.items())),
            )
            if signature in seen_recipes:
                ignored_recipes.append({
                    "recipe_id": variant_id,
                    "crafting_method": crafting_method,
                    "duplicate_of": seen_recipes[signature],
                })
                skipped_count += 1
                duplicate_count += 1
                continue
            seen_recipes[signature] = variant_id
            loaded_variants += 1
            for input_item, input_count in inputs.items():
                if not graph.has_edge(input_item, output_item):
                    graph.add_edge(input_item, output_item, recipes=[])
                graph[input_item][output_item]["recipes"].append({
                    "recipe_id": variant_id,
                    "input": input_count,
                    "output": output_count,
                    "crafting_method": crafting_method,
                })

        crafting_count += bool(loaded_variants)
        variant_count += loaded_variants

    graph.graph.update(
        crafting_recipes=crafting_count,
        recipe_variants=variant_count,
        skipped_recipes=skipped_count,
        ignored_recipes=ignored_recipes,
        duplicate_recipes=duplicate_count,
    )
    return graph

# Função main, responsável pela lógica geral de chamadas as funções e representação gráfica
# Permite também apenas fazer a leitura das receitas, sem plotar o grafo
def main():
    parser = argparse.ArgumentParser(
        description="Read Minecraft Java 1.21.1 crafting recipes into a directed graph."
    )
    parser.add_argument(
        "recipe_directory",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "recipe",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Read recipes without opening the Plotly visualization.",
    )
    parser.add_argument(
        "--fragility",
        action="store_true",
        help="Print which items stop being craftable without each base resource.",
    )
    parser.add_argument(
        "--communities",
        action="store_true",
        help="Detect item families (Louvain) and the items that bridge them.",
    )
    parser.add_argument(
        "--pagerank",
        action="store_true",
        help="Rank items by PageRank in both edge directions.",
    )
    parser.add_argument(
        "--centrality",
        action="store_true",
        help="Rank items by betweenness and closeness in the largest component.",
    )
    parser.add_argument(
        "--questions",
        action="store_true",
        help="Answer diffusion, preservation, robustness and navigation questions.",
    )
    args = parser.parse_args()
    graph = build_graph(args.recipe_directory)
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Loaded recipes: {graph.graph['crafting_recipes']}")
    print(f"Recipe variants: {graph.graph['recipe_variants']}")
    print(f"Ignored recipes/variants: {graph.graph['skipped_recipes']}")
    print(f"Duplicates: {graph.graph['duplicate_recipes']}")
    for recipe in graph.graph["ignored_recipes"]:
        reason = f"duplicate of {recipe['duplicate_of']}"
        print(f"Ignored: {recipe['recipe_id']} ({recipe['crafting_method']}; {reason})")
    if args.fragility:
        from analytics import resource_fragility, short_name

        result = resource_fragility(graph)
        print(f"Craftable with all base resources: {len(result['baseline'])}")
        print(f"Unreachable (loot-only or unsourced cycles): {len(result['unreachable'])}")
        print("Items lost without each resource:")
        for row in result["by_resource"][:15]:
            print(f"  {short_name(row['name'])}: {len(row['lost'])}")
        if not args.no_plot:
            from plot_graph import show_fragility

            show_fragility(result)
    if args.communities:
        from analytics import detect_communities, short_name

        result = detect_communities(graph)
        print(
            f"Communities: {len(result['communities'])}; "
            f"modularity {result['modularity']:.3f} "
            f"(null model {result['null_modularity']:.3f})"
        )
        for community in result["communities"][:15]:
            names = ", ".join(short_name(node) for node in community["top"])
            print(f"  #{community['id']} ({community['size']}): {names}")
        print("Bridge items (neighbouring communities):")
        for row in result["bridges"][:10]:
            print(f"  {short_name(row['name'])}: {row['touches']}")
        if not args.no_plot:
            from plot_graph import show_communities

            show_communities(graph, result)
    if args.pagerank:
        from analytics import pagerank_rankings, short_name

        result = pagerank_rankings(graph)
        for key, title in (
            ("normal", "PageRank normal (ingrediente -> produto)"),
            ("reverse", "PageRank reverso (produto -> ingrediente)"),
        ):
            print(title)
            for row in result[key]:
                print(
                    f"  {row['score']:.5f}  {short_name(row['name'])}"
                    f" (in={row['in_degree']}, out={row['out_degree']})"
                )
        if not args.no_plot:
            from plot_graph import show_pagerank

            show_pagerank(result)
    if args.centrality:
        from analytics import centrality_report, short_name

        result = centrality_report(graph)
        print(f"Largest component: {result['component_size']} of {result['node_count']} nodes")
        for key, title in (("betweenness", "Betweenness"), ("closeness", "Closeness")):
            print(title)
            for row in result[key]:
                print(
                    f"  {row['score']:.5f}  {short_name(row['name'])}"
                    f" (degree={row['degree']})"
                )
        print("Candidates (degree, PageRank reverse, betweenness, closeness, bridge):")
        for row in result["profile"]:
            values = [
                "-" if row[key] is None else f"{row[key]:.5f}"
                for key in ("pagerank_reverse", "betweenness", "closeness")
            ]
            print(
                f"  {short_name(row['name'])}: degree={row['degree']}, "
                f"pagerank={values[0]}, betweenness={values[1]}, "
                f"closeness={values[2]}, bridge={row['bridge_touches']}"
            )
        if not args.no_plot:
            from plot_graph import show_centrality

            show_centrality(result)
    if args.questions:
        from analytics import (
            diffusion_report, navigation_report, preservation_report,
            robustness_report, short_name,
        )

        diffusion = diffusion_report(graph)
        print("Difusão (maior componente):")
        print(f"  Nós: {diffusion['nodes']}; grau médio: {diffusion['mean_degree']:.2f}")
        print(
            f"  Caminho médio L: {diffusion['average_path']:.2f} "
            f"(ln N = {diffusion['log_nodes']:.2f}); diâmetro: {diffusion['diameter']}"
        )
        preservation = preservation_report(graph)
        share = 100 * preservation["with_alternative"] / preservation["crafted_items"]
        core = [short_name(node) for node in preservation["core_nodes"]]
        print("Preservação:")
        print(
            f"  Itens com receita alternativa: {preservation['with_alternative']} "
            f"de {preservation['crafted_items']} ({share:.1f}%)"
        )
        print(
            f"  k-core máximo: {preservation['max_core']} "
            f"({len(core)} nós: {', '.join(core[:8])}, ...)"
        )
        robustness = robustness_report(graph)
        print("Robustez (maior componente cai abaixo de 50%):")
        for key, title in (("threshold_random", "aleatória"), ("threshold_targeted", "hubs")):
            value = robustness[key]
            result_text = "não cai até 50% removido" if value is None else f"{100 * value:.1f}% removido"
            print(f"  Remoção {title}: {result_text}")
        navigation = navigation_report(graph)
        print("Navegação (busca gulosa por grau):")
        print(
            f"  Chega ao destino: {100 * navigation['success_rate']:.1f}% "
            f"de {navigation['pairs']} pares"
        )
        if navigation["stretch"] is not None:
            print(
                f"  Passos médios: {navigation['mean_steps']:.1f} contra "
                f"{navigation['mean_shortest']:.1f} do caminho mínimo "
                f"(alongamento {navigation['stretch']:.2f}x)"
            )
        if not args.no_plot:
            from plot_graph import show_robustness

            show_robustness(robustness)
    if not args.no_plot:
        # JsBegin
        from plot_graph import show_once

        show_once(graph)
        # JsEnd


if __name__ == "__main__":
    main()
