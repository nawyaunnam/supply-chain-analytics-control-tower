"""Opt-in AWS path. Credentials use the AWS default chain and explicit Redshift environment settings."""

import os
import re
import time
from pathlib import Path

import pyarrow.parquet as pq

from .contracts import CONTRACTS
from .ingest import verify
from .warehouse import INTELLIGENCE, connect, execute, init_intelligence, sql_type


def load_redshift(root, batch):
    import boto3

    batch = Path(batch)
    manifest = verify(batch)
    batch_id = manifest["batch_id"]
    if not re.fullmatch(r"[a-f0-9]{24}", batch_id):
        raise ValueError("Invalid batch ID")
    bucket = os.environ["TOWER_BUCKET"]
    role = os.environ["REDSHIFT_COPY_ROLE"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Invalid S3 bucket")
    if not re.fullmatch(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9_+=,.@/-]+", role):
        raise ValueError("Invalid COPY role")
    s3 = boto3.client("s3")
    prefix = f"landing/{batch_id}"
    for path in sorted(batch.glob("*.parquet")):
        s3.upload_file(
            str(path), bucket, f"{prefix}/{path.name}", ExtraArgs={"ServerSideEncryption": "AES256"}
        )
    s3.upload_file(
        str(batch / "manifest.json"),
        bucket,
        f"{prefix}/manifest.json",
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    glue = boto3.client("glue")
    job = os.environ["GLUE_JOB_NAME"]
    run = glue.start_job_run(JobName=job, Arguments={"--BUCKET": bucket, "--BATCH_ID": batch_id})["JobRunId"]
    deadline = time.monotonic() + 1800
    while True:
        state = glue.get_job_run(JobName=job, RunId=run)["JobRun"]["JobRunState"]
        if state == "SUCCEEDED":
            break
        if state in ["FAILED", "STOPPED", "TIMEOUT", "ERROR", "EXPIRED"]:
            raise RuntimeError(f"Glue failed: {state}")
        if time.monotonic() > deadline:
            glue.batch_stop_job_run(JobName=job, JobRunIds=[run])
            raise TimeoutError("Glue exceeded 30-minute run budget")
        time.sleep(10)
    s3.head_object(Bucket=bucket, Key=f"curated/{batch_id}/_READY.json")
    with connect(root, "redshift") as con:
        execute(con, "create schema if not exists raw")
        for name in CONTRACTS:
            columns = [(f.name, sql_type(f.type)) for f in pq.read_schema(batch / f"{name}.parquet")]
            execute(
                con, f"create table if not exists raw.{name} ({', '.join(n + ' ' + t for n, t in columns)})"
            )
            execute(con, f"create temp table load_{name} (like raw.{name})")
            # Paths and role are tightly validated. The Glue output preserves Parquet column order.
            execute(
                con,
                f"copy load_{name} from 's3://{bucket}/curated/{batch_id}/{name}/' iam_role '{role}' format as parquet",
            )
        init_intelligence(con)
        con.commit()
        execute(con, "begin")
        try:
            for name in CONTRACTS:
                execute(con, f"delete from raw.{name}")
                execute(con, f"insert into raw.{name} select * from load_{name}")
            for name in INTELLIGENCE:
                execute(con, f"delete from raw.{name}")
            con.commit()
        except Exception:
            con.rollback()
            raise
