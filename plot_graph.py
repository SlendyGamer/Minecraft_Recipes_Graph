from html import escape
from math import atan2, cos, pi, sin
from collections import Counter

from analytics import short_name


import networkx as nx
import plotly.graph_objects as go


def create_figure(graph):
    positions = nx.spring_layout(
        graph.to_undirected(), seed=42, k=0.16, iterations=80, method="force"
    )
    edge_x, edge_y = [], []
    arrow_x, arrow_y = [], []
    hover_x, hover_y, hover_text = [], [], []
    for source, target, data in graph.edges(data=True):
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        angle = atan2(y1 - y0, x1 - x0)
        tip_x, tip_y = x0 + 0.8 * (x1 - x0), y0 + 0.8 * (y1 - y0)
        for offset in (-pi / 6, pi / 6):
            arrow_x.extend([tip_x - 0.008 * cos(angle + offset), tip_x, None])
            arrow_y.extend([tip_y - 0.008 * sin(angle + offset), tip_y, None])
        hover_x.append((x0 + x1) / 2)
        hover_y.append((y0 + y1) / 2)
        description = [f"{escape(source)} &#8594; {escape(target)}"]
        description.extend(
            f"{escape(record['recipe_id'])}<br>"
            f"{escape(record['crafting_method'])}: "
            f"input {record['input']}, output {record['output']}"
            for record in data["recipes"]
        )
        hover_text.append("<br><br>".join(description))

    figure = go.Figure()
    figure.add_trace(go.Scattergl(
        x=edge_x + arrow_x, y=edge_y + arrow_y, mode="lines",
        line={"color": "rgba(129,148,165,0.35)", "width": 1},
        hoverinfo="skip", showlegend=False,
    ))
    figure.add_trace(go.Scattergl(
        x=hover_x, y=hover_y, mode="markers",
        marker={"size": 8, "color": "rgba(129,148,165,0.01)"},
        text=hover_text, hovertemplate="%{text}<extra></extra>",
        showlegend=False,
    ))
    groups = {
        "Items": ("#6ab7ff", []),
        "Tags (any)": ("#f6c85f", []),
    }
    for node in graph.nodes:
        group = "Tags (any)" if node.endswith("(any)") else "Items"
        groups[group][1].append(node)
    for name, (color, nodes) in groups.items():
        if not nodes:
            continue
        figure.add_trace(go.Scattergl(
            x=[positions[node][0] for node in nodes],
            y=[positions[node][1] for node in nodes],
            mode="markers", name=name,
            marker={"color": color, "size": 9},
            text=[
                f"{escape(node)}<br>Incoming: {graph.in_degree(node)}"
                f"<br>Outgoing: {graph.out_degree(node)}"
                for node in nodes
            ],
            customdata=nodes,
            hovertemplate="%{text}<extra></extra>",
        ))
    figure.update_layout(
        title=f"Minecraft crafting: {graph.number_of_nodes()} nodes, "
              f"{graph.number_of_edges()} edges",
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        dragmode="pan", hovermode="closest",
        margin={"l": 15, "r": 15, "t": 60, "b": 15},
        xaxis={"visible": False},
        yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1},
        legend={"orientation": "h", "y": 1.04},
    )
    return figure


# JsBegin
def interactive_html(graph):
    import json

    figure = create_figure(graph)
    figure.update_layout(uirevision="fixed-layout")
    positions = {
        node: (x, y)
        for trace in figure.data[2:]
        for node, x, y in zip(trace.customdata, trace.x, trace.y)
    }
    payload = {
        "positions": {node: [float(x), float(y)] for node, (x, y) in positions.items()},
        "edges": [
            {"source": source, "target": target, "recipes": data["recipes"]}
            for source, target, data in graph.edges(data=True)
        ],
    }
    script = r"""
const plot = document.getElementById('{plot_id}');
const model = __MODEL__;
const base = JSON.parse(JSON.stringify(plot.data));
let selected = null, hovered = null;
let pending = false;
function eventNode(event) {
    const node = event?.points?.[0]?.customdata;
    return typeof node === 'string' && Object.hasOwn(model.positions, node) ? node : null;
}
function render() {
    const traces = JSON.parse(JSON.stringify(base));
    const neighbors = new Set(hovered ? [hovered] : []);
    const connectedEdges = model.edges.filter(edge =>
        edge.source === hovered || edge.target === hovered);
    for (const edge of connectedEdges) {
        neighbors.add(edge.source);
        neighbors.add(edge.target);
    }
    traces[0].opacity = hovered ? 0.08 : 1;
    traces[1].opacity = hovered ? 0.08 : 1;
    for (const trace of traces.slice(2)) {
        trace.marker.opacity = trace.customdata.map(node =>
            !hovered || neighbors.has(node) ? 1 : 0.08);
    }
    if (hovered) {
        const x = [], y = [];
        for (const edge of connectedEdges) {
            const a = model.positions[edge.source], b = model.positions[edge.target];
            x.push(a[0], b[0], null); y.push(a[1], b[1], null);
        }
        traces.push({type:'scattergl', mode:'lines', x, y,
            line:{color:'#c5d9ec', width:2}, hoverinfo:'skip', showlegend:false});
    }
    const incoming = model.edges.filter(edge => edge.target === selected);
    const ids = [...new Set(incoming.flatMap(edge =>
        edge.recipes.map(recipe => recipe.recipe_id)))].sort();
    ids.forEach((id, index) => {
        const x = [], y = [], text = [];
        for (const edge of incoming) {
            const recipe = edge.recipes.find(recipe => recipe.recipe_id === id);
            if (!recipe) continue;
            const a = model.positions[edge.source], b = model.positions[edge.target];
            const length = Math.hypot(b[0]-a[0], b[1]-a[1]) || 1;
            const edgeIds = [...new Set(edge.recipes.map(r => r.recipe_id))].sort();
            const rank = edgeIds.indexOf(id);
            const spread = Math.min(0.08, length*0.3);
            const offset = edgeIds.length === 1 ? 0 :
                (2*rank/(edgeIds.length-1)-1)*spread;
            const dx = -(b[1]-a[1])/length*offset, dy = (b[0]-a[0])/length*offset;
            const label = `${edge.source} → ${edge.target}<br>${id}<br>` +
                `${recipe.crafting_method}: input ${recipe.input}, output ${recipe.output}`;
            // Separate shared recipes without detaching endpoints from their nodes.
            for (let step = 0; step <= 16; step++) {
                const t = step/16, bend = 4*t*(1-t);
                x.push(a[0]+t*(b[0]-a[0])+bend*dx);
                y.push(a[1]+t*(b[1]-a[1])+bend*dy);
                text.push(label);
            }
            x.push(null); y.push(null); text.push(null);
        }
        traces.push({type:'scattergl', mode:'lines', x, y, text, name:id,
            line:{color:`hsl(${index*360/ids.length},80%,65%)`, width:3},
            opacity:!hovered || neighbors.has(selected) ? 1 : 0.08,
            hovertemplate:'%{text}<extra></extra>'});
    });
    Plotly.react(plot, traces, plot.layout, plot._context);
}
function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; render(); });
}
plot.on('plotly_hover', event => {
    const node = eventNode(event);
    if (node !== hovered) { hovered = node; schedule(); }
});
plot.on('plotly_unhover', () => {
    if (hovered !== null) { hovered = null; schedule(); }
});
plot.on('plotly_click', event => {
    const node = eventNode(event);
    if (node) { selected = node; schedule(); }
});
const clear = document.createElement('button');
clear.textContent = 'Limpar selecao';
clear.style.cssText = 'position:fixed;left:20px;bottom:15px;z-index:10;padding:8px';
clear.onclick = () => { selected = null; hovered = null; schedule(); };
document.body.appendChild(clear);
"""
    script = script.replace("__MODEL__", json.dumps(payload).replace("<", "\\u003c"))
    return figure.to_html(
        full_html=True, include_plotlyjs=True, post_script=script,
        config={"scrollZoom": True, "editable": False, "displaylogo": False},
    )


def show_once(graph):
    _serve_once(interactive_html(graph).encode("utf-8"))


def _serve_once(content):
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 60
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Opening once: {url} (F5 requires running the script again)")
        if not webbrowser.open(url):
            print(f"Open this address within 60 seconds: {url}")
        server.handle_request()


def degree_centrality(graph, log_log=False):
    """Plota graus de entrada e saída; log_log ativa escalas logarítmicas."""
    # Tags (any) fazem parte da rede.
    nodes = list(graph.nodes)
    analysis_graph = graph
    node_count = len(nodes)

    # Graus contam vizinhos distintos, não receitas; entrada são ingredientes conectados.
    # Cada par (nó, grau) permite exibir os nomes no hover.
    degree_sequences = {
        "Grau de entrada:": [
            (node, analysis_graph.in_degree(node)) for node in nodes
        ],
        "Grau de saída:": [
            (node, analysis_graph.out_degree(node)) for node in nodes
        ],
    }

    # Inicializa a figura Plotly; cada série representa uma direção do grau.
    figure = go.Figure()

    for name, node_degrees in degree_sequences.items():
        # Agrupa os nós por grau para calcular a frequência de cada valor k.
        nodes_by_degree = {}
        for node, degree in node_degrees:
            # Grau zero só é omitido no modo log, pois log(0) não é definido.
            if not log_log or degree > 0:
                nodes_by_degree.setdefault(degree, []).append(node)
        # Counter registra quantos nós têm cada grau.
        count = Counter({degree: len(items) for degree, items in nodes_by_degree.items()})
        if not count:
            # Sem graus positivos, não há pontos para a escala logarítmica.
            continue
        # Ordena graus e frequências para usá-los nos eixos X e Y.
        degree_values, frequency = zip(*sorted(count.items()))
        hover_nodes = []
        for degree in degree_values:
            matching_nodes = nodes_by_degree[degree]
            # Limita o hover a 30 nomes e escapa caracteres especiais de HTML.
            labels = [escape(node) for node in matching_nodes[:30]]
            remaining = len(matching_nodes) - len(labels)
            if remaining:
                labels.append(f"... e mais {remaining} nós")
            hover_nodes.append("<br>".join(labels))

        # customdata e hovertemplate mostram grau, frequência e nomes ao passar o mouse.
        hover_options = {
            "customdata": hover_nodes,
            "hovertemplate": (
                "Grau: %{x}<br>Frequência: %{y}<br><br>" 
                "Nós:<br>%{customdata}<extra>%{fullData.name}</extra>"
            ),
        }
        # Barras mostram a distribuição; marcadores são usados na escala log-log.
        if log_log:
            figure.add_trace(go.Scatter(
                x=degree_values,
                y=frequency,
                mode="markers",
                name=name,
                **hover_options,
            ))
        else:
            figure.add_trace(go.Bar(
                x=degree_values,
                y=frequency,
                name=name,
                **hover_options,
            ))

    # A escala log-log ajuda a examinar a cauda, mas não prova uma lei de potência.
    # update_layout define títulos, escalas, aparência e legenda.
    figure.update_layout(
        title=(
            f"Distribuição de grau{' (log-log)' if log_log else ''}: "
            f"{node_count} nós"
        ),
        xaxis={
            "title": "Grau k" if not log_log else "Grau k (k > 0)",
            "type": "log" if log_log else "linear",
        },
        yaxis={"title": "Frequência", "type": "log" if log_log else "linear"},
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        margin={"l": 15, "r": 15, "t": 60, "b": 15},
        legend={"orientation": "h", "y": 1.04},
        # Coloca as barras de entrada e saída lado a lado para cada grau.
        barmode="group",
    )

    # Devolve a figura pronta; quem chamou a função decide se usa .show() ou a salva.
    return figure


def fragility_figure(result, top=25):
    """Barras horizontais: itens que deixam de ser fabricáveis sem cada recurso base."""
    rows = list(reversed(result["by_resource"][:top]))
    figure = go.Figure(go.Bar(
        x=[len(row["lost"]) for row in rows],
        y=[short_name(row["name"]) for row in rows],
        orientation="h", marker={"color": "#4aa3df"},
        hovertemplate="%{y}: %{x} itens perdidos<extra></extra>",
    ))
    figure.update_layout(
        title=(
            "Fragilidade: itens que deixam de ser fabricáveis sem o recurso "
            f"(linha de base: {len(result['baseline'])} itens; tags (any) tratadas como disponíveis)"
        ),
        xaxis={"title": "Itens perdidos"},
        yaxis={"dtick": 1, "automargin": True},
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        margin={"l": 15, "r": 400, "t": 60, "b": 40},
    )
    return figure


def fragility_html(result, top=25):
    """Página com o gráfico e um painel que lista todos os itens perdidos ao clicar."""
    import json

    figure = fragility_figure(result, top)
    payload = {
        short_name(row["name"]): {
            "members": sorted(short_name(node) for node in row["members"]),
            "lost": sorted(short_name(node) for node in row["lost"]),
        }
        for row in result["by_resource"][:top]
    }
    script = r"""
const plot = document.getElementById('{plot_id}');
const model = __MODEL__;
const baseColors = plot.data[0].y.map(() => '#4aa3df');
const panel = document.createElement('div');
panel.style.cssText = 'position:fixed;top:60px;right:15px;bottom:15px;' +
    'overflow:auto;padding:12px;background:#0f1720;color:#dce6f0;' +
    'font:14px sans-serif;border:1px solid #2a3b4c;box-sizing:border-box;display:none';
document.body.appendChild(panel);
function fitPanel() {
    const width = Math.max(220, Math.min(360, innerWidth * 0.3));
    panel.style.width = `${width}px`;
    Plotly.relayout(plot, {'margin.r': width + 30});
}
fitPanel();
window.addEventListener('resize', fitPanel);
plot.on('plotly_click', event => {
    const name = event?.points?.[0]?.y;
    if (!Object.hasOwn(model, name)) return;
    const entry = model[name];
    const colors = baseColors.slice();
    colors[event.points[0].pointIndex] = '#f2b84b';
    Plotly.restyle(plot, {'marker.color': [colors]}, [0]);
    panel.replaceChildren();
    panel.style.display = 'block';
    const title = document.createElement('h3');
    title.textContent = `Sem ${entry.members.join(', ')}: ${entry.lost.length} itens`;
    title.style.margin = '0 0 8px';
    const list = document.createElement('ul');
    list.style.cssText = 'margin:0;padding-left:18px';
    for (const item of entry.lost) {
        const li = document.createElement('li');
        li.textContent = item;
        list.appendChild(li);
    }
    panel.append(title, entry.lost.length ? list : 'Nenhum item perdido.');
});
"""
    script = script.replace("__MODEL__", json.dumps(payload).replace("<", "\\u003c"))
    return figure.to_html(
        full_html=True, include_plotlyjs=True, post_script=script,
        config={"displaylogo": False},
    )


def show_fragility(result, top=25):
    _serve_once(fragility_html(result, top).encode("utf-8"))


def pagerank_figure(result):
    """Barras horizontais lado a lado: PageRank normal e reverso."""
    from plotly.subplots import make_subplots

    figure = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.2,
        subplot_titles=(
            "Normal (ingrediente → produto)",
            "Reverso (produto → ingrediente)",
        ),
    )
    for column, (key, color) in enumerate(
        (("normal", "#f2b84b"), ("reverse", "#4aa3df")), start=1
    ):
        rows = list(reversed(result[key]))
        figure.add_trace(go.Bar(
            x=[row["score"] for row in rows],
            y=[short_name(row["name"]) for row in rows],
            orientation="h", marker={"color": color},
            customdata=[[row["in_degree"], row["out_degree"]] for row in rows],
            hovertemplate=(
                "%{y}<br>PageRank: %{x:.5f}"
                "<br>Grau de entrada: %{customdata[0]}"
                "<br>Grau de saída: %{customdata[1]}<extra></extra>"
            ),
        ), row=1, col=column)
    figure.update_xaxes(title_text="PageRank")
    figure.update_yaxes(dtick=1, automargin=True)
    figure.update_layout(
        title="PageRank nos dois sentidos das receitas", showlegend=False,
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        margin={"l": 15, "r": 15, "t": 80, "b": 40},
    )
    return figure


def show_pagerank(result):
    html = pagerank_figure(result).to_html(
        full_html=True, include_plotlyjs=True, config={"displaylogo": False},
    )
    _serve_once(html.encode("utf-8"))



def centrality_figure(result):
    """Barras horizontais lado a lado: betweenness e closeness no maior componente."""
    from plotly.subplots import make_subplots

    figure = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.2,
        subplot_titles=("Betweenness", "Closeness"),
    )
    for column, (key, color) in enumerate(
        (("betweenness", "#7bd88f"), ("closeness", "#c792ea")), start=1
    ):
        rows = list(reversed(result[key]))
        figure.add_trace(go.Bar(
            x=[row["score"] for row in rows],
            y=[short_name(row["name"]) for row in rows],
            orientation="h", marker={"color": color},
            customdata=[row["degree"] for row in rows],
            hovertemplate=(
                "%{y}<br>Valor: %{x:.5f}<br>Grau: %{customdata}<extra></extra>"
            ),
        ), row=1, col=column)
    figure.update_xaxes(title_text="Centralidade")
    figure.update_yaxes(dtick=1, automargin=True)
    figure.update_layout(
        title=(
            f"Centralidade no maior componente: {result['component_size']} "
            f"de {result['node_count']} nós"
        ),
        showlegend=False,
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        margin={"l": 15, "r": 15, "t": 80, "b": 40},
    )
    return figure


def show_centrality(result):
    html = centrality_figure(result).to_html(
        full_html=True, include_plotlyjs=True, config={"displaylogo": False},
    )
    _serve_once(html.encode("utf-8"))


def communities_figure(graph, result, top=12, bridges=10):
    """Rede colorida por comunidade; as `top` maiores têm cor própria e as demais são agrupadas."""
    from analytics import analysis_graph

    undirected = analysis_graph(graph)
    positions = nx.spring_layout(
        undirected, seed=42, k=0.16, iterations=80, method="force"
    )
    communities = result["communities"]
    membership = result["membership"]
    touches = {row["name"]: row["touches"] for row in result["bridges"]}

    edge_x, edge_y = [], []
    for source, target in undirected.edges:
        edge_x.extend([positions[source][0], positions[target][0], None])
        edge_y.extend([positions[source][1], positions[target][1], None])
    figure = go.Figure(go.Scattergl(
        x=edge_x, y=edge_y, mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": "rgba(129,148,165,0.25)", "width": 1},
    ))

    def add_nodes(name, color, nodes):
        figure.add_trace(go.Scattergl(
            x=[positions[node][0] for node in nodes],
            y=[positions[node][1] for node in nodes],
            mode="markers", name=name, marker={"color": color, "size": 9},
            text=[
                f"{escape(short_name(node))}<br>Comunidade {membership[node]} "
                f"({communities[membership[node]]['size']} itens)"
                f"<br>Comunidades vizinhas: {touches.get(node, 0)}"
                for node in nodes
            ],
            hovertemplate="%{text}<extra></extra>",
        ))

    for community in communities[:top]:
        label = ", ".join(short_name(node) for node in community["top"][:3])
        add_nodes(
            f"{community['size']}: {label}",
            f"hsl({community['id'] * 137.5 % 360:.0f},75%,62%)",
            sorted(community["members"]),
        )
    rest = [node for community in communities[top:] for node in community["members"]]
    if rest:
        add_nodes(
            f"outras {len(communities) - top} comunidades", "#6b7785", sorted(rest),
        )

    # Os itens-ponte recebem rótulo, pois são os conectores entre famílias.
    top_bridges = [row["name"] for row in result["bridges"][:bridges]]
    figure.add_trace(go.Scattergl(
        x=[positions[node][0] for node in top_bridges],
        y=[positions[node][1] for node in top_bridges],
        mode="markers+text", name="itens-ponte",
        text=[f"{short_name(node)} ({touches[node]})" for node in top_bridges],
        textposition=[
            ["top center", "bottom center", "middle right", "middle left"][index % 4]
            for index in range(len(top_bridges))
        ],
        textfont={"color": "#ffffff", "size": 12},
        marker={
            "size": 14, "color": "rgba(0,0,0,0)",
            "line": {"color": "#ffffff", "width": 2},
        },
        hoverinfo="skip",
    ))

    null = result["null_modularity"]
    null_text = f"; modelo nulo: {null:.3f}" if null is not None else ""
    figure.update_layout(
        title=(
            f"Comunidades (Louvain): {len(communities)} grupos, "
            f"modularidade {result['modularity']:.3f}{null_text}. "
            "Itens-ponte circulados: número de comunidades vizinhas"
        ),
        template="plotly_dark", paper_bgcolor="#17212b", plot_bgcolor="#17212b",
        dragmode="pan", hovermode="closest",
        margin={"l": 15, "r": 15, "t": 60, "b": 15},
        xaxis={"visible": False},
        yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1},
        legend={"orientation": "v", "x": 1.01, "y": 1},
    )
    return figure


def communities_html(graph, result):
    return communities_figure(graph, result).to_html(
        full_html=True, include_plotlyjs=True,
        config={"scrollZoom": True, "displaylogo": False},
    )


def show_communities(graph, result):
    _serve_once(communities_html(graph, result).encode("utf-8"))
# JsEnd
