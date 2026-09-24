# Run and deploy

## Local demo

Python 3.11–3.13:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
tower demo
pytest -q
python -m http.server 8082 --directory artifacts
```

The demo generates and validates data, atomically loads raw tables, builds/tests dbt marts, forecasts/detects anomalies, rebuilds intelligence marts, and exports CSVs plus dashboard.html. Individual commands: `generate`, `ingest`, `load`, `build`, `score`, `export`. `score` requires core marts and at least 84 daily observations per series. `tower demo --days 84 --skus 2` is a smaller smoke run. Activate the virtual environment so dbt is on PATH.

## ERP exports

Supply seven JSON arrays named suppliers.json, products.json, warehouses.json, order_lines.json, shipments.json, inventory.json and purchase_orders.json, following `src/control_tower/contracts.py`. Use ISO dates, integer quantities and USD cents. Include a complete daily inventory spine, opening/closing balances and explicit cancelled lines. Duplicate natural keys fail validation; deduplicate revisions in the source adapter instead of silently discarding them.

```bash
tower ingest --source-dir /path/to/exports
tower load
tower build
tower score
tower export
```

Source batches and real-data outputs are gitignored. Do not copy real data into docs/demo or commit an exported dashboard from a live ERP.

## PostgreSQL

`docker compose --profile postgres up -d postgres` exposes a development-only service on localhost:5433. It uses `local-demo-only` unless PGPASSWORD is set; replace this for any non-demo use. Use a fresh dedicated database, because loads replace tables in the raw schema.

```bash
export PGHOST=localhost PGPORT=5433 PGUSER=tower PGDATABASE=tower PGPASSWORD=local-demo-only
export POSTGRES_DSN=postgresql://tower:local-demo-only@localhost:5433/tower
tower demo --target postgres
```

PG* variables configure dbt; POSTGRES_DSN configures the Python loader. They must refer to the same database. Snapshot replacement uses DELETE/INSERT inside one transaction; replay does not duplicate records. The CI postgres job executes the full pipeline against PostgreSQL 16, not a mock.

## Docker and Airflow

```bash
docker compose up --build pipeline preview
docker compose --profile airflow up --build airflow
```

Preview: localhost:8082/dashboard.html. Airflow: localhost:8080. The standalone Airflow command creates development credentials; read its logs/generated password file. Unpause supply_chain_control_tower. Tasks retry twice, have a 45-minute limit and one active DAG run. Separate volumes prevent the standalone demo and Airflow from writing the same DuckDB file. For production use an external metadata database, managed secret backend and appropriate executor/HA deployment.

## AWS: S3 → Glue → Athena/Redshift → dbt

Cloud resources are **not deployed by this repository or CI**. Provisioning incurs costs; review the template before applying it.

1. Upload glue/curate.py to an existing private script bucket. Deploy aws/infrastructure.yaml with that script's bucket/key. It creates an encrypted/private/versioned data bucket, Glue job and IAM role, and an Athena workgroup with a 1 GiB scan limit. The managed AWSGlueServiceRole policy is a demo starting point; restrict catalog/log permissions for your organization.
2. Supply a dedicated existing Redshift database and service user. Grant schema/table creation only in raw and analytics. Attach a Redshift COPY IAM role with read access to the curated data prefix; its trust policy must allow Redshift. This repo deliberately does not create a Redshift cluster.
3. Install `pip install -e '.[cloud]'`. Export the variables listed in .env.example using your secret store/AWS workload role. The CLI does not automatically source .env. Give the caller S3 landing write/read and Glue StartJobRun/GetJobRun/BatchStopJobRun permissions. No keys are committed.
4. Run `tower generate`, `tower load --target redshift`, `tower build --target redshift`, `tower score --target redshift`, `tower export --target redshift`.
5. Loading uploads verified Parquet and its manifest, runs Glue, waits for completion/readiness, COPYs to Redshift temporary tables and atomically replaces the complete raw snapshot. Intelligence outputs are invalidated until rescored. Glue's job is limited to one active run; orchestration must serialize writers to the same Redshift schema.
6. For Athena, choose the **tower_<batch_id>** Glue database only after curated/<batch_id>/_READY.json exists. Each batch has independent table locations, avoiding cross-batch mixing. aws/athena_queries.sql demonstrates exploration. dbt builds its tested marts on Redshift, not Athena, in this implementation.
7. Configure Power BI's Redshift connection or use the exported CSVs. Establish credentials in Power BI Desktop/Service; do not embed them in M.

The batch-versioned layout makes replay/recovery explicit but grows the S3/catalog footprint. Define retention and catalog cleanup before long-running deployments. Glue uses four output files per table at most for this sample; at scale tune file sizes and date partitions rather than copying the demo setting blindly. A failed rewrite removes readiness until every table is complete. S3/Glue catalog updates are not one multi-table transaction; readiness is the consumer barrier.

## Official references

- [AWS Glue versions](https://docs.aws.amazon.com/glue/latest/dg/release-notes.html)
- [Athena and Glue catalog](https://docs.aws.amazon.com/athena/latest/ug/using-athena-sql.html)
- [Athena data optimization](https://docs.aws.amazon.com/athena/latest/ug/performance-tuning-data-optimization-techniques.html)
- [Airflow Docker deployment](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)
- [Power BI project models](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
