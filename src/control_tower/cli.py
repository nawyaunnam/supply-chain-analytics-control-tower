import argparse
import json
import os
import subprocess
from pathlib import Path

from .contracts import CONTRACTS
from .generate import generate
from .ingest import publish
from .warehouse import load_batch


def main():
    p = argparse.ArgumentParser(description="Supply chain control tower")
    p.add_argument("command", choices=["generate", "ingest", "load", "build", "score", "export", "demo"])
    p.add_argument("--root", type=Path, default=Path(os.getenv("TOWER_ROOT", ".")))
    p.add_argument("--target", choices=["local", "postgres", "redshift"], default="local")
    p.add_argument("--source-dir", type=Path)
    p.add_argument("--batch", type=Path)
    p.add_argument("--days", type=int, default=240)
    p.add_argument("--skus", type=int, default=8)
    args = p.parse_args()
    if args.command == "ingest" and args.source_dir is None:
        p.error("ingest requires --source-dir")
    root = args.root.resolve()
    (root / "data").mkdir(parents=True, exist_ok=True)
    if args.command in ["generate", "ingest", "demo"]:
        data = (
            {n: json.loads((args.source_dir / f"{n}.json").read_text()) for n in CONTRACTS}
            if args.command == "ingest"
            else generate(args.days, args.skus)
        )
        batch = publish(
            data, root / "data/landing", source_kind="imported" if args.command == "ingest" else "synthetic"
        )
        (root / "data/latest_batch.txt").write_text(str(batch))
        print(json.dumps({"batch": str(batch)}))
    if args.command in ["load", "demo"]:
        batch = args.batch or Path((root / "data/latest_batch.txt").read_text())
        load_batch(root, batch, args.target)

    def build(selection=None):
        command = [
            "dbt",
            "build",
            "--project-dir",
            str(root / "dbt"),
            "--profiles-dir",
            str(root / "dbt"),
            "--target",
            args.target,
        ]
        if selection:
            command.extend(["--select", selection])
        subprocess.run(
            command, check=True, env={**os.environ, "DUCKDB_PATH": str(root / "data/warehouse.duckdb")}
        )

    if args.command in ["build", "demo"]:
        build()
    if args.command in ["score", "demo"]:
        from .intelligence import score

        print(json.dumps(score(root, args.target)))
        build("tag:intelligence")
    if args.command in ["export", "demo"]:
        from .report import export

        export(root, args.target)


if __name__ == "__main__":
    main()
