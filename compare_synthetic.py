import argparse
import csv
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import stats

# Converte o arquivo de receitas em um grafo NetworkX.
from read_recipes import build_graph

# Nomes internos dos modelos sinteticos usados nas estruturas de dados e graficos.
MODELS = ("ER", "BA", "WS")
# Rótulos exibidos ao usuário em tabelas e gráficos.
MODEL_LABELS = {
    "Real": "Real",
    "ER": "ER (aleatorio)",
    "BA": "BA (livre de escala)",
    "WS": "WS (small world)",
}
COLORS = {"Real": "#1f77b4", "ER": "#d62728", "BA": "#2ca02c", "WS": "#ff7f0e"}

# (chave usada nos dados, rotulo exibido na interface textual).
METRICS = (
    ("nodes", "Nos"),
    ("edges", "Arestas"),
    ("mean_degree", "Grau medio"),
    ("max_degree", "Grau maximo"),
    ("clustering", "Clustering medio"),
    ("transitivity", "Transitividade"),
    ("avg_path", "Caminho medio"),
    ("diameter", "Diametro"),
    ("assortativity", "Assortatividade"),
    ("ks_degree", "Distancia KS do grau (vs real)"),
)


# Preparacao dos grafos
def to_simple_undirected(graph):
    """Versao nao dirigida e sem lacos do grafo dirigido de receitas."""
    # Mantem apenas uma aresta entre cada par de nós em uma representação simples.
    undirected = nx.Graph(graph.to_undirected())
    # Remove auto-relacoes que não representam receitas entre itens diferentes.
    undirected.remove_edges_from(nx.selfloop_edges(undirected))
    return undirected


def giant_component(graph):
    """Subgrafo induzido pela maior componente conexa (copia independente)."""
    # Grafos vazios não possuem componentes, portanto são preservados por cópia.
    if graph.number_of_nodes() == 0:
        return graph.copy()
    # Seleciona o conjunto de nós da componente com maior quantidade de vértices.
    nodes = max(nx.connected_components(graph), key=len)
    return graph.subgraph(nodes).copy()


def model_parameters(n, m):
    """Parametros dos modelos para igualar o tamanho do grafo real.

    ER: n nos e exatamente m arestas.
    BA: cada novo no traz round(m/n) arestas (>= 1), o que da cerca de m arestas.
    WS: grau medio inicial k = 2m/n arredondado para o par mais proximo (>= 2).
    """
    # BA: garante pelo menos uma aresta de entrada para cada novo nó.
    attach = max(1, round(m / n))
    # WS: usa um grau inicial par e evita valores menores que dois.
    k = max(2, 2 * round(m / n))
    return {"er_edges": m, "ba_attach": attach, "ws_k": k}


def generate(model, n, m, seed, ws_p=0.1):
    """Gera um grafo sintetico do modelo pedido, equivalente ao real (n, m)."""
    params = model_parameters(n, m)
    # ER preserva a quantidade total de nós e arestas do grafo real.
    if model == "ER":
        return nx.gnm_random_graph(n, params["er_edges"], seed=seed)
    # BA gera preferência por nós de grau maior.
    if model == "BA":
        return nx.barabasi_albert_graph(n, params["ba_attach"], seed=seed)
    # WS começa com estrutura regular e aplica religação aleatória com probabilidade p.
    if model == "WS":
        return nx.watts_strogatz_graph(n, params["ws_k"], ws_p, seed=seed)
    # Impede a comparação silenciosa com um identificador de modelo inválido.
    raise ValueError(f"Modelo desconhecido: {model}")


# Metricas
def path_statistics(graph):
    """Caminho medio e diametro em uma unica varredura de BFS por no.

    Exige grafo conexo e com ao menos dois nos.
    """
    n = graph.number_of_nodes()
    if n < 2:
        raise ValueError("Caminho medio exige ao menos 2 nos.")
    # total acumula todas as distâncias entre pares; longest guarda o maior deles.
    total = 0
    longest = 0
    for source in graph:
        lengths = nx.single_source_shortest_path_length(graph, source)
        # A maior componente já deveria ser conexa; esta validação evita resultados incompletos.
        if len(lengths) != n:
            raise ValueError("O grafo precisa ser conexo.")
        total += sum(lengths.values())
        longest = max(longest, max(lengths.values()))
    # Divide pelas n*(n-1) orientações possíveis entre pares distintos.
    return total / (n * (n - 1)), longest


def graph_metrics(graph, reference_degrees=None):
    """Metricas de um grafo conexo e nao dirigido.

    reference_degrees: graus do grafo real, para a distancia KS entre
    distribuicoes de grau (0 = identicas, 1 = totalmente diferentes).
    """
    # Conjunto de graus necessário para estatísticas e para o teste KS.
    degrees = np.array([d for _, d in graph.degree()])
    avg_path, diameter = path_statistics(graph)
    # Agrupa em um único registro todas as métricas usadas na saída e nos gráficos.
    result = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "mean_degree": float(degrees.mean()),
        "max_degree": int(degrees.max()),
        "clustering": nx.average_clustering(graph),
        "transitivity": nx.transitivity(graph),
        "avg_path": avg_path,
        "diameter": diameter,
        "assortativity": nx.degree_assortativity_coefficient(graph),
        "ks_degree": float("nan"),
    }
    if reference_degrees is not None:
        # A estatística KS mede a maior diferença entre as distribuições acumuladas de grau.
        result["ks_degree"] = float(stats.ks_2samp(degrees, reference_degrees).statistic)
    return result


def compare(real, samples=20, seed=42, ws_p=0.1):
    """Compara o grafo real (conexo) com `samples` sorteios de cada modelo.

    Retorna um dicionario com:
        real:     metricas do grafo real
        models:   {modelo: {metrica: (media, desvio)}}
        graphs:   {modelo: [grafos sorteados (maior componente)]}
        params:   parametros usados nos modelos
        sigma:    indice small world (Humphries & Gurney) com ER como referencia
    """
    n, m = real.number_of_nodes(), real.number_of_edges()
    # Os graus reais são usados como referência para calcular KS nas amostras.
    real_degrees = np.array([d for _, d in real.degree()])
    real_metrics = graph_metrics(real)
    # Para o próprio grafo real, a distância da distribuição em relação a si é zero.
    real_metrics["ks_degree"] = 0.0

    # graphs conserva os componentes gerados; rows guarda suas métricas por amostra.
    graphs = {model: [] for model in MODELS}
    rows = {model: [] for model in MODELS}
    for model_index, model in enumerate(MODELS):
        for i in range(samples):
            # Semente distinta por modelo e por amostra, mas reprodutivel.
            sample = generate(model, n, m, seed + 1000 * model_index + i, ws_p)
            # A análise estrutural é feita sobre a maior componente de cada realização.
            sample = giant_component(sample)
            graphs[model].append(sample)
            rows[model].append(graph_metrics(sample, real_degrees))

    # Resume todas as amostras em média e desvio padrão para cada métrica.
    models = {}
    for model in MODELS:
        models[model] = {
            key: (
                float(np.mean([row[key] for row in rows[model]])),
                float(np.std([row[key] for row in rows[model]])),
            )
            for key, _ in METRICS
        }

    sigma = None
    # ER é usado como referência aleatória para normalizar clustering e caminho médio.
    c_rand, l_rand = models["ER"]["clustering"][0], models["ER"]["avg_path"][0]
    if c_rand > 0 and l_rand > 0 and real_metrics["avg_path"] > 0:
        # sigma > 1 é uma indicação clássica de propriedade small-world.
        sigma = (real_metrics["clustering"] / c_rand) / (real_metrics["avg_path"] / l_rand)

    params = model_parameters(n, m)
    params["ws_p"] = ws_p
    return {
        "real": real_metrics,
        "models": models,
        "graphs": graphs,
        "params": params,
        "sigma": sigma,
        "real_graph": real,
    }


def closest_model(result, key):
    """Modelo cuja media esta mais proxima do valor real, por diferenca relativa."""
    real_value = result["real"][key]
    # Normaliza pela escala real; evita divisão por zero usando 1.0 nesse caso.
    scale = abs(real_value) if real_value else 1.0
    # Compara a média de cada modelo pela menor diferença relativa.
    return min(
        MODELS,
        key=lambda model: abs(result["models"][model][key][0] - real_value) / scale,
    )


# Saida em texto e CSV
def format_value(value, key):
    # Métricas discretas são exibidas sem casas decimais desnecessárias.
    if key in {"nodes", "edges", "max_degree", "diameter"}:
        return f"{value:.1f}" if isinstance(value, float) and value % 1 else f"{value:.0f}"
    # Métricas contínuas são formatadas com três casas decimais.
    return f"{value:.3f}"


def print_report(result):
    params = result["params"]
    print("\n=== COMPARACAO COM GRAFOS SINTETICOS (maior componente conexa) ===")
    print(
        f"Parametros: ER m={params['er_edges']} | BA m_attach={params['ba_attach']} | "
        f"WS k={params['ws_k']}, p={params['ws_p']}"
    )
    header = f"{'Metrica':34s}{'Real':>10s}" + "".join(f"{m:>18s}" for m in MODELS)
    print(header)
    print("-" * len(header))
    for key, label in METRICS:
        cells = [f"{format_value(result['real'][key], key):>10s}"]
        for model in MODELS:
            # Mostra média e desvio da realização sintética em cada coluna.
            mean, std = result["models"][model][key]
            cells.append(f"{format_value(mean, key)} ± {std:.3f}".rjust(18))
        print(f"{label:34s}" + "".join(cells))

    print("\nModelo mais proximo do real em cada metrica estrutural:")
    for key in ("clustering", "avg_path", "diameter", "max_degree", "assortativity"):
        label = dict(METRICS)[key]
        print(f"  {label:20s} -> {MODEL_LABELS[closest_model(result, key)]}")

    real, er = result["real"], result["models"]["ER"]
    print("\nEvidencias (real em relacao ao aleatorio ER):")
    if er["clustering"][0] > 0:
        print(f"  Clustering real / ER    = {real['clustering'] / er['clustering'][0]:.1f}x")
    print(f"  Caminho medio real / ER = {real['avg_path'] / er['avg_path'][0]:.2f}x")
    print(f"  Grau maximo real / ER   = {real['max_degree'] / er['max_degree'][0]:.1f}x")
    if result["sigma"] is not None:
        print(f"  Indice small world sigma = {result['sigma']:.1f} (> 1 sugere small world)")


def save_csv(result, path):
    # newline="" evita linhas vazias adicionais em sistemas que usam CSV no Windows.
    with Path(path).open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        # Salva primeiro o valor real e depois média e desvio de cada modelo.
        writer.writerow(
            ["metrica", "real"]
            + [f"{m}_media" for m in MODELS]
            + [f"{m}_desvio" for m in MODELS]
        )
        for key, label in METRICS:
            writer.writerow(
                [label, result["real"][key]]
                + [result["models"][m][key][0] for m in MODELS]
                + [result["models"][m][key][1] for m in MODELS]
            )


# Graficos
def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def ccdf(degrees):
    """P(K >= k) para cada grau k presente."""
    # Agrupa graus iguais em contagens antes de construir a função acumulada.
    values, counts = np.unique(np.asarray(degrees), return_counts=True)
    # Subtrai os graus menores que k para obter P(K >= k).
    prob = 1.0 - (np.cumsum(counts) - counts) / counts.sum()
    return values, prob


def plot_degree_comparison(result, path):
    """CCDF do grau em escala log-log: real x modelos (distribuicao agregada)."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(7, 5))
    # Curva do grafo real em escala log-log.
    x, y = ccdf([d for _, d in result["real_graph"].degree()])
    ax.loglog(x, y, "o", ms=5, color=COLORS["Real"], label=MODEL_LABELS["Real"], zorder=3)
    for model in MODELS:
        # Junta os graus de todas as realizações para representar o modelo agregado.
        pooled = [d for g in result["graphs"][model] for _, d in g.degree()]
        x, y = ccdf(pooled)
        ax.loglog(x, y, "-", lw=1.8, alpha=0.85, color=COLORS[model], label=MODEL_LABELS[model])
    ax.set(
        title="Distribuicao de grau acumulada (CCDF): real x sinteticos",
        xlabel="grau k",
        ylabel="P(K >= k)",
    )
    ax.legend()
    ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_metric_comparison(result, path):
    """Barras do real e das medias dos modelos (com desvio) por metrica."""
    plt = _pyplot()
    panels = (
        ("clustering", "Clustering medio", True),
        ("avg_path", "Caminho medio", False),
        ("diameter", "Diametro", False),
        ("max_degree", "Grau maximo", False),
        ("assortativity", "Assortatividade de grau", False),
        ("ks_degree", "Distancia KS do grau (vs real)", False),
    )
    names = ["Real", *MODELS]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, (key, title, log_scale) in zip(axes.ravel(), panels):
        # A barra real não possui erro; as barras sintéticas usam desvio padrão.
        values = [result["real"][key]] + [result["models"][m][key][0] for m in MODELS]
        errors = [0.0] + [result["models"][m][key][1] for m in MODELS]
        bars = ax.bar(
            names, values, yerr=errors, capsize=4, color=[COLORS[n] for n in names]
        )
        if log_scale:
            ax.set_yscale("log")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title(title)
        # Anota o valor numérico no topo de cada barra.
        for bar, value in zip(bars, values):
            ax.annotate(
                f"{value:.3g}",
                (bar.get_x() + bar.get_width() / 2, max(value, 0)),
                ha="center", va="bottom", fontsize=8,
                xytext=(0, 3), textcoords="offset points",
            )
    params = result["params"]
    fig.suptitle(
        f"Grafo real x sinteticos equivalentes "
        f"(media de amostras; WS k={params['ws_k']}, p={params['ws_p']})"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_small_world_map(result, path):
    """Mapa C x L normalizados pelo aleatorio (ER): onde cada modelo se posiciona."""
    plt = _pyplot()
    er = result["models"]["ER"]
    # Valores usados para normalizar C e L em relação ao modelo aleatório.
    c_rand, l_rand = er["clustering"][0], er["avg_path"][0]
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    # O ponto real usa as mesmas métricas calculadas no grafo original.
    points = {"Real": (result["real"]["avg_path"], result["real"]["clustering"])}
    for model in MODELS:
        points[model] = (
            result["models"][model]["avg_path"][0],
            result["models"][model]["clustering"][0],
        )
    for name, (length, clustering) in points.items():
        # Cada ponto representa caminho médio normalizado e clustering normalizado.
        ax.scatter(
            length / l_rand, clustering / c_rand, s=140, color=COLORS[name],
            label=MODEL_LABELS[name], zorder=3,
        )
    ax.axvline(1, color="gray", lw=0.8, ls="--")
    ax.axhline(1, color="gray", lw=0.8, ls="--")
    ax.set_yscale("log")
    ax.set(
        title="Small world: C/C_ER x L/L_ER",
        xlabel="caminho medio / caminho medio do ER",
        ylabel="clustering / clustering do ER (log)",
    )
    ax.text(
        0.02, 0.97, "Small world: L/L_ER ~ 1 e C/C_ER >> 1",
        transform=ax.transAxes, va="top", fontsize=9, color="gray",
    )
    ax.legend(loc="center right")
    ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def make_plots(result, out_dir):
    # mkdir com exist_ok=True permite reutilizar um diretório já existente.
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        out_dir / "comparacao_distribuicao_grau.png",
        out_dir / "comparacao_metricas.png",
        out_dir / "comparacao_small_world.png",
    ]
    plot_degree_comparison(result, paths[0])
    plot_metric_comparison(result, paths[1])
    plot_small_world_map(result, paths[2])
    return paths


# Programa principal
def main():
    parser = argparse.ArgumentParser(
        description="Compara o grafo de receitas com ER, BA e Watts-Strogatz."
    )
    # Argumentos opcionais permitem ajustar amostragem, sementes e saída dos resultados.
    parser.add_argument(
        "recipe_directory",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "recipe",
    )
    parser.add_argument("--samples", type=int, default=20, help="sorteios por modelo")
    parser.add_argument("--seed", type=int, default=42, help="semente base")
    parser.add_argument("--ws-p", type=float, default=0.1, help="religacao do Watts-Strogatz")
    parser.add_argument("--out", type=Path, default=Path("figures_synthetic"))
    parser.add_argument("--no-plot", action="store_true", help="so imprime a tabela")
    args = parser.parse_args()
    # Validações impedem execuções sem amostras ou com probabilidade WS fora do intervalo.
    if args.samples < 1:
        parser.error("--samples precisa ser >= 1")
    if not 0 <= args.ws_p <= 1:
        parser.error("--ws-p precisa estar entre 0 e 1")

    # Constrói o grafo dirigido de receitas e converte para representação simples.
    directed = build_graph(args.recipe_directory)
    full = to_simple_undirected(directed)
    # Todas as métricas e comparações usam apenas a maior componente.
    real = giant_component(full)
    print(
        f"Grafo completo: {full.number_of_nodes()} nos, {full.number_of_edges()} arestas, "
        f"{nx.number_connected_components(full)} componentes"
    )
    print(
        f"Maior componente (base da comparacao): {real.number_of_nodes()} nos, "
        f"{real.number_of_edges()} arestas"
    )

    result = compare(real, samples=args.samples, seed=args.seed, ws_p=args.ws_p)
    print_report(result)

    # Garante que o diretório de saída exista antes de escrever qualquer resultado.
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "comparacao_metricas.csv"
    save_csv(result, csv_path)
    print(f"\nTabela salva em: {csv_path.resolve()}")
    if not args.no_plot:
        for path in make_plots(result, args.out):
            print(f"Grafico salvo em: {path.resolve()}")


if __name__ == "__main__":
    main()
