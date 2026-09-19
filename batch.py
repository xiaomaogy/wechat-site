"""按清单批量抓取文章：限速、断点续传、失败只记录不中断。"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Callable

import ingest

PROJECT_ROOT = Path(__file__).resolve().parent

# 微信对批量抓取有频率限制，篇与篇之间必须留够间隔。
MIN_DELAY = 3.0
MAX_DELAY = 6.0


def read_urls(path: Path) -> list[str]:
    """一行一个链接。空行和 # 开头的注释忽略，重复的只留第一次。"""
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line not in urls:
            urls.append(line)
    return urls


def run(
    urls: list[str],
    content_root: Path,
    *,
    sleeper: Callable[[float], None],
    min_delay: float = MIN_DELAY,
    max_delay: float = MAX_DELAY,
) -> dict:
    """逐篇抓。返回 {"done": [...], "skipped": [...], "failed": [(url, 原因)]}。

    已经抓过的直接跳过，所以整条命令可以重复跑——被限流中断之后接着跑就是续传。
    """
    done: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    fetched_any = False

    for index, url in enumerate(urls, start=1):
        if ingest.existing_dir(url, content_root) is not None:
            skipped.append(url)
            continue

        if fetched_any:
            sleeper(random.uniform(min_delay, max_delay))
        fetched_any = True

        print(f"[{index}/{len(urls)}] {url}")
        try:
            ingest.ingest(url, content_root)
            done.append(url)
        except Exception as error:  # noqa: BLE001 — 一篇失败不该中断整批
            print(f"  ✗ {error}", file=sys.stderr)
            failed.append((url, str(error)))

    return {"done": done, "skipped": skipped, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按清单批量抓取微信公众号文章")
    parser.add_argument("listing", type=Path, help="每行一个 mp.weixin.qq.com 链接的文本文件")
    parser.add_argument("--min-delay", type=float, default=MIN_DELAY)
    parser.add_argument("--max-delay", type=float, default=MAX_DELAY)
    args = parser.parse_args(argv)

    # 输出重定向到文件时 Python 会整块缓冲，后台跑就看不到进度。
    sys.stdout.reconfigure(line_buffering=True)

    import time

    urls = read_urls(args.listing)
    print(f"清单里 {len(urls)} 篇\n")

    result = run(
        urls,
        ingest.CONTENT_ROOT,
        sleeper=time.sleep,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    print(
        f"\n新抓 {len(result['done'])} 篇"
        f"，跳过 {len(result['skipped'])} 篇"
        f"，失败 {len(result['failed'])} 篇"
    )
    if result["failed"]:
        print("\n失败的（重跑本命令会自动只抓这些）：", file=sys.stderr)
        for url, reason in result["failed"]:
            print(f"  {url}  —  {reason}", file=sys.stderr)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
