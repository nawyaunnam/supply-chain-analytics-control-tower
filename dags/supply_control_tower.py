from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG(
    "supply_chain_control_tower",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=45),
    },
    tags=["supply-chain", "dbt", "forecasting"],
) as dag:

    def step(name, command):
        return BashOperator(
            task_id=name,
            bash_command=f'cd /opt/project && /opt/airflow/pipeline/bin/tower {command} --target "$TOWER_TARGET"',
            append_env=True,
        )

    extract = step("extract_validate_land", "generate")
    load = step("load_warehouse", "load")
    models = step("build_test_core_marts", "build")
    intelligence = step("forecast_detect_test", "score")
    export = step("export_powerbi_inputs", "export")
    extract >> load >> models >> intelligence >> export
