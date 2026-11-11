from html import escape
from math import atan2, cos, pi, sin

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
        "Unresolved recipes": ("#ef6c6c", []),
    }
    for node, data in graph.nodes(data=True):
        group = (
            "Unresolved recipes" if data.get("unresolved")
            else "Tags (any)" if node.endswith("(any)") else "Items"
        )
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
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    content = interactive_html(graph).encode("utf-8")

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
# JsEnd
