"""管道共用的路径和参数。"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_ZIP = ROOT / "data" / "raw" / "archive.zip"
WAREHOUSE = ROOT / "data" / "warehouse"
DB_PATH = WAREHOUSE / "warehouse.duckdb"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"
DASHBOARD_DATA = ROOT / "dashboard" / "data"

MONTHS = ["2019-10", "2019-11"]
CSV_NAME = {"2019-10": "2019-Oct.csv", "2019-11": "2019-Nov.csv"}

# 数据集只说明 event_time 是 UTC，没给店铺所在时区。
# 按小时流量曲线推断本地时区为 UTC+3（推断过程见 notebooks/01），
# 业务日期、时段都按这个偏移切分。
TZ_OFFSET_HOURS = 3

# 大促窗口：数据里没有活动日历，按日 GMV 异常抬升识别（见 notebooks/06）
CAMPAIGN_START = "2019-11-15"
CAMPAIGN_END = "2019-11-17"


def ods_path(month: str) -> Path:
    return WAREHOUSE / f"ods_events_{month}.parquet"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=read_only)
    con.execute("SET memory_limit = '10GB'")
    con.execute(f"SET temp_directory = '{WAREHOUSE / 'tmp'}'")
    con.execute("SET preserve_insertion_order = false")
    return con
