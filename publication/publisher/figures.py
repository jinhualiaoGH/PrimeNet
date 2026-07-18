from .diagram import Diagram
from .layout import vertical_stack, horizontal_stack
from .shapes import Node

def fig01_evolution(outdir, theme_name="primenet_light"):
    d = Diagram("Evolution of Computational Research", "From computation to persistent scientific infrastructure", theme_name=theme_name)
    # Publisher v2.4.3 final Figure 1 refinement:
    # - approximately 12% tighter milestone spacing
    # - center milestone raised slightly
    # - naturally shorter connectors
    # - approximately 6% larger milestone typography
    # Scientific content, title, subtitle, colors, and final-stage emphasis are unchanged.
    nodes = [
        Node("a", "1960s-1980s\nCan we compute?", .11, .62, .22, .12, "neutral"),
        Node("b", "1990s-2010s\nCan we compute faster?", .355, .45, .22, .12, "neutral"),
        Node("c", "2020s-\nHow do we organize,\nverify, preserve,\nshare, and build upon\nwhat we compute?", .60, .20, .25, .18, "foundation"),
    ]
    d.add_nodes(nodes, 8.5)
    d.connect("a", "b", "right", "left")
    d.connect("b", "c", "right", "left")
    d.note("PrimeNet addresses the infrastructure question in computational arithmetic.")
    d.save(outdir, "fig01_evolution")

def fig02_architecture(outdir, theme_name="primenet_light"):
    d = Diagram("Overall PrimeNet Architecture", "Coordinate, repository, observatory, product, and publication layers", theme_name=theme_name)
    d.container(.05, .10, .90, .74, "Reference Architecture")
    p = d.add_node(Node("p", "Prime Space\ncanonical coordinates", .36, .72, .28, .09, "foundation"), 8)
    mids = [
        Node("r", "Persistent\nRepository", .10, .50, .20, .10),
        Node("o", "Observatory\nFramework", .40, .50, .20, .10),
        Node("m", "Metadata\nRegistry", .70, .50, .20, .10),
    ]
    d.add_nodes(mids, 8)
    s = d.add_node(Node("s", "Observation Sessions", .32, .33, .36, .08, "neutral"), 8)
    pr = d.add_node(Node("pr", "Computational Products & Atlases", .27, .19, .46, .08, "foundation"), 8)
    f = d.add_node(Node("f", "Future Scientific Investigation", .31, .06, .38, .07, "evidence"), 8)
    [d.connect_nodes(p, m) for m in mids]
    [d.connect_nodes(m, s) for m in mids]
    d.connect("s", "pr")
    d.connect("pr", "f")
    d.save(outdir, "fig02_architecture")

def fig03_prime_space(outdir, theme_name="primenet_light"):
    d = Diagram("Prime Space Coordinate System", "Each prime has both numerical value and observational coordinate", theme_name=theme_name)
    primes = [2, 3, 5, 7, 11, 13, 17]
    xs = [.14 + i * .12 for i in range(len(primes))]
    d.ax.hlines(.46, .08, .92, linewidth=1.4, color=d.theme.muted)
    for i, (x, p) in enumerate(zip(xs, primes), 1):
        d.ax.plot([x], [.46], marker="o", color=d.theme.accent, markersize=6)
        d.ax.text(x, .55, f"p_{i} = {p}", ha="center", fontsize=8, color=d.theme.ink)
        d.ax.text(x, .34, f"i = {i}", ha="center", fontsize=8, color=d.theme.muted)
        d.ax.annotate("", xy=(x, .49), xytext=(x, .52), arrowprops=dict(arrowstyle="-|>", color=d.theme.accent, lw=1.0))
    d.add_node(Node("coord", "Observation record:  (i, p_i)", .32, .10, .36, .08, "foundation"), 9)
    d.note("The prime index supplies a stable observational coordinate independent of any individual analysis.")
    d.save(outdir, "fig03_prime_space")

def fig04_repository(outdir, theme_name="primenet_light"):
    d = Diagram("Layered Repository Architecture", "Persistent computational assets separated from services and metadata", 7.6, 5.8, theme_name)
    nodes = vertical_stack(["Applications", "Observatories", "Repository Services", "Metadata / Catalogs", "Persistent Computational Repository"], .24, .72, .52, .08, .065, "l")
    d.add_nodes(nodes)
    [d.connect_nodes(a, b) for a, b in zip(nodes[:-1], nodes[1:])]
    d.note("Layering allows metadata and services to evolve without altering verified computational assets.")
    d.save(outdir, "fig04_repository")

def fig05_construction(outdir, theme_name="primenet_light"):
    d = Diagram("Repository Construction Workflow", "Deterministic generation followed by independent verification", theme_name=theme_name)
    # Publisher v2.4.2 visual polish: narrower stages, more connector space,
    # and subtle emphasis on the persistent scientific asset.
    labels = [
        ("s1", "Integer\nInterval", .045, .47, .11, .11, "step"),
        ("s2", "Segment", .205, .47, .11, .11, "step"),
        ("s3", "Prime\nGeneration", .365, .47, .11, .11, "step"),
        ("s4", "Repository\nSegment", .525, .47, .11, .11, "step"),
        ("s5", "Independent\nVerification", .685, .47, .11, .11, "step"),
        ("s6", "Persistent\nRepository", .845, .465, .12, .12, "foundation"),
    ]
    nodes = [Node(*item) for item in labels]
    d.add_nodes(nodes, 7.5)
    [d.connect_nodes(a, b, "right", "left") for a, b in zip(nodes[:-1], nodes[1:])]
    d.ax.text(.5, .29, "Verified segments become reusable repository assets.", ha="center", fontsize=9, color=d.theme.muted)
    d.save(outdir, "fig05_construction")

from .fig06_repository_scale import build as fig06_repository_scale
from .fig07_validation import build as fig07_validation
from .fig08_performance import build as fig08_performance
from .fig09_growth import build as fig09_growth
from .fig10_observatory import build as fig10_observatory
from .theory_validation_assets import build as build_theory_validation_assets

FIGURES = [
    fig01_evolution,
    fig02_architecture,
    fig03_prime_space,
    fig04_repository,
    fig05_construction,
    fig06_repository_scale,
    fig07_validation,
    fig08_performance,
    fig09_growth,
    fig10_observatory,
]

def build_all(outdir, theme_name="primenet_light", stats=None):
    print("Generating figures with Figure Engine 2.4.3...")
    generated = []
    for index, function in enumerate(FIGURES, 1):
        print(f"  [{index}/16] {function.__name__}")
        if index <= 5:
            function(outdir, theme_name)
        else:
            function(outdir, theme_name, stats)
        generated.append(function.__name__)

    theory = build_theory_validation_assets(outdir, theme_name, stats)
    for offset, name in enumerate(theory, len(FIGURES) + 1):
        print(f"  [{offset}/16] {name}")
        generated.append(name)

    return generated
