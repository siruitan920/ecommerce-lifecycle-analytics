"""Step 3: 按编号顺序执行 sql/*.sql，在 DuckDB 里建 ODS → DWD → DIM → DWS → ADS 各层。

SQL 里的 {{TZ}} {{START}} {{END}} {{ODS_FILES}} 由 config.py 统一替换，
口径参数只有一处来源。

用法：python pipeline/transform.py [起始编号]   例：python pipeline/transform.py 08
"""
import re
import sys
import time

from config import MONTHS, SQL_DIR, TZ_OFFSET_HOURS, connect, ods_path

PARAMS = {
    "TZ": str(TZ_OFFSET_HOURS),
    "START": f"{MONTHS[0]}-01",
    "END": "2019-11-30",
    "ODS_FILES": "[" + ", ".join(f"'{ods_path(m)}'" for m in MONTHS) + "]",
}


def render(sql: str) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: PARAMS[m.group(1)], sql)


def main() -> None:
    start = sys.argv[1] if len(sys.argv) > 1 else "00"
    con = connect()
    for path in sorted(SQL_DIR.glob("*.sql")):
        if path.name[:2] < start:
            continue
        t0 = time.time()
        con.execute(render(path.read_text()))
        m = re.search(r"CREATE OR REPLACE (?:TABLE|VIEW) (\w+)", path.read_text())
        rows = f"{con.execute(f'SELECT COUNT(*) FROM {m.group(1)}').fetchone()[0]:>12,} 行" if m else ""
        print(f"{path.name:36s} {rows}  {time.time() - t0:5.0f}s", flush=True)
    con.close()


if __name__ == "__main__":
    main()
