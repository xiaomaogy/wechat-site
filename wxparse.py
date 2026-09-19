"""解析微信公众号文章 HTML 的纯函数集合。这个模块不联网。"""

from __future__ import annotations

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
