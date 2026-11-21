from collections import defaultdict

import networkx as nx


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
