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
        if crafting_method is None:
            graph.add_node(
                f"unresolved_recipe:{recipe_id}",
                recipe_id=recipe_id,
                crafting_method=recipe["type"].removeprefix("minecraft:"),
                unresolved=True,
            )
            ignored_recipes.append({
                "recipe_id": recipe_id,
                "crafting_method": recipe["type"].removeprefix("minecraft:"),
            })
            skipped_count += 1
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
    args = parser.parse_args()
    graph = build_graph(args.recipe_directory)
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Loaded recipes: {graph.graph['crafting_recipes']}")
    print(f"Recipe variants: {graph.graph['recipe_variants']}")
    print(f"Ignored recipes/variants: {graph.graph['skipped_recipes']}")
    print(f"Duplicates: {graph.graph['duplicate_recipes']}")
    for recipe in graph.graph["ignored_recipes"]:
        reason = (
            f"duplicate of {recipe['duplicate_of']}"
            if "duplicate_of" in recipe else "unresolved; isolated placeholder"
        )
        print(f"Ignored: {recipe['recipe_id']} ({recipe['crafting_method']}; {reason})")
    if not args.no_plot:
        # JsBegin
        from plot_graph import show_once

        show_once(graph)
        # JsEnd


if __name__ == "__main__":
    main()
