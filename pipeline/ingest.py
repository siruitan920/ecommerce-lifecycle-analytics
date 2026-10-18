"""Step 2: 原始 CSV → ODS 层 Parquet。

一次只解压一个月的 CSV（单月最大 9GB），转成 Parquet 后立刻删掉 CSV，
避免同时落地 14.7GB 明文。字段只做类型转换，不做任何清洗——
清洗规则全部放在 sql/ 里，保证 ODS 层可以和原始文件逐行对账。

用法：python pipeline/ingest.py [--keep-zip]
"""
import argparse
import time
import zipfile

import duckdb

from config import CSV_NAME, MONTHS, RAW_ZIP, WAREHOUSE, ods_path

COLUMNS = {
    "event_time": "VARCHAR",
    "event_type": "VARCHAR",
    "product_id": "BIGINT",
    "category_id": "BIGINT",
    "category_code": "VARCHAR",
    "brand": "VARCHAR",
    "price": "DOUBLE",
    "user_id": "BIGINT",
    "user_session": "VARCHAR",
}


def convert(csv_path, out_path) -> int:
    con = duckdb.connect()
    con.execute("SET memory_limit = '8GB'")
    con.execute(f"SET temp_directory = '{WAREHOUSE / 'tmp'}'")
    cols = ", ".join(f"'{k}': '{v}'" for k, v in COLUMNS.items())
    con.execute(f"""
        COPY (
            SELECT
                strptime(replace(event_time, ' UTC', ''), '%Y-%m-%d %H:%M:%S') AS event_time_utc,
                * EXCLUDE (event_time)
            FROM read_csv('{csv_path}', header = true, columns = {{{cols}}})
        ) TO '{out_path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 1000000)
    """)
    n = con.execute(f"SELECT COUNT(*) FROM '{out_path}'").fetchone()[0]
    con.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-zip", action="store_true", help="转换完保留压缩包")
    args = ap.parse_args()

    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    pending = [m for m in MONTHS if not ods_path(m).exists()]
    if pending and not RAW_ZIP.exists():
        raise SystemExit(f"缺少 {RAW_ZIP}，先运行 pipeline/download.py")

    for month in pending:
        t0 = time.time()
        with zipfile.ZipFile(RAW_ZIP) as zf:
            csv_path = zf.extract(CSV_NAME[month], RAW_ZIP.parent)
        try:
            n = convert(csv_path, ods_path(month))
        finally:
            (RAW_ZIP.parent / CSV_NAME[month]).unlink(missing_ok=True)
        size = ods_path(month).stat().st_size / 1e9
        print(f"{month}: {n:,} 行 → {ods_path(month).name}（{size:.2f} GB，{time.time() - t0:.0f}s）")

    for month in MONTHS:
        if month not in pending:
            print(f"{month}: 已存在 {ods_path(month).name}，跳过")

    if not args.keep_zip and RAW_ZIP.exists() and all(ods_path(m).exists() for m in MONTHS):
        RAW_ZIP.unlink()
        print(f"已删除 {RAW_ZIP.name}（需要时重跑 download.py）")


if __name__ == "__main__":
    main()
