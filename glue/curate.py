"""Glue Spark job: validate landed Parquet, compact it, register a versioned Athena database."""

import json
import re
import sys

KEYS = {
    "suppliers": ["supplier_id"],
    "products": ["sku"],
    "warehouses": ["warehouse_id"],
    "order_lines": ["line_id"],
    "shipments": ["shipment_id"],
    "inventory": ["sku", "warehouse_id", "snapshot_date"],
    "purchase_orders": ["po_id"],
}


def validate_frame(frame, name):
    from pyspark.sql import functions as f

    keys = KEYS[name]
    for key in keys:
        if frame.filter(f.col(key).isNull()).limit(1).count():
            raise ValueError(f"Null {name} key")
    if frame.groupBy(*keys).count().filter("count > 1").limit(1).count():
        raise ValueError(f"Duplicate {name} key")
    for col in frame.columns:
        if col.endswith("_qty") or col.endswith("_cents"):
            if frame.filter(f.col(col) < 0).limit(1).count():
                raise ValueError(f"Negative {name} value")
    if (
        name == "inventory"
        and frame.filter("opening_qty + received_qty - shipped_qty <> on_hand_qty").limit(1).count()
    ):
        raise ValueError("Inventory does not balance")
    return frame


def run():
    import boto3
    from awsglue.context import GlueContext
    from awsglue.job import Job
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext

    args = getResolvedOptions(sys.argv, ["JOB_NAME", "BUCKET", "BATCH_ID"])
    bucket, batch_id = args["BUCKET"], args["BATCH_ID"]
    if not re.fullmatch(r"[a-f0-9]{24}", batch_id):
        raise ValueError("Invalid batch ID")
    context = GlueContext(SparkContext.getOrCreate())
    spark = context.spark_session
    job = Job(context)
    job.init(args["JOB_NAME"], args)
    client = boto3.client("glue")
    database = "tower_" + batch_id
    s3 = boto3.client("s3")
    marker = f"curated/{batch_id}/_READY.json"
    # A rerun removes readiness first, so a failed rewrite cannot look complete.
    s3.delete_object(Bucket=bucket, Key=marker)
    try:
        client.create_database(DatabaseInput={"Name": database})
    except client.exceptions.AlreadyExistsException:
        pass
    for name in KEYS:
        frame = validate_frame(spark.read.parquet(f"s3://{bucket}/landing/{batch_id}/{name}.parquet"), name)
        path = f"s3://{bucket}/curated/{batch_id}/{name}/"
        # Four output partitions bound small-file growth in this demo; tune to 128–512 MB files at scale.
        frame.coalesce(4).write.mode("overwrite").parquet(path)
        types = {"long": "bigint", "integer": "int"}
        columns = [
            {
                "Name": field.name,
                "Type": types.get(field.dataType.simpleString(), field.dataType.simpleString()),
            }
            for field in frame.schema.fields
        ]
        table = {
            "Name": name,
            "TableType": "EXTERNAL_TABLE",
            "Parameters": {"classification": "parquet"},
            "StorageDescriptor": {
                "Columns": columns,
                "Location": path,
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                },
            },
        }
        try:
            client.create_table(DatabaseName=database, TableInput=table)
        except client.exceptions.AlreadyExistsException:
            client.update_table(DatabaseName=database, TableInput=table)
    s3.put_object(
        Bucket=bucket,
        Key=marker,
        Body=json.dumps({"database": database, "batch_id": batch_id}).encode(),
        ServerSideEncryption="AES256",
    )
    job.commit()


if __name__ == "__main__":
    run()
