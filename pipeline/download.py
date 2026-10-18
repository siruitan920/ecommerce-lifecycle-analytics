"""Step 1: 从 Kaggle 下载原始行为日志压缩包。

数据集是公开的，不需要 Kaggle 账号：Kaggle API 的下载地址会 302 跳到
Google Cloud Storage 上的签名链接。支持断点续传，已下载完整就直接跳过。

用法：python pipeline/download.py
"""
from pathlib import Path
import sys

import requests

DATASET = "mkechinov/ecommerce-behavior-data-from-multi-category-store"
URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET}"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "archive.zip"
CHUNK = 8 * 1024 * 1024


def remote_size(session: requests.Session) -> tuple[str, int]:
    r = session.get(URL, allow_redirects=False, timeout=60)
    r.raise_for_status()
    signed = r.headers["Location"]
    head = session.head(signed, timeout=60)
    head.raise_for_status()
    return signed, int(head.headers["Content-Length"])


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    signed, total = remote_size(session)
    done = OUT.stat().st_size if OUT.exists() else 0
    if done == total:
        print(f"已存在且完整：{OUT}（{total / 1e9:.2f} GB）")
        return

    headers = {"Range": f"bytes={done}-"} if done else {}
    with session.get(signed, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        mode = "ab" if done and r.status_code == 206 else "wb"
        if mode == "wb":
            done = 0
        with open(OUT, mode) as f:
            last = -1
            for chunk in r.iter_content(CHUNK):
                f.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total)
                if pct != last and pct % 5 == 0:
                    print(f"{pct:3d}%  {done / 1e9:.2f} / {total / 1e9:.2f} GB", flush=True)
                    last = pct

    if OUT.stat().st_size != total:
        sys.exit(f"下载不完整：{OUT.stat().st_size} / {total} 字节，重跑可续传")
    print(f"完成：{OUT}")


if __name__ == "__main__":
    main()
