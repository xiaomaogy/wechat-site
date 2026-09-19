"""解析微信公众号文章 HTML 的纯函数集合。这个模块不联网。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

CST = timezone(timedelta(hours=8))

DELETED_MARKERS = (
    "该内容已被发布者删除",
    "此内容因违规无法查看",
    "该公众号已迁移",
    "参数错误",
)

_CT_RE = re.compile(r"var\s+(?:ct|create_time)\s*=\s*[\"'](\d{9,11})[\"']")
_MSG_TITLE_RE = re.compile(r"var\s+msg_title\s*=\s*(['\"])(.*?)\1", re.S)
_DATE_TEXT_RE = re.compile(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})")
_WX_ID_RE = re.compile(r"/s/([A-Za-z0-9_-]+)")


class ArticleUnavailable(Exception):
    """页面不是一篇可读的文章（被删、需要验证、字段缺失）。"""


@dataclass
class ParsedArticle:
    title: str
    author: str
    published: str
    cover_url: str
    body_html: str
    image_urls: list[str]


def _meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    if not tag:
        return ""
    return (tag.get("content") or "").strip()


def extract_published(html: str, soup: BeautifulSoup) -> str:
    """返回 YYYY-MM-DD。微信的 ct 是 unix 秒，按北京时间换算。"""
    match = _CT_RE.search(html)
    if match:
        return datetime.fromtimestamp(int(match.group(1)), CST).date().isoformat()

    node = soup.find(id="publish_time")
    if node:
        text_match = _DATE_TEXT_RE.search(node.get_text(strip=True))
        if text_match:
            year, month, day = (int(part) for part in text_match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"

    raise ArticleUnavailable("页面里找不到发布时间")


def wx_id(url: str) -> str:
    match = _WX_ID_RE.search(url)
    if match:
        return match.group(1)
    raise ValueError(f"无法从链接提取文章 id: {url}")


def slug_for(url: str, published: str) -> str:
    return f"{published}-{wx_id(url)}"


_FMT_RE = re.compile(r"wx_fmt=([A-Za-z0-9]+)")
_KNOWN_EXTS = ("png", "gif", "webp", "jpg")


def image_filename(url: str) -> str:
    """图片落地后的文件名。用 URL 的 sha1 前 12 位，保证同一张图只存一份。"""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]

    match = _FMT_RE.search(url)
    ext = match.group(1).lower() if match else url.rsplit(".", 1)[-1].lower()
    if ext == "jpeg":
        ext = "jpg"
    if ext not in _KNOWN_EXTS:
        ext = "jpg"

    return f"{digest}.{ext}"


def clean_body(node) -> tuple[str, list[str]]:
    """去掉噪声标签，把图片指向本地 images/，返回（HTML, 原始图片 URL 列表）。"""
    for junk in node.find_all(["script", "style", "noscript"]):
        junk.decompose()

    urls: list[str] = []
    for img in node.find_all("img"):
        src = (img.get("data-src") or img.get("src") or "").strip()
        img.attrs.pop("data-src", None)
        if not src.startswith("http"):
            img.decompose()
            continue
        if src not in urls:
            urls.append(src)
        img["src"] = f"images/{image_filename(src)}"
        img["loading"] = "lazy"

    return node.decode_contents(), urls


def parse(html: str) -> ParsedArticle:
    for marker in DELETED_MARKERS:
        if marker in html:
            raise ArticleUnavailable(f"页面提示：{marker}")

    soup = BeautifulSoup(html, "html.parser")

    body_node = soup.find(id="js_content")
    if body_node is None:
        raise ArticleUnavailable("页面里找不到正文 #js_content，可能需要验证或链接已失效")

    title = _meta(soup, "og:title")
    if not title:
        title_match = _MSG_TITLE_RE.search(html)
        title = title_match.group(2).strip() if title_match else ""
    if not title:
        raise ArticleUnavailable("页面里找不到标题")

    published = extract_published(html, soup)
    body_html, image_urls = clean_body(body_node)

    return ParsedArticle(
        title=title,
        author=_meta(soup, "og:article:author"),
        published=published,
        cover_url=_meta(soup, "og:image"),
        body_html=body_html,
        image_urls=image_urls,
    )
