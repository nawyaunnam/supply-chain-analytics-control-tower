"""Bounded snapshot loading with atomic replacement. SQL identifiers are registry-controlled."""

import os
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .contracts import CONTRACTS
from .ingest import verify

INTELLIGENCE = {
    "forecasts": {
        "sku": "VARCHAR",
        "warehouse_id": "VARCHAR",
        "forecast_date": "DATE",
        "training_cutoff": "DATE",
        "model": "VARCHAR",
        "predicted_qty": "DOUBLE PRECISION",
        "lower_qty": "DOUBLE PRECISION",
        "upper_qty": "DOUBLE PRECISION",
    },
    "backtests": {
        "sku": "VARCHAR",
        "warehouse_id": "VARCHAR",
        "origin_date": "DATE",
        "target_date": "DATE",
        "model": "VARCHAR",
        "predicted_qty": "DOUBLE PRECISION",
        "actual_qty": "DOUBLE PRECISION",
    },
    "anomalies": {
        "sku": "VARCHAR",
        "warehouse_id": "VARCHAR",
        "date_day": "DATE",
        "metric": "VARCHAR",
        "observed": "DOUBLE PRECISION",
        "expected": "DOUBLE PRECISION",
        "robust_score": "DOUBLE PRECISION",
        "severity": "VARCHAR",
    },
}


@contextmanager
def connect(root, target="local"):
    if target == "local":
        con = duckdb.connect(str(Path(root) / "data/warehouse.duckdb"))
    elif target == "postgres":
        import psycopg

        con = psycopg.connect(os.environ["POSTGRES_DSN"])
    elif target == "redshift":
        import redshift_connector

        con = redshift_connector.connect(
            host=os.environ["REDSHIFT_HOST"],
            database=os.environ["REDSHIFT_DATABASE"],
            user=os.environ["REDSHIFT_USER"],
            password=os.environ["REDSHIFT_PASSWORD"],
            port=int(os.getenv("REDSHIFT_PORT", "5439")),
            ssl=True,
        )
    else:
        raise ValueError("Unsupported warehouse")
    try:
        yield con
    finally:
        con.close()


def execute(con, sql, params=None):
    cur = con if isinstance(con, duckdb.DuckDBPyConnection) else con.cursor()
    cur.execute(sql, params) if params else cur.execute(sql)
    return cur


def init_intelligence(con):
    for name, cols in INTELLIGENCE.items():
        execute(
            con, f"create table if not exists raw.{name} ({', '.join(k + ' ' + v for k, v in cols.items())})"
        )


def sql_type(dtype):
    if pa.types.is_integer(dtype):
        return "BIGINT"
    if pa.types.is_date(dtype):
        return "DATE"
    if pa.types.is_timestamp(dtype):
        return "TIMESTAMP"
    return "VARCHAR"


def load_batch(root, batch, target="local"):
    batch = Path(batch)
    verify(batch)
    if target == "redshift":
        from .cloud import load_redshift

        load_redshift(root, batch)
        return
    with connect(root, target) as con:
        execute(con, "begin")
        try:
            execute(con, "create schema if not exists raw")
            for name in CONTRACTS:
                arrow = pq.read_table(batch / f"{name}.parquet")
                cols = {f.name: sql_type(f.type) for f in arrow.schema}
                if target == "local":
                    execute(
                        con,
                        f"create or replace table raw.{name} as select * from read_parquet(?)",
                        [str(batch / f"{name}.parquet")],
                    )
                else:
                    execute(
                        con,
                        f"create table if not exists raw.{name} ({', '.join(k + ' ' + v for k, v in cols.items())})",
                    )
                    execute(con, f"delete from raw.{name}")
                    rows = [tuple(r[c] for c in cols) for r in arrow.to_pylist()]
                    con.cursor().executemany(
                        f"insert into raw.{name} values ({','.join(['%s'] * len(cols))})", rows
                    )
            init_intelligence(con)
            # Forecasts for a previous source snapshot must not survive a new load.
            for name in INTELLIGENCE:
                execute(con, f"delete from raw.{name}")
            con.commit()
        except Exception:
            con.rollback()
            raise


def read_table(root, target, name):
    if name not in ["fct_demand_daily", "fct_inventory_daily", "fct_delivery_daily"]:
        raise ValueError("Unsupported scoring input")
    with connect(root, target) as con:
        cur = execute(con, f"select * from analytics.{name}")
        return pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])


def save_intelligence(root, target, results):
    with connect(root, target) as con:
        execute(con, "begin")
        try:
            for name, cols in INTELLIGENCE.items():
                execute(con, f"delete from raw.{name}")
                rows = [tuple(r[k] for k in cols) for r in results[name]]
                if rows:
                    marker = "?" if target == "local" else "%s"
                    cur = con if target == "local" else con.cursor()
                    cur.executemany(f"insert into raw.{name} values ({','.join([marker] * len(cols))})", rows)
            con.commit()
        except Exception:
            con.rollback()
            raise
