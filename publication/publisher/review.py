from pathlib import Path
from .captions import FIGURE_CAPTIONS
from .manuscript_source import section_paragraphs

OPTIONAL_PUBLICATION_TABLES = {"table07_observational_performance"}

def _active_review_tables(table_dir, tables):
    active = []
    for table_name in tables:
        paths = [table_dir / f"{table_name}.{extension}" for extension in ("csv", "md", "docx")]
        if table_name in OPTIONAL_PUBLICATION_TABLES and not any(path.exists() for path in paths):
            print(f"[SKIP] Optional verification table unavailable: {table_name}")
            continue
        active.append(table_name)
    return active

def review_publication(root, config, tables):
    root = Path(root)
    fig_dir = root / config["paths"]["figures"]
    table_dir = root / config["paths"]["tables"]
    out_dir = root / config["paths"]["output"]
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "status": "PASSED" if ok else "FAILED", "detail": detail})

    for figure in FIGURE_CAPTIONS:
        for extension, min_size in (("png", 20000), ("svg", 5000)):
            path = fig_dir / f"{figure}.{extension}"
            check(f"Figure {extension.upper()} exists: {figure}", path.exists())
            if path.exists():
                check(
                    f"Figure {extension.upper()} nontrivial size: {figure}",
                    path.stat().st_size > min_size,
                    f"{path.stat().st_size} bytes",
                )

    for table in _active_review_tables(table_dir, tables):
        for extension in ("csv", "md", "docx"):
            check(f"Table {extension.upper()} exists: {table}", (table_dir / f"{table}.{extension}").exists())

    document = out_dir / "PrimeNet_Architecture_Publication_Draft_v2_4.docx"
    check("Integrated Publisher v2.4 DOCX exists", document.exists())
    if document.exists():
        check("Integrated Publisher v2.4 DOCX nontrivial size", document.stat().st_size > 250000, f"{document.stat().st_size} bytes")

    sections = section_paragraphs({})
    check("Fourteen numbered manuscript sections present", len(sections) == 14, f"{len(sections)} sections configured")
    check("Sixteen publication figures configured", len(FIGURE_CAPTIONS) == 16, f"{len(FIGURE_CAPTIONS)} figures configured")
    check("Eight canonical tables configured", len(tables) == 8, f"{len(tables)} tables generated")

    theory_summary = Path(r"E:\PrimeNet\Repository\observations\theory_validation\theory_validation_summary.json")
    theory_partitions = Path(r"E:\PrimeNet\Repository\observations\theory_validation\theory_validation_partition_data.csv")
    check("Theory-validation summary exists", theory_summary.is_file())
    check("Theory-validation partition dataset exists", theory_partitions.is_file())

    status = "PASSED" if all(item["status"] == "PASSED" for item in checks) else "FAILED"
    lines = ["=" * 68, "PrimeNet Publication Verification v2.4", "=" * 68]
    for item in checks:
        symbol = "OK" if item["status"] == "PASSED" else "FAIL"
        detail = f" - {item['detail']}" if item.get("detail") else ""
        lines.append(f"[{symbol}] {item['check']}{detail}")
    lines += ["=" * 68, f"Overall Status: {status}", "=" * 68]

    path = out_dir / "publication_review_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status, path, checks
