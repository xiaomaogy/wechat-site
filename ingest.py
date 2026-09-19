"""把一篇微信公众号文章抓下来，落成 content/<slug>/ 三件套。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

import wxparse

PROJECT_ROOT = Path(__file__).resolve().parent
CONTENT_ROOT = PROJECT_ROOT / "content"
DEBUG_DIR = PROJECT_ROOT / "tmp"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
PAGE_HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
IMAGE_HEADERS = {"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/"}
RETRIES = 3


def fetch(url: str) -> str:
    """抓文章页 HTML，失败重试三次。"""
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, headers=PAGE_HEADERS, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception as error:  # noqa: BLE001 — 重试后统一抛出
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"抓取失败 {url}: {last_error}")


def _get_bytes(url: str) -> bytes:
    response = requests.get(url, headers=IMAGE_HEADERS, timeout=30)
    response.raise_for_status()
    return response.content


def download_images(urls: list[str], dest: Path) -> dict:
    """下载图片到 dest。单张失败只记录不中断。

    文件名是按 URL 猜的，猜不出格式时会默认 .jpg；微信正文里的装饰图标其实是
    SVG，存成 .jpg 会让浏览器按 image/jpeg 解析而裂图。所以下载完按文件头纠正
    扩展名，并把改名回报给调用方去改正文引用。

    返回 {"failed": [url...], "renamed": {旧文件名: 新文件名}}。
    """
    dest.mkdir(parents=True, exist_ok=True)
    failed: list[str] = []
    renamed: dict[str, str] = {}

    for url in urls:
        assumed = wxparse.image_filename(url)
        try:
            data = _get_bytes(url)
        except Exception as error:  # noqa: BLE001 — 单图失败不该毁掉整篇
            print(f"  WARNING 图片下载失败 {url}: {error}", file=sys.stderr)
            failed.append(url)
            continue

        name = assumed
        real_ext = wxparse.sniff_ext(data)
        if real_ext and not assumed.endswith(f".{real_ext}"):
            name = assumed.rsplit(".", 1)[0] + f".{real_ext}"
            renamed[assumed] = name

        (dest / name).write_bytes(data)

    return {"failed": failed, "renamed": renamed}


def _save_debug(url: str, html: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{wxparse.wx_id(url)}.html"
    path.write_text(html, encoding="utf-8")
    return path


def existing_dir(url: str, content_root: Path) -> Path | None:
    """这篇抓过了吗？slug 末尾就是微信短链 id，拿它找，不用先联网取日期。"""
    if not content_root.is_dir():
        return None
    matches = sorted(content_root.glob(f"*-{wxparse.wx_id(url)}"))
    return matches[0] if matches else None


def ingest(url: str, content_root: Path, skip_existing: bool = False) -> Path:
    if skip_existing:
        already = existing_dir(url, content_root)
        if already is not None:
            print(f"· 跳过（已有） {already.name}")
            return already

    html = fetch(url)
    try:
        article = wxparse.parse(html)
    except wxparse.ArticleUnavailable:
        saved = _save_debug(url, html)
        print(f"  原始 HTML 已存到 {saved}，可人工排查", file=sys.stderr)
        raise

    slug = wxparse.slug_for(url, article.published)
    out_dir = content_root / slug
    if out_dir.exists():
        shutil.rmtree(out_dir)
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True)

    image_urls = list(article.image_urls)
    cover_name = ""
    if article.cover_url:
        cover_name = wxparse.image_filename(article.cover_url)
        if article.cover_url not in image_urls:
            image_urls.append(article.cover_url)

    downloaded = download_images(image_urls, images_dir)
    failed = downloaded["failed"]
    if cover_name and article.cover_url in failed:
        cover_name = ""

    body_html = article.body_html
    for old_name, new_name in downloaded["renamed"].items():
        body_html = body_html.replace(f"images/{old_name}", f"images/{new_name}")
    cover_name = downloaded["renamed"].get(cover_name, cover_name)

    (out_dir / "body.html").write_text(body_html, encoding="utf-8")
    meta = {
        "slug": slug,
        "title": article.title,
        "author": article.author,
        "published": article.published,
        "source_url": url,
        "cover": cover_name,
        "fetched_at": datetime.now(wxparse.CST).isoformat(timespec="seconds"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"✓ {article.title} → {out_dir}")
    if failed:
        print(f"  {len(failed)} 张图片没下下来，页面上会缺图", file=sys.stderr)
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取微信公众号文章到 content/")
    parser.add_argument("urls", nargs="+", help="mp.weixin.qq.com/s/... 链接")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="content/ 里已有的就跳过，不重新抓",
    )
    args = parser.parse_args(argv)

    failures = 0
    for url in args.urls:
        try:
            ingest(url, CONTENT_ROOT, skip_existing=args.skip_existing)
        except Exception as error:  # noqa: BLE001 — 一篇失败不该中断其余
            print(f"✗ {url}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
