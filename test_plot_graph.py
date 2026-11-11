import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

import networkx as nx

from plot_graph import interactive_html, show_once


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
