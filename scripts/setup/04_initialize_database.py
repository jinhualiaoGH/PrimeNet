from pathlib import Path
from datetime import datetime
import csv
import json
import platform
import sqlite3


ROOT = Path("C:/PrimeNet")
CATALOG = ROOT / "catalog"
LOGS = ROOT / "logs"

DB_PATH = CATALOG / "primenet_catalog.db"
ASSET_REGISTRY_CSV = CATALOG / "asset_registry.csv"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect_db() -> sqlite3.Connection:
    CATALOG.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        asset_id TEXT PRIMARY KEY,
        source_asset_id TEXT,
        asset_type TEXT,
        asset_name TEXT,
        relative_path TEXT,
        category TEXT,
        dataset_role TEXT,
        extension TEXT,
        size_bytes INTEGER,
        size_mb REAL,
        created_at TEXT,
        modified_at TEXT,
        registered_at TEXT,
        status TEXT,
        provenance TEXT,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS datasets (
        dataset_id TEXT PRIMARY KEY,
        asset_id TEXT,
        dataset_name TEXT,
        dataset_type TEXT,
        dataset_role TEXT,
        relative_path TEXT,
        size_bytes INTEGER,
        created_at TEXT,
        registered_at TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS instruments (
        instrument_id TEXT PRIMARY KEY,
        instrument_name TEXT,
        instrument_type TEXT,
        version TEXT,
        script_path TEXT,
        description TEXT,
        registered_at TEXT,
        status TEXT,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS observations (
        observation_id TEXT PRIMARY KEY,
        instrument_id TEXT,
        dataset_id TEXT,
        observation_name TEXT,
        parameters_json TEXT,
        output_path TEXT,
        runtime_sec REAL,
        created_at TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(instrument_id) REFERENCES instruments(instrument_id),
        FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS experiments (
        experiment_id TEXT PRIMARY KEY,
        experiment_name TEXT,
        description TEXT,
        start_time TEXT,
        end_time TEXT,
        status TEXT,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS atlases (
        atlas_id TEXT PRIMARY KEY,
        atlas_name TEXT,
        atlas_type TEXT,
        description TEXT,
        source_observation_ids TEXT,
        created_at TEXT,
        status TEXT,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS publications (
        publication_id TEXT PRIMARY KEY,
        title TEXT,
        publication_type TEXT,
        manuscript_path TEXT,
        related_assets TEXT,
        related_observations TEXT,
        created_at TEXT,
        status TEXT,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS figures (
        figure_id TEXT PRIMARY KEY,
        figure_name TEXT,
        figure_path TEXT,
        source_observation_id TEXT,
        related_publication_id TEXT,
        created_at TEXT,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(source_observation_id) REFERENCES observations(observation_id),
        FOREIGN KEY(related_publication_id) REFERENCES publications(publication_id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS registry_manifest (
        registry_id TEXT PRIMARY KEY,
        registry_name TEXT,
        table_name TEXT,
        description TEXT,
        created_at TEXT,
        updated_at TEXT,
        record_count INTEGER,
        status TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS setup_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        script TEXT,
        action TEXT,
        status TEXT,
        details TEXT
    );
    """)

    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    index_sql = [
        "CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);",
        "CREATE INDEX IF NOT EXISTS idx_assets_path ON assets(relative_path);",
        "CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);",
        "CREATE INDEX IF NOT EXISTS idx_datasets_role ON datasets(dataset_role);",
        "CREATE INDEX IF NOT EXISTS idx_observations_instrument ON observations(instrument_id);",
        "CREATE INDEX IF NOT EXISTS idx_observations_dataset ON observations(dataset_id);",
        "CREATE INDEX IF NOT EXISTS idx_figures_publication ON figures(related_publication_id);",
    ]

    for sql in index_sql:
        cur.execute(sql)

    conn.commit()


def to_int(value) -> int:
    try:
        if value in ("", None):
            return 0
        return int(float(value))
    except Exception:
        return 0


def to_float(value) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def read_asset_registry() -> list[dict]:
    if not ASSET_REGISTRY_CSV.exists():
        raise FileNotFoundError(
            f"Missing asset registry: {ASSET_REGISTRY_CSV}\n"
            "Please run 03_register_assets.py first."
        )

    with ASSET_REGISTRY_CSV.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def import_assets(conn: sqlite3.Connection, records: list[dict]) -> None:
    cur = conn.cursor()

    cur.execute("DELETE FROM assets;")

    for r in records:
        cur.execute("""
        INSERT OR REPLACE INTO assets (
            asset_id,
            source_asset_id,
            asset_type,
            asset_name,
            relative_path,
            category,
            dataset_role,
            extension,
            size_bytes,
            size_mb,
            created_at,
            modified_at,
            registered_at,
            status,
            provenance,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            r.get("asset_id", ""),
            r.get("source_asset_id", ""),
            r.get("asset_type", ""),
            r.get("asset_name", ""),
            r.get("relative_path", ""),
            r.get("category", ""),
            r.get("dataset_role", ""),
            r.get("extension", ""),
            to_int(r.get("size_bytes", 0)),
            to_float(r.get("size_mb", 0)),
            r.get("created_at", ""),
            r.get("modified_at", ""),
            r.get("registered_at", ""),
            r.get("status", ""),
            r.get("provenance", ""),
            r.get("notes", ""),
        ))

    conn.commit()
    print(f"  imported assets: {len(records)}")


def import_datasets_from_assets(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute("DELETE FROM datasets;")

    cur.execute("""
    SELECT asset_id, asset_name, asset_type, dataset_role, relative_path,
           size_bytes, created_at
    FROM assets
    WHERE asset_type LIKE 'dataset_%';
    """)

    rows = cur.fetchall()

    for i, row in enumerate(rows, start=1):
        asset_id, asset_name, asset_type, dataset_role, relative_path, size_bytes, created_at = row

        dataset_id = f"DATASET{i:06d}"

        cur.execute("""
        INSERT OR REPLACE INTO datasets (
            dataset_id,
            asset_id,
            dataset_name,
            dataset_type,
            dataset_role,
            relative_path,
            size_bytes,
            created_at,
            registered_at,
            status,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            dataset_id,
            asset_id,
            asset_name,
            asset_type,
            dataset_role,
            relative_path,
            size_bytes,
            created_at,
            now(),
            "registered",
            "Imported automatically from asset registry.",
        ))

    conn.commit()
    print(f"  imported datasets: {len(rows)}")


def register_default_instruments(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    instruments = [
        ("INST000001", "Entropy Observatory", "observatory", "1.0", "observatories/entropy", "Measures entropy of prime event languages."),
        ("INST000002", "Transition Observatory", "observatory", "1.0", "observatories/transition", "Measures transition structure among arithmetic states."),
        ("INST000003", "Invariant Observatory", "observatory", "1.0", "observatories/invariant", "Searches for stable prime information invariants."),
        ("INST000004", "Runtime Observatory", "observatory", "1.0", "observatories/runtime", "Tracks runtime and computational scaling."),
        ("INST000005", "Taxonomy Observatory", "observatory", "1.0", "observatories/taxonomy", "Classifies gap and event information families."),
        ("INST000006", "Geometry Observatory", "observatory", "1.0", "observatories/geometry", "Studies information geometry of prime structures."),
        ("INST000007", "Spectrum Observatory", "observatory", "1.0", "observatories/spectrum", "Analyzes gap and event spectra."),
        ("INST000008", "Validation Observatory", "observatory", "1.0", "observatories/validation", "Runs validation and counterexample searches."),
        ("INST000009", "Compression Observatory", "observatory", "1.0", "observatories/compression", "Measures compressibility and predictive structure."),
        ("INST000010", "Flow Observatory", "observatory", "1.0", "observatories/flow", "Studies directed flow among gap states."),
    ]

    for item in instruments:
        cur.execute("""
        INSERT OR REPLACE INTO instruments (
            instrument_id,
            instrument_name,
            instrument_type,
            version,
            script_path,
            description,
            registered_at,
            status,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            item[0],
            item[1],
            item[2],
            item[3],
            item[4],
            item[5],
            now(),
            "active",
            "Registered by 04_initialize_database.py",
        ))

    conn.commit()
    print(f"  registered instruments: {len(instruments)}")


def update_registry_manifest(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    registries = [
        ("REG000001", "Asset Registry", "assets", "All registered PrimeNet assets."),
        ("REG000002", "Dataset Registry", "datasets", "Registered datasets derived from assets."),
        ("REG000003", "Instrument Registry", "instruments", "Registered PrimeNet observatory instruments."),
        ("REG000004", "Observation Registry", "observations", "Completed observatory observations."),
        ("REG000005", "Experiment Registry", "experiments", "PrimeNet experiment records."),
        ("REG000006", "Atlas Registry", "atlases", "PrimeNet information atlases."),
        ("REG000007", "Publication Registry", "publications", "Manuscripts and publications."),
        ("REG000008", "Figure Registry", "figures", "Publication and analysis figures."),
    ]

    for registry_id, registry_name, table_name, description in registries:
        cur.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cur.fetchone()[0]

        cur.execute("""
        INSERT OR REPLACE INTO registry_manifest (
            registry_id,
            registry_name,
            table_name,
            description,
            created_at,
            updated_at,
            record_count,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            registry_id,
            registry_name,
            table_name,
            description,
            now(),
            now(),
            count,
            "active",
        ))

    conn.commit()


def write_setup_history(conn: sqlite3.Connection, details: dict) -> None:
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO setup_history (
        timestamp,
        script,
        action,
        status,
        details
    ) VALUES (?, ?, ?, ?, ?);
    """, (
        now(),
        "04_initialize_database.py",
        "initialize_database",
        "completed",
        json.dumps(details),
    ))

    conn.commit()


def count_table(conn: sqlite3.Connection, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table};")
    return int(cur.fetchone()[0])


def make_summary(conn: sqlite3.Connection) -> dict:
    tables = [
        "assets",
        "datasets",
        "instruments",
        "observations",
        "experiments",
        "atlases",
        "publications",
        "figures",
        "registry_manifest",
    ]

    counts = {table: count_table(conn, table) for table in tables}

    return {
        "project": "PrimeNet",
        "script": "04_initialize_database.py",
        "created_at": now(),
        "database_path": str(DB_PATH),
        "table_counts": counts,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


def write_summary_json(summary: dict) -> None:
    path = CATALOG / "database_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  wrote: {path}")


def write_log(summary: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)

    path = LOGS / "04_initialize_database.log"

    with path.open("a", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"[{now()}] 04_initialize_database.py completed\n")
        f.write(f"database={summary['database_path']}\n")
        for table, count in summary["table_counts"].items():
            f.write(f"{table}={count}\n")

    print(f"  updated log: {path}")


def update_manifest(summary: dict) -> None:
    manifest_path = ROOT / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "project": "PrimeNet",
            "version": "1.0.0",
            "created_at": now(),
        }

    manifest["last_updated_at"] = now()

    manifest["database"] = {
        "path": "catalog/primenet_catalog.db",
        "summary": "catalog/database_summary.json",
        "last_initialized_at": summary["created_at"],
        "table_counts": summary["table_counts"],
    }

    setup_history = manifest.setdefault("setup_history", [])
    setup_history.append(
        {
            "timestamp": now(),
            "script": "04_initialize_database.py",
            "action": "initialize_database",
            "status": "completed",
            "database": "catalog/primenet_catalog.db",
        }
    )

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  updated manifest: {manifest_path}")


def print_summary(summary: dict) -> None:
    print("\nPrimeNet Database Summary")
    print("-" * 80)
    print(f"Database: {summary['database_path']}")

    print("\nTable counts:")
    for table, count in summary["table_counts"].items():
        print(f"  {table:20s} {count}")


def main() -> None:
    print("=" * 80)
    print("PrimeNet Catalog Database Initializer v1.0")
    print("=" * 80)

    records = read_asset_registry()

    with connect_db() as conn:
        print("\nCreating database tables...")
        create_tables(conn)

        print("\nCreating indexes...")
        create_indexes(conn)

        print("\nImporting asset registry...")
        import_assets(conn, records)

        print("\nImporting datasets from assets...")
        import_datasets_from_assets(conn)

        print("\nRegistering default observatory instruments...")
        register_default_instruments(conn)

        print("\nUpdating registry manifest...")
        update_registry_manifest(conn)

        summary = make_summary(conn)
        write_setup_history(conn, summary)

    write_summary_json(summary)
    update_manifest(summary)
    write_log(summary)
    print_summary(summary)

    print("\n" + "=" * 80)
    print("PrimeNet catalog database initialized successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()