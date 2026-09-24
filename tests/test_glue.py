import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_SPARK_TESTS") != "1", reason="Spark runtime job runs in CI")


def test_glue_validation_rejects_duplicates_and_accepts_valid_rows():
    from pyspark.sql import SparkSession

    path = Path(__file__).resolve().parents[1] / "glue/curate.py"
    spec = importlib.util.spec_from_file_location("curate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    spark = SparkSession.builder.master("local[2]").appName("tower-tests").getOrCreate()
    try:
        frame = spark.createDataFrame(
            [("S1", "Supplier", 4)], "supplier_id string,supplier_name string,target_lead_days int"
        )
        assert module.validate_frame(frame, "suppliers").count() == 1
        with pytest.raises(ValueError, match="Duplicate"):
            module.validate_frame(frame.union(frame), "suppliers")
    finally:
        spark.stop()
