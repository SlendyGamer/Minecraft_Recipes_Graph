import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

import networkx as nx

from analytics import detect_communities
from plot_graph import communities_html, fragility_html, interactive_html, show_once


class PlotInteractionTests(unittest.TestCase):
    def test_interactive_page_embeds_events_and_graph(self):
        graph = nx.DiGraph()
        graph.add_edge("ingredient", "product", recipes=[
            {"recipe_id": "first", "input": 1, "output": 1,
             "crafting_method": "shaped"},
        ])
        page = interactive_html(graph)
        self.assertIn("plotly_hover", page)
        self.assertIn("plotly_click", page)
        self.assertIn('"recipe_id": "first"', page)
        self.assertNotIn("{plot_id}", page)
        self.assertIn("plotly.js", page)

    def test_fragility_page_lists_every_lost_item_on_click(self):
        result = {
            "baseline": {"a", "b", "c"},
            "by_resource": [{
                "name": "minecraft:a", "members": frozenset({"minecraft:a"}),
                "lost": frozenset({"minecraft:b", "minecraft:c"}),
            }],
        }
        page = fragility_html(result)
        self.assertIn("plotly_click", page)
        self.assertIn('"lost": ["b", "c"]', page)
        self.assertNotIn("{plot_id}", page)

    def test_communities_page_names_groups_and_bridges(self):
        graph = nx.DiGraph()
        for family in "ab":
            for recipe, (inputs, output) in enumerate([
                ([f"{family}1", f"{family}2"], f"{family}3"),
                ([f"{family}3"], f"{family}1"),
                ([f"{family}2"], f"{family}3"),
            ]):
                for item in inputs:
                    if not graph.has_edge(item, output):
                        graph.add_edge(item, output, recipes=[])
                    graph[item][output]["recipes"].append({
                        "recipe_id": f"{family}{recipe}", "input": 1, "output": 1,
                        "crafting_method": "shaped",
                    })
        graph.add_edge("a3", "b1", recipes=[
            {"recipe_id": "link", "input": 1, "output": 1, "crafting_method": "shaped"},
        ])
        page = communities_html(graph, detect_communities(graph, null_samples=1))
        self.assertIn("itens-ponte", page)
        self.assertIn("a3 (1)", page)
        self.assertIn("plotly.js", page)

    def test_one_request_closes_server(self):
        responses = []
        requests = []

        def open_browser(url):
            def fetch():
                with urlopen(url, timeout=5) as response:
                    responses.append(response.read())
            thread = threading.Thread(target=fetch)
            requests.append(thread)
            thread.start()
            return True

        with patch("plot_graph.interactive_html", return_value="<html>test</html>"):
            with patch("webbrowser.open", side_effect=open_browser):
                show_once(nx.DiGraph())
        for thread in requests:
            thread.join(timeout=5)
        self.assertEqual(responses, [b"<html>test</html>"])


if __name__ == "__main__":
    unittest.main()
