from collections import defaultdict

import networkx as nx
import math
import random


def is_tag(node):
    return str(node).endswith("(any)")


def extract_recipes(graph):
    """Reconstrói cada receita (todos os ingredientes ao mesmo tempo) a partir das arestas.

    Caminhos no grafo não representam fabricação: uma receita só é possível se
    todos os seus ingredientes existirem. O recipe_id das arestas liga as partes.
    """
    inputs = defaultdict(set)
    outputs = {}
    for source, target, data in graph.edges(data=True):
        for recipe in data["recipes"]:
            inputs[recipe["recipe_id"]].add(source)
            outputs[recipe["recipe_id"]] = target
    return [
        (recipe_id, frozenset(ingredients), outputs[recipe_id])
        for recipe_id, ingredients in inputs.items()
    ]


def craftable_items(resources, recipes):
    """Ponto fixo: repete as receitas possíveis até nada novo ser fabricado."""
    available = set(resources)
    changed = True
    while changed:
        changed = False
        for _, ingredients, output in recipes:
            if output not in available and ingredients <= available:
                available.add(output)
                changed = True
    return available


def base_resources(graph):
    """Grupos de nós sem entrada externa.

    Usa a condensação para tratar ciclos sem fonte (ex.: bruto <-> bloco bruto)
    como um único recurso. Grupos formados só por tags (any) são devolvidos
    separadamente, pois o grafo não os liga aos itens que representam.
    """
    condensed = nx.condensation(graph)
    groups = [
        frozenset(data["members"])
        for component, data in condensed.nodes(data=True)
        if condensed.in_degree(component) == 0
    ]
    tags = [group for group in groups if all(is_tag(node) for node in group)]
    removable = [group for group in groups if group not in tags]
    return removable, tags


def resource_fragility(graph):
    """Quantos itens deixam de ser fabricáveis ao remover cada recurso base.

    Devolve um dicionário com a linha de base, os itens inalcançáveis mesmo
    com todos os recursos e a lista (ordenada) de perdas por recurso.
    """
    recipes = extract_recipes(graph)
    removable, tags = base_resources(graph)
    always = set().union(*tags) if tags else set()
    all_resources = set(always).union(*removable) if removable else set(always)
    baseline = craftable_items(all_resources, recipes)

    def loss(removed):
        remaining = all_resources - removed
        return baseline - craftable_items(remaining, recipes) - removed

    by_resource = [
        {"name": sorted(group)[0], "members": group, "lost": frozenset(loss(group))}
        for group in removable
    ]
    by_resource.sort(key=lambda row: (-len(row["lost"]), row["name"]))

    nodes = set(graph)
    return {
        "baseline": baseline,
        "unreachable": nodes - baseline,
        "by_resource": by_resource,
    }


def analysis_graph(graph):
    """Grafo simples e não dirigido, sem placeholders e sem laços, para estrutura.

    Comunidades dependem apenas de quem se conecta a quem, não da direção.
    Laços (ex.: moldes de armadura que se duplicam) são removidos.
    """
    nodes = [node for node, data in graph.nodes(data=True) if not data.get("unresolved")]
    undirected = nx.Graph(graph.subgraph(nodes))
    undirected.remove_edges_from(nx.selfloop_edges(undirected))
    return undirected


def detect_communities(graph, seed=1, null_samples=5):
    """Comunidades por Louvain, itens-ponte e modularidade contra um modelo nulo.

    Item-ponte: tem vizinhos em outras comunidades; `touches` conta quantas.
    O modelo nulo (mesmos graus, ligações sorteadas) mostra quanta modularidade
    um grafo esparso teria sem nenhuma família de itens.
    """
    undirected = analysis_graph(graph)
    parts = nx.community.louvain_communities(undirected, seed=seed)
    parts.sort(key=lambda part: (-len(part), min(part)))
    membership = {node: index for index, part in enumerate(parts) for node in part}

    communities = [
        {
            "id": index,
            "members": frozenset(part),
            "size": len(part),
            "top": sorted(part, key=lambda node: (-undirected.degree(node), node))[:5],
        }
        for index, part in enumerate(parts)
    ]
    bridges = []
    for node in undirected:
        others = {membership[other] for other in undirected[node]} - {membership[node]}
        if others:
            bridges.append({
                "name": node, "touches": len(others), "communities": sorted(others),
                "degree": undirected.degree(node),
            })
    bridges.sort(key=lambda row: (-row["touches"], -row["degree"], row["name"]))

    degrees = [degree for _, degree in undirected.degree()]
    null_values = []
    for sample in range(null_samples):
        random_graph = nx.Graph(nx.configuration_model(degrees, seed=seed + sample))
        random_graph.remove_edges_from(nx.selfloop_edges(random_graph))
        if random_graph.number_of_edges():
            random_parts = nx.community.louvain_communities(random_graph, seed=seed)
            null_values.append(nx.community.modularity(random_graph, random_parts))

    return {
        "modularity": nx.community.modularity(undirected, parts),
        "null_modularity": sum(null_values) / len(null_values) if null_values else None,
        "communities": communities,
        "membership": membership,
        "bridges": bridges,
    }


def short_name(node):
    return str(node).removeprefix("minecraft:")


def pagerank_rankings(graph, top=15, alpha=0.85):
    """PageRank nos dois sentidos das arestas (ingrediente → produto).

    Normal: a importância flui dos ingredientes para os produtos e destaca itens
    no fim de cadeias de dependência. Reverso: flui dos produtos para os
    ingredientes e destaca recursos dos quais muitos itens dependem.
    """
    def ranking(directed):
        scores = nx.pagerank(directed, alpha=alpha)
        ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return [
            {
                "name": node,
                "score": score,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
            }
            for node, score in ordered[:top]
        ]

    return {"normal": ranking(graph), "reverse": ranking(graph.reverse(copy=False))}


def centrality_report(graph, top=15, candidates=None, candidate_count=6):
    """Betweenness e closeness no maior componente, mais um perfil dos candidatos.

    Caminhos mínimos só existem entre nós conectados, então o cálculo usa o maior
    componente do grafo não dirigido e sem laços (o mesmo de `analysis_graph`).
    O perfil junta, para cada candidato, grau, PageRank reverso, betweenness,
    closeness e quantas comunidades vizinhas ele toca (item-ponte). Sem
    `candidates`, são os `candidate_count` maiores do PageRank reverso.
    """
    undirected = analysis_graph(graph)
    component = undirected.subgraph(max(nx.connected_components(undirected), key=len))
    betweenness = nx.betweenness_centrality(component)
    closeness = nx.closeness_centrality(component)
    pagerank = nx.pagerank(graph.reverse(copy=False))
    if candidates is None:
        candidates = sorted(pagerank, key=lambda node: (-pagerank[node], node))[:candidate_count]
    bridges = {
        row["name"]: row["touches"]
        for row in detect_communities(graph, null_samples=0)["bridges"]
    }

    def ranking(scores):
        ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return [
            {"name": node, "score": score, "degree": component.degree(node)}
            for node, score in ordered[:top]
        ]

    profile = [
        {
            "name": node,
            "degree": component.degree(node) if node in component else None,
            "pagerank_reverse": pagerank.get(node),
            "betweenness": betweenness.get(node),
            "closeness": closeness.get(node),
            "bridge_touches": bridges.get(node, 0),
        }
        for node in candidates
    ]
    return {
        "component_size": component.number_of_nodes(),
        "node_count": undirected.number_of_nodes(),
        "betweenness": ranking(betweenness),
        "closeness": ranking(closeness),
        "profile": profile,
    }
    
    
def largest_component(graph):
    """Maior componente do grafo não dirigido, sem laços e sem placeholders."""
    undirected = analysis_graph(graph)
    return undirected.subgraph(max(nx.connected_components(undirected), key=len)).copy()


def diffusion_report(graph):
    """Caminho médio e diâmetro: quão curtas são as rotas entre quaisquer dois itens."""
    component = largest_component(graph)
    nodes = component.number_of_nodes()
    return {
        "nodes": nodes,
        "average_path": nx.average_shortest_path_length(component),
        "diameter": nx.diameter(component),
        "mean_degree": 2 * component.number_of_edges() / nodes,
        "log_nodes": math.log(nodes),
    }


def preservation_report(graph):
    """Redundância de receitas e k-core.

    Uma alternativa é um conjunto de ingredientes diferente para o mesmo item;
    trocar só a estação (forno × alto-forno) não conta como redundância.
    """
    by_output = defaultdict(set)
    for _, ingredients, output in extract_recipes(graph):
        by_output[output].add(ingredients)
    cores = nx.core_number(largest_component(graph))
    max_core = max(cores.values())
    return {
        "crafted_items": len(by_output),
        "with_alternative": sum(1 for options in by_output.values() if len(options) > 1),
        "max_core": max_core,
        "core_nodes": sorted(node for node, value in cores.items() if value == max_core),
    }


def robustness_report(graph, max_fraction=0.5, steps=25, runs=20, seed=1):
    """Fração do maior componente restante ao remover nós aleatórios × hubs.

    A fração é relativa aos nós que sobraram. Hubs são removidos por grau inicial.
    O limiar é a primeira fração removida em que o componente cai abaixo de 50%.
    """
    component = largest_component(graph)
    total = component.number_of_nodes()
    rng = random.Random(seed)
    nodes = sorted(component)
    by_degree = sorted(nodes, key=lambda node: (-component.degree(node), node))
    counts = [round(total * max_fraction * step / steps) for step in range(steps + 1)]

    def connected(removed):
        removed = set(removed)
        rest = component.subgraph(node for node in nodes if node not in removed)
        if not rest:
            return 0.0
        return max(len(part) for part in nx.connected_components(rest)) / rest.number_of_nodes()

    random_runs = []
    for _ in range(runs):
        order = nodes[:]
        rng.shuffle(order)
        random_runs.append([connected(order[:count]) for count in counts])
    random_curve = [sum(values) / runs for values in zip(*random_runs)]
    targeted_curve = [connected(by_degree[:count]) for count in counts]
    fractions = [count / total for count in counts]

    def threshold(curve):
        return next((f for f, value in zip(fractions, curve) if value < 0.5), None)

    return {
        "fractions": fractions,
        "random": random_curve,
        "targeted": targeted_curve,
        "threshold_random": threshold(random_curve),
        "threshold_targeted": threshold(targeted_curve),
    }


def navigation_report(graph, pairs=1000, seed=1):
    """Busca gulosa por grau, só com informação local, contra o caminho mínimo.

    De cada nó, vai ao vizinho ainda não visitado de maior grau; se o destino é
    vizinho, vai direto. Sem retrocesso: fica preso se todos os vizinhos já foram
    visitados. O alongamento (stretch) é a média de passos ÷ caminho mínimo.
    """
    component = largest_component(graph)
    rng = random.Random(seed)
    nodes = sorted(component)
    steps_taken, shortest_taken, stretch = [], [], []
    for _ in range(pairs):
        source, target = rng.sample(nodes, 2)
        current, visited, steps = source, {source}, 0
        while current != target:
            neighbors = component[current]
            if target in neighbors:
                current = target
            else:
                options = [node for node in neighbors if node not in visited]
                if not options:
                    break
                current = max(options, key=lambda node: (component.degree(node), node))
            visited.add(current)
            steps += 1
        if current == target:
            shortest = nx.shortest_path_length(component, source, target)
            steps_taken.append(steps)
            shortest_taken.append(shortest)
            stretch.append(steps / shortest)
    reached = len(steps_taken)
    return {
        "pairs": pairs,
        "success_rate": reached / pairs,
        "mean_steps": sum(steps_taken) / reached if reached else None,
        "mean_shortest": sum(shortest_taken) / reached if reached else None,
        "stretch": sum(stretch) / reached if reached else None,
    }