import json
import tempfile
import unittest
from pathlib import Path

from read_recipes import build_graph, recipe_inputs


class RecipeTests(unittest.TestCase):
    def test_shaped_counts_symbols_and_ignores_spaces(self):
        recipe = {
            "type": "minecraft:crafting_shaped",
            "key": {
                "X": {"tag": "minecraft:planks"},
                "#": {"item": "minecraft:stick"},
            },
            "pattern": ["XXX", " # ", " # "],
        }
        self.assertEqual(
            recipe_inputs(recipe),
            [{"minecraft:planks(any)": 3, "minecraft:stick": 2}],
        )

    def test_shapeless_aggregates_repeated_ingredients(self):
        recipe = {
            "type": "minecraft:crafting_shapeless",
            "ingredients": [
                {"item": "minecraft:wheat"},
                {"item": "minecraft:wheat"},
                {"tag": "minecraft:planks"},
            ],
        }
        self.assertEqual(
            recipe_inputs(recipe),
            [{"minecraft:wheat": 2, "minecraft:planks(any)": 1}],
        )

    def test_explicit_alternatives_allow_mixed_inputs_without_duplicates(self):
        options = [
            {"item": "minecraft:coal"},
            {"item": "minecraft:charcoal"},
        ]
        recipe = {
            "type": "minecraft:crafting_shapeless",
            "ingredients": [options, options],
        }
        variants = recipe_inputs(recipe)
        self.assertEqual(len(variants), 3)
        self.assertIn({"minecraft:coal": 1, "minecraft:charcoal": 1}, variants)

    def test_shared_edge_preserves_recipes_and_output_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name, count in [("first", 1), ("second", 4)]:
                recipe = {
                    "type": "minecraft:crafting_shapeless",
                    "ingredients": [{"item": "minecraft:oak_log"}],
                    "result": {"id": "minecraft:oak_planks", "count": count},
                }
                (folder / f"{name}.json").write_text(json.dumps(recipe), encoding="utf-8")
            (folder / "ignored.json").write_text(
                '{"type": "minecraft:crafting_special_repairitem"}', encoding="utf-8"
            )
            graph = build_graph(folder)

        self.assertEqual(graph.number_of_edges(), 1)
        self.assertEqual(
            graph["minecraft:oak_log"]["minecraft:oak_planks"]["recipes"],
            [
                {"recipe_id": "minecraft:first", "input": 1, "output": 1,
                 "crafting_method": "shaped"},
                {"recipe_id": "minecraft:second", "input": 1, "output": 4,
                 "crafting_method": "shaped"},
            ],
        )
        self.assertEqual(graph.graph["skipped_recipes"], 1)
        self.assertEqual(graph.degree("unresolved_recipe:minecraft:ignored"), 0)
        self.assertEqual(graph.graph["ignored_recipes"], [{
            "recipe_id": "minecraft:ignored",
            "crafting_method": "crafting_special_repairitem",
        }])

    def test_processing_methods_preserve_parallel_recipe_records(self):
        methods = {
            "smelting": "furnace",
            "blasting": "blast_furnace",
            "smoking": "smoker",
            "campfire_cooking": "campfire",
            "stonecutting": "stonecutter",
        }
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for kind in methods:
                recipe = {
                    "type": f"minecraft:{kind}",
                    "ingredient": {"item": "minecraft:source"},
                    "result": {"id": "minecraft:target"},
                }
                if kind == "stonecutting":
                    recipe["result"]["count"] = 2
                (folder / f"{kind}.json").write_text(json.dumps(recipe), encoding="utf-8")
            graph = build_graph(folder)
        records = graph["minecraft:source"]["minecraft:target"]["recipes"]
        self.assertEqual(len(records), 5)
        for record in records:
            kind = record["recipe_id"].removeprefix("minecraft:")
            self.assertEqual(record["crafting_method"], methods[kind])
            self.assertEqual(record["input"], 1)
            self.assertEqual(record["output"], 2 if kind == "stonecutting" else 1)

    def test_smithing_consumes_template_base_and_addition(self):
        recipe = {
            "type": "minecraft:smithing_transform",
            "template": {"item": "minecraft:netherite_upgrade_smithing_template"},
            "base": {"item": "minecraft:diamond_axe"},
            "addition": {"item": "minecraft:netherite_ingot"},
            "result": {"id": "minecraft:netherite_axe"},
        }
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "upgrade.json").write_text(json.dumps(recipe), encoding="utf-8")
            graph = build_graph(folder)
        self.assertEqual(graph.number_of_edges(), 3)
        for _, _, data in graph.edges(data=True):
            self.assertEqual(data["recipes"], [{
                "recipe_id": "minecraft:upgrade",
                "input": 1,
                "output": 1,
                "crafting_method": "smithing_table",
            }])

    def test_duplicates_ignore_position_symbols_and_shapeless_order(self):
        recipes = [
            {
                "type": "minecraft:crafting_shaped",
                "key": {"X": {"item": "minecraft:a"}, "#": {"item": "minecraft:b"}},
                "pattern": ["XX", "# "],
            },
            {
                "type": "minecraft:crafting_shaped",
                "key": {"A": {"item": "minecraft:a"}, "B": {"item": "minecraft:b"}},
                "pattern": [" B", "AA"],
            },
            {
                "type": "minecraft:crafting_shapeless",
                "ingredients": [
                    {"item": "minecraft:b"}, {"item": "minecraft:a"},
                    {"item": "minecraft:a"},
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for index, recipe in enumerate(recipes):
                recipe["result"] = {"id": "minecraft:product", "count": 1}
                (folder / f"{index}.json").write_text(json.dumps(recipe), encoding="utf-8")
            graph = build_graph(folder)
        self.assertEqual(graph.graph["duplicate_recipes"], 2)
        self.assertEqual(graph.graph["skipped_recipes"], 2)
        self.assertEqual(graph.graph["crafting_recipes"], 1)
        self.assertEqual(graph.graph["recipe_variants"], 1)
        self.assertEqual(len(graph["minecraft:a"]["minecraft:product"]["recipes"]), 1)
        self.assertTrue(all(
            recipe["duplicate_of"] == "minecraft:0"
            for recipe in graph.graph["ignored_recipes"]
        ))

    def test_deduplication_preserves_different_inputs_outputs_and_partial_variants(self):
        recipes = [
            ([{"item": "minecraft:a"}], "minecraft:product", 1),
            ([[{"item": "minecraft:a"}, {"item": "minecraft:b"}]], "minecraft:product", 1),
            ([{"item": "minecraft:a"}] * 2, "minecraft:product", 1),
            ([{"item": "minecraft:a"}], "minecraft:product", 2),
            ([{"item": "minecraft:a"}], "minecraft:other_product", 1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for index, (ingredients, output, count) in enumerate(recipes):
                recipe = {
                    "type": "minecraft:crafting_shapeless",
                    "ingredients": ingredients,
                    "result": {"id": output, "count": count},
                }
                (folder / f"{index}.json").write_text(json.dumps(recipe), encoding="utf-8")
            graph = build_graph(folder)
        self.assertEqual(graph.graph["duplicate_recipes"], 1)
        self.assertEqual(graph.graph["crafting_recipes"], 5)
        self.assertEqual(graph.graph["recipe_variants"], 5)
        self.assertEqual(len(graph["minecraft:a"]["minecraft:product"]["recipes"]), 3)
        self.assertTrue(graph.has_edge("minecraft:b", "minecraft:product"))


if __name__ == "__main__":
    unittest.main()
