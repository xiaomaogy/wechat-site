# 微信公众号文章静态站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把微信公众号文章抓成本地静态文件，生成一个仿公众号主页的目录站，托管在 Cloudflare Pages 的 `blog.vincentg.net`。

**Architecture:** 零构建。本机 `ingest.py` 抓取单篇文章（含把所有微信图片下载到本地），
写成 `content/<slug>/` 三件套；`build.py` 全量套模板生成 `dist/`。`dist/` 提交进 Git，
Cloudflare Pages 不跑任何构建命令，直接 serve。解析逻辑单独放 `wxparse.py`，
是不联网的纯函数，用固定 fixture 做 TDD。

**Tech Stack:** Python 3.14（Homebrew）、`requests`、`beautifulsoup4`、`pytest`、
`string.Template`（标准库，不引模板引擎）。前端纯 HTML + CSS，无 JS 框架。

**Spec:** `projects/wechat-site/docs/superpowers/specs/2026-09-19-wechat-site-design.md`

## Global Constraints

- 项目根目录：`/Users/vincentgao/Desktop/claude_code/projects/wechat-site/`。所有路径相对于此。
- Python 必须用项目内 venv：`.venv/bin/python`，由 `/opt/homebrew/bin/python3` 创建。**禁止**用 Anaconda 的 python。
- 运行时依赖只有 `requests` 和 `beautifulsoup4`；开发依赖只有 `pytest`。不得引入其他第三方库。
- 单文件不超过 300 行。
- 站点标识固定为：站名「高小猫」、地区「越南」、简介「一个我用来向自己和向世界解释为什么的地方」。
- 域名 `blog.vincentg.net`。GitHub 仓库 `xiaomaogy/wechat-site`，public。
- Git 远程一律用 HTTPS，不用 SSH。
- 临时文件写 `projects/wechat-site/tmp/`，不写 `/tmp`。
- slug 格式固定为 `YYYY-MM-DD-<微信短链 id>`，例：`2025-09-07-X8no6IXr1-e0GtSaYjhCGA`。
- 正文里的内联 `style` 属性必须保留（微信排版依赖它）。
- 所有 `mmbiz.qpic.cn` 图片必须下载到本地并重写引用，不得留外链。

---

### Task 1: 项目骨架与 wxparse 字段提取

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `site.config.json`
- Create: `wxparse.py`
- Create: `tests/fixtures/sample_article.html`
- Test: `tests/test_wxparse.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `wxparse.CST` — `timezone(timedelta(hours=8))`
  - `wxparse.ArticleUnavailable(Exception)`
  - `wxparse.ParsedArticle` dataclass，字段 `title: str`、`author: str`、
    `published: str`（`YYYY-MM-DD`）、`cover_url: str`、`body_html: str`、`image_urls: list[str]`
  - `wxparse.extract_published(html: str, soup: BeautifulSoup) -> str`
  - `wxparse.wx_id(url: str) -> str`
  - `wxparse.slug_for(url: str, published: str) -> str`

- [ ] **Step 1: 建目录与配置文件**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
mkdir -p templates static content dist tests/fixtures tmp
```

`.gitignore`：

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
tmp/
.DS_Store
.claude/settings.local.json
CLAUDE.local.md
.env
.env.*
```

`requirements.txt`：

```
requests>=2.32
beautifulsoup4>=4.13
```

`requirements-dev.txt`：

```
-r requirements.txt
pytest>=8.0
```

`site.config.json`：

```json
{
  "site_name": "高小猫",
  "region": "越南",
  "bio": "一个我用来向自己和向世界解释为什么的地方",
  "avatar": "avatar.svg",
  "domain": "blog.vincentg.net"
}
```

- [ ] **Step 2: 建 venv 并装依赖**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
.venv/bin/python -c "import requests, bs4, pytest; print('deps ok')"
```

Expected: 打印 `deps ok`

- [ ] **Step 3: 写 fixture HTML**

`tests/fixtures/sample_article.html`：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta property="og:title" content="Vipassana 10日冥想营" />
<meta property="og:image" content="https://mmbiz.qpic.cn/mmbiz_jpg/COVER/640?wx_fmt=jpeg" />
<meta property="og:article:author" content="高小猫" />
</head>
<body>
<script>
  var ct = "1757260800";
  var msg_title = 'Vipassana 10日冥想营';
</script>
<h1 id="activity-name">Vipassana 10日冥想营</h1>
<em id="publish_time">2025年09月07日 08:00</em>
<div id="js_content" style="visibility: hidden; opacity: 0;">
  <p style="text-indent: 2em;">第一天很难熬。</p>
  <p><img data-src="https://mmbiz.qpic.cn/mmbiz_png/IMG1/640?wx_fmt=png" src="" /></p>
  <p><img data-src="https://mmbiz.qpic.cn/mmbiz_jpg/IMG2/640?wx_fmt=jpeg" /></p>
  <style>.foo { color: red }</style>
  <script>console.log('junk')</script>
</div>
</body>
</html>
```

- [ ] **Step 4: 写失败的测试**

`tests/test_wxparse.py`：

```python
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import wxparse

FIXTURE = (Path(__file__).parent / "fixtures" / "sample_article.html").read_text(encoding="utf-8")


def test_extract_published_reads_ct_in_beijing_time():
    soup = BeautifulSoup(FIXTURE, "html.parser")
    assert wxparse.extract_published(FIXTURE, soup) == "2025-09-07"


def test_extract_published_falls_back_to_publish_time_node():
    html = '<em id="publish_time">2024年03月05日 21:30</em>'
    soup = BeautifulSoup(html, "html.parser")
    assert wxparse.extract_published(html, soup) == "2024-03-05"


def test_extract_published_raises_when_nothing_found():
    soup = BeautifulSoup("<html></html>", "html.parser")
    with pytest.raises(wxparse.ArticleUnavailable):
        wxparse.extract_published("<html></html>", soup)


def test_wx_id_from_short_link():
    assert wxparse.wx_id("https://mp.weixin.qq.com/s/X8no6IXr1-e0GtSaYjhCGA") == "X8no6IXr1-e0GtSaYjhCGA"


def test_slug_combines_date_and_id():
    slug = wxparse.slug_for("https://mp.weixin.qq.com/s/X8no6IXr1-e0GtSaYjhCGA", "2025-09-07")
    assert slug == "2025-09-07-X8no6IXr1-e0GtSaYjhCGA"
```

- [ ] **Step 5: 跑测试确认失败**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_wxparse.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'wxparse'`

- [ ] **Step 6: 写 wxparse.py 的字段提取部分**

```python
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
```

- [ ] **Step 7: 跑测试确认通过**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_wxparse.py -v
```

Expected: 5 passed

- [ ] **Step 8: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git init -b main 2>/dev/null || true
git add .gitignore requirements.txt requirements-dev.txt site.config.json wxparse.py tests/
git commit -m "feat: 项目骨架 + 微信文章字段提取"
```

---

### Task 2: 正文清洗与图片本地化

**Files:**
- Modify: `wxparse.py`（追加 `image_filename`、`clean_body`、`parse`）
- Test: `tests/test_wxparse.py`（追加用例）

**Interfaces:**
- Consumes: `wxparse.ParsedArticle`、`wxparse.ArticleUnavailable`、`wxparse.extract_published`（Task 1）
- Produces:
  - `wxparse.image_filename(url: str) -> str` — 返回 `<sha1前12位>.<ext>`
  - `wxparse.clean_body(node) -> tuple[str, list[str]]` — 返回（重写后的内部 HTML，按出现顺序去重的原始图片 URL 列表）
  - `wxparse.parse(html: str) -> ParsedArticle`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_wxparse.py`：

```python
def test_image_filename_uses_wx_fmt_extension():
    name = wxparse.image_filename("https://mmbiz.qpic.cn/mmbiz_png/IMG1/640?wx_fmt=png")
    assert name.endswith(".png")
    assert len(name.split(".")[0]) == 12


def test_image_filename_normalises_jpeg_to_jpg():
    name = wxparse.image_filename("https://mmbiz.qpic.cn/mmbiz_jpg/IMG2/640?wx_fmt=jpeg")
    assert name.endswith(".jpg")


def test_image_filename_is_stable_for_same_url():
    url = "https://mmbiz.qpic.cn/mmbiz_png/IMG1/640?wx_fmt=png"
    assert wxparse.image_filename(url) == wxparse.image_filename(url)


def test_image_filename_defaults_to_jpg_when_unknown():
    assert wxparse.image_filename("https://mmbiz.qpic.cn/mmbiz/IMG3/640").endswith(".jpg")


def test_parse_returns_all_fields():
    article = wxparse.parse(FIXTURE)
    assert article.title == "Vipassana 10日冥想营"
    assert article.author == "高小猫"
    assert article.published == "2025-09-07"
    assert article.cover_url == "https://mmbiz.qpic.cn/mmbiz_jpg/COVER/640?wx_fmt=jpeg"


def test_parse_rewrites_images_to_local_paths():
    article = wxparse.parse(FIXTURE)
    assert article.image_urls == [
        "https://mmbiz.qpic.cn/mmbiz_png/IMG1/640?wx_fmt=png",
        "https://mmbiz.qpic.cn/mmbiz_jpg/IMG2/640?wx_fmt=jpeg",
    ]
    for url in article.image_urls:
        assert f'images/{wxparse.image_filename(url)}' in article.body_html
    assert "mmbiz.qpic.cn" not in article.body_html
    assert "data-src" not in article.body_html


def test_parse_keeps_inline_styles_and_drops_script_and_style_tags():
    article = wxparse.parse(FIXTURE)
    assert 'style="text-indent: 2em;"' in article.body_html
    assert "<script" not in article.body_html
    assert "color: red" not in article.body_html


def test_parse_raises_on_deleted_article():
    html = "<html><body><div class='weui-msg__title'>该内容已被发布者删除</div></body></html>"
    with pytest.raises(wxparse.ArticleUnavailable):
        wxparse.parse(html)


def test_parse_raises_when_body_missing():
    html = '<html><head><meta property="og:title" content="x"/></head><body></body></html>'
    with pytest.raises(wxparse.ArticleUnavailable):
        wxparse.parse(html)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_wxparse.py -v
```

Expected: FAIL，`AttributeError: module 'wxparse' has no attribute 'image_filename'`

- [ ] **Step 3: 实现清洗与解析**

在 `wxparse.py` 顶部 import 区加 `import hashlib`，然后追加：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_wxparse.py -v
```

Expected: 14 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add wxparse.py tests/test_wxparse.py
git commit -m "feat: 正文清洗与图片本地化重写"
```

---

### Task 3: ingest.py — 抓取、下图、写盘

**Files:**
- Create: `ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `wxparse.parse`、`wxparse.slug_for`、`wxparse.image_filename`、`wxparse.ArticleUnavailable`（Task 1、2）
- Produces:
  - `ingest.fetch(url: str) -> str`
  - `ingest._get_bytes(url: str) -> bytes`
  - `ingest.download_images(urls: list[str], dest: Path) -> list[str]` — 返回失败的 URL 列表
  - `ingest.ingest(url: str, content_root: Path) -> Path` — 返回写好的 `content/<slug>/` 路径
  - `meta.json` 结构：`{"slug", "title", "author", "published", "source_url", "cover", "fetched_at"}`
    其中 `cover` 是 `images/` 下的文件名，取不到封面时为 `""`

- [ ] **Step 1: 写失败的测试**

`tests/test_ingest.py`：

```python
import json
from pathlib import Path

import pytest

import ingest
import wxparse

FIXTURE = (Path(__file__).parent / "fixtures" / "sample_article.html").read_text(encoding="utf-8")
URL = "https://mp.weixin.qq.com/s/X8no6IXr1-e0GtSaYjhCGA"

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake png payload"


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(ingest, "fetch", lambda url: FIXTURE)
    monkeypatch.setattr(ingest, "_get_bytes", lambda url: PNG_BYTES)


def test_ingest_creates_slug_directory_with_three_parts(tmp_path, offline):
    out = ingest.ingest(URL, tmp_path)

    assert out == tmp_path / "2025-09-07-X8no6IXr1-e0GtSaYjhCGA"
    assert (out / "meta.json").exists()
    assert (out / "body.html").exists()
    assert (out / "images").is_dir()


def test_ingest_writes_expected_meta(tmp_path, offline):
    out = ingest.ingest(URL, tmp_path)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))

    assert meta["title"] == "Vipassana 10日冥想营"
    assert meta["author"] == "高小猫"
    assert meta["published"] == "2025-09-07"
    assert meta["source_url"] == URL
    assert meta["slug"] == "2025-09-07-X8no6IXr1-e0GtSaYjhCGA"
    assert meta["cover"] == wxparse.image_filename(
        "https://mmbiz.qpic.cn/mmbiz_jpg/COVER/640?wx_fmt=jpeg"
    )


def test_ingest_downloads_body_images_and_cover(tmp_path, offline):
    out = ingest.ingest(URL, tmp_path)
    names = sorted(p.name for p in (out / "images").iterdir())

    expected = sorted(
        wxparse.image_filename(url)
        for url in [
            "https://mmbiz.qpic.cn/mmbiz_jpg/COVER/640?wx_fmt=jpeg",
            "https://mmbiz.qpic.cn/mmbiz_png/IMG1/640?wx_fmt=png",
            "https://mmbiz.qpic.cn/mmbiz_jpg/IMG2/640?wx_fmt=jpeg",
        ]
    )
    assert names == expected
    assert (out / "images" / expected[0]).read_bytes() == PNG_BYTES


def test_ingest_is_idempotent(tmp_path, offline):
    first = ingest.ingest(URL, tmp_path)
    second = ingest.ingest(URL, tmp_path)

    assert first == second
    assert len(list(tmp_path.iterdir())) == 1


def test_download_images_reports_failures_without_raising(tmp_path, monkeypatch):
    def boom(url):
        raise OSError("connection reset")

    monkeypatch.setattr(ingest, "_get_bytes", boom)
    failed = ingest.download_images(["https://mmbiz.qpic.cn/a/640?wx_fmt=png"], tmp_path)

    assert failed == ["https://mmbiz.qpic.cn/a/640?wx_fmt=png"]


def test_ingest_saves_raw_html_when_page_unusable(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "fetch", lambda url: "<html>该内容已被发布者删除</html>")
    monkeypatch.setattr(ingest, "_get_bytes", lambda url: PNG_BYTES)
    debug_dir = tmp_path / "debug"
    monkeypatch.setattr(ingest, "DEBUG_DIR", debug_dir)

    with pytest.raises(wxparse.ArticleUnavailable):
        ingest.ingest(URL, tmp_path)

    saved = list(debug_dir.glob("*.html"))
    assert len(saved) == 1
    assert "该内容已被发布者删除" in saved[0].read_text(encoding="utf-8")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_ingest.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'ingest'`

- [ ] **Step 3: 实现 ingest.py**

```python
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


def download_images(urls: list[str], dest: Path) -> list[str]:
    """下载图片到 dest。单张失败只记录不中断，返回失败的 URL 列表。"""
    dest.mkdir(parents=True, exist_ok=True)
    failed: list[str] = []
    for url in urls:
        target = dest / wxparse.image_filename(url)
        if target.exists():
            continue
        try:
            target.write_bytes(_get_bytes(url))
        except Exception as error:  # noqa: BLE001 — 单图失败不该毁掉整篇
            print(f"  WARNING 图片下载失败 {url}: {error}", file=sys.stderr)
            failed.append(url)
    return failed


def _save_debug(url: str, html: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{wxparse.wx_id(url)}.html"
    path.write_text(html, encoding="utf-8")
    return path


def ingest(url: str, content_root: Path) -> Path:
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

    failed = download_images(image_urls, images_dir)
    if cover_name and article.cover_url in failed:
        cover_name = ""

    (out_dir / "body.html").write_text(article.body_html, encoding="utf-8")
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
    args = parser.parse_args(argv)

    failures = 0
    for url in args.urls:
        try:
            ingest(url, CONTENT_ROOT)
        except Exception as error:  # noqa: BLE001 — 一篇失败不该中断其余
            print(f"✗ {url}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/ -v
```

Expected: 20 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add ingest.py tests/test_ingest.py
git commit -m "feat: ingest 抓取、下图、写盘"
```

---

### Task 4: build.py 与文章页

**Files:**
- Create: `build.py`
- Create: `templates/article.html`
- Create: `static/style.css`
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: Task 3 写出的 `content/<slug>/{meta.json, body.html, images/}` 结构
- Produces:
  - `build.load_articles(content_root: Path) -> list[dict]` — 每项是 `meta.json` 的内容加上
    `body`（正文 HTML）和 `dir`（`Path`），按 `published` 倒序、同日按 `slug` 倒序
  - `build.date_label(published: str, today: date) -> str`
  - `build.load_config(project_root: Path) -> dict`
  - `build.render_article(article: dict, config: dict, template: str) -> str`
  - `build.build(project_root: Path, content_root: Path | None = None, dist_root: Path | None = None) -> None`
  - 文章页产物路径：`dist/p/<slug>/index.html`，图片在 `dist/p/<slug>/images/`

- [ ] **Step 1: 写失败的测试**

`tests/test_build.py`：

```python
import json
from datetime import date
from pathlib import Path

import pytest

import build

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_article(content_root: Path, slug: str, title: str, published: str, cover: str = "c.jpg"):
    out = content_root / slug
    (out / "images").mkdir(parents=True)
    (out / "images" / cover).write_bytes(b"fake")
    (out / "body.html").write_text(
        f'<p style="text-indent: 2em;">{title} 的正文</p><img src="images/{cover}" />',
        encoding="utf-8",
    )
    (out / "meta.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "title": title,
                "author": "高小猫",
                "published": published,
                "source_url": f"https://mp.weixin.qq.com/s/{slug}",
                "cover": cover,
                "fetched_at": "2026-09-08T10:00:00+08:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out


def test_date_label_today_and_yesterday():
    today = date(2026, 9, 8)
    assert build.date_label("2026-09-08", today) == "今天"
    assert build.date_label("2026-09-07", today) == "昨天"


def test_date_label_same_year_omits_year():
    assert build.date_label("2026-08-02", date(2026, 9, 8)) == "8月2日"


def test_date_label_other_year_includes_year():
    assert build.date_label("2025-09-07", date(2026, 9, 8)) == "2025年9月7日"


def test_load_articles_sorted_newest_first(tmp_path):
    content = tmp_path / "content"
    make_article(content, "2025-01-01-aaa", "旧文", "2025-01-01")
    make_article(content, "2026-09-08-bbb", "新文", "2026-09-08")

    articles = build.load_articles(content)

    assert [a["title"] for a in articles] == ["新文", "旧文"]
    assert "旧文 的正文" in articles[1]["body"]


def test_build_writes_article_page_with_body_and_images(tmp_path):
    content = tmp_path / "content"
    dist = tmp_path / "dist"
    make_article(content, "2025-09-07-xyz", "Vipassana 10日冥想营", "2025-09-07")

    build.build(PROJECT_ROOT, content_root=content, dist_root=dist)

    page = dist / "p" / "2025-09-07-xyz" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert "Vipassana 10日冥想营" in html
    assert 'style="text-indent: 2em;"' in html
    assert "https://mp.weixin.qq.com/s/2025-09-07-xyz" in html
    assert (dist / "p" / "2025-09-07-xyz" / "images" / "c.jpg").exists()


def test_build_clears_stale_output(tmp_path):
    content = tmp_path / "content"
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "stale.html").write_text("old", encoding="utf-8")
    make_article(content, "2025-09-07-xyz", "标题", "2025-09-07")

    build.build(PROJECT_ROOT, content_root=content, dist_root=dist)

    assert not (dist / "stale.html").exists()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_build.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'build'`

- [ ] **Step 3: 写文章页模板**

`templates/article.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>$title · $site_name</title>
<link rel="stylesheet" href="../../static/style.css" />
</head>
<body>
<main class="wrap">
  <p class="back"><a href="../../">← $site_name</a></p>
  <article>
    <h1 class="post-title">$title</h1>
    <p class="post-meta">$author · $date_label</p>
    <div class="post-body">
$body
    </div>
  </article>
  <footer class="post-footer">
    <a href="$source_url" rel="noopener">原文发表于微信公众号</a>
  </footer>
</main>
</body>
</html>
```

- [ ] **Step 4: 写 build.py**

```python
"""把 content/ 下的文章全量渲染成 dist/。"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from string import Template

PROJECT_ROOT = Path(__file__).resolve().parent


def load_config(project_root: Path) -> dict:
    return json.loads((project_root / "site.config.json").read_text(encoding="utf-8"))


def load_articles(content_root: Path) -> list[dict]:
    articles: list[dict] = []
    if not content_root.is_dir():
        return articles

    for entry in sorted(content_root.iterdir()):
        meta_path = entry / "meta.json"
        if not meta_path.is_file():
            continue
        article = json.loads(meta_path.read_text(encoding="utf-8"))
        article["body"] = (entry / "body.html").read_text(encoding="utf-8")
        article["dir"] = entry
        articles.append(article)

    articles.sort(key=lambda a: (a["published"], a["slug"]), reverse=True)
    return articles


def date_label(published: str, today: date) -> str:
    day = date.fromisoformat(published)
    delta = (today - day).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "昨天"
    if day.year == today.year:
        return f"{day.month}月{day.day}日"
    return f"{day.year}年{day.month}月{day.day}日"


def render_article(article: dict, config: dict, template: str) -> str:
    return Template(template).safe_substitute(
        title=article["title"],
        author=article["author"] or config["site_name"],
        date_label=date_label(article["published"], date.today()),
        body=article["body"],
        source_url=article["source_url"],
        site_name=config["site_name"],
    )


def build(
    project_root: Path,
    content_root: Path | None = None,
    dist_root: Path | None = None,
) -> None:
    content_root = content_root or project_root / "content"
    dist_root = dist_root or project_root / "dist"
    templates = project_root / "templates"
    config = load_config(project_root)

    if dist_root.exists():
        shutil.rmtree(dist_root)
    dist_root.mkdir(parents=True)

    shutil.copytree(project_root / "static", dist_root / "static")

    articles = load_articles(content_root)
    article_template = (templates / "article.html").read_text(encoding="utf-8")

    for article in articles:
        out_dir = dist_root / "p" / article["slug"]
        out_dir.mkdir(parents=True)
        (out_dir / "index.html").write_text(
            render_article(article, config, article_template), encoding="utf-8"
        )
        images = article["dir"] / "images"
        if images.is_dir():
            shutil.copytree(images, out_dir / "images")

    print(f"✓ 生成 {len(articles)} 篇文章 → {dist_root}")


if __name__ == "__main__":
    build(PROJECT_ROOT)
```

- [ ] **Step 5: 写 style.css 的基础与文章页部分**

`static/style.css`：

```css
:root {
  --bg: #f7f7f7;
  --card: #ffffff;
  --text: #1a1a1a;
  --muted: #8c8c8c;
  --line: #ebebeb;
  --link: #576b95;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111111;
    --card: #1c1c1e;
    --text: #ededed;
    --muted: #8e8e93;
    --line: #2c2c2e;
    --link: #7d90bb;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 17px/1.75 -apple-system, BlinkMacSystemFont, "PingFang SC",
        "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
}

a { color: var(--link); text-decoration: none; }

.wrap { max-width: 680px; margin: 0 auto; padding: 20px 18px 64px; }

.back { font-size: 14px; margin: 0 0 20px; }

.post-title {
  font-size: 26px;
  line-height: 1.4;
  font-weight: 600;
  margin: 0 0 12px;
}

.post-meta { color: var(--muted); font-size: 14px; margin: 0 0 28px; }

.post-body { word-wrap: break-word; }
.post-body img { max-width: 100%; height: auto; display: block; margin: 12px auto; border-radius: 4px; }
.post-body p { margin: 0 0 18px; }

.post-footer {
  margin-top: 48px;
  padding-top: 20px;
  border-top: 1px solid var(--line);
  font-size: 14px;
  color: var(--muted);
}
```

- [ ] **Step 6: 跑测试确认通过**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/ -v
```

Expected: 26 passed

- [ ] **Step 7: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add build.py templates/article.html static/style.css tests/test_build.py
git commit -m "feat: build 渲染引擎与文章页"
```

---

### Task 5: 目录页

**Files:**
- Modify: `build.py`（追加 `render_index`，在 `build()` 里写 `dist/index.html`）
- Create: `templates/index.html`
- Create: `static/avatar.svg`
- Modify: `static/style.css`（追加目录页样式）
- Modify: `tests/test_build.py`（追加用例）

**Interfaces:**
- Consumes: `build.load_articles`、`build.date_label`、`build.load_config`（Task 4）
- Produces:
  - `build.render_index(articles: list[dict], config: dict, template: str) -> str`
  - 产物 `dist/index.html`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_build.py`：

```python
def test_index_lists_articles_grouped_by_date(tmp_path):
    content = tmp_path / "content"
    dist = tmp_path / "dist"
    make_article(content, "2026-08-02-old", "四种创造价值的方式", "2026-08-02")
    make_article(content, "2025-09-07-new", "Vipassana 10日冥想营", "2025-09-07")

    build.build(PROJECT_ROOT, content_root=content, dist_root=dist)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert "高小猫" in html
    assert "一个我用来向自己和向世界解释为什么的地方" in html
    assert "2篇原创内容" in html
    assert "8月2日" in html or "今天" in html
    assert html.index("四种创造价值的方式") < html.index("Vipassana 10日冥想营")
    assert 'href="p/2026-08-02-old/"' in html
    assert 'src="p/2026-08-02-old/images/c.jpg"' in html


def test_index_handles_article_without_cover(tmp_path):
    content = tmp_path / "content"
    dist = tmp_path / "dist"
    out = make_article(content, "2026-01-01-nocover", "无封面", "2026-01-01")
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["cover"] = ""
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    build.build(PROJECT_ROOT, content_root=content, dist_root=dist)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert "无封面" in html
    assert "<img" not in html.split('class="cards"')[1]


def test_index_escapes_titles(tmp_path):
    content = tmp_path / "content"
    dist = tmp_path / "dist"
    make_article(content, "2026-02-02-esc", "A & B <script>", "2026-02-02")

    build.build(PROJECT_ROOT, content_root=content, dist_root=dist)
    html = (dist / "index.html").read_text(encoding="utf-8")

    assert "A &amp; B &lt;script&gt;" in html
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/test_build.py -v
```

Expected: FAIL，`FileNotFoundError` 找不到 `templates/index.html`

- [ ] **Step 3: 写目录页模板**

`templates/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>$site_name</title>
<link rel="stylesheet" href="static/style.css" />
</head>
<body>
<main class="wrap">
  <header class="profile">
    <img class="avatar" src="static/$avatar" alt="$site_name" />
    <div class="profile-text">
      <h1 class="profile-name">$site_name</h1>
      <p class="profile-region">$region</p>
    </div>
  </header>
  <p class="profile-bio">$bio</p>
  <p class="profile-stat">$count篇原创内容</p>
  <div class="cards">
$cards
  </div>
</main>
</body>
</html>
```

- [ ] **Step 4: 写头像 SVG**

`static/avatar.svg`（占位；用户可以直接换成 `static/avatar.png` 并改 `site.config.json` 的 `avatar` 字段）：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <circle cx="48" cy="48" r="48" fill="#f6a83c"/>
  <path d="M22 34 L30 16 L44 28 Z" fill="#e08a1e"/>
  <path d="M74 34 L66 16 L52 28 Z" fill="#e08a1e"/>
  <circle cx="36" cy="48" r="5" fill="#3b2a15"/>
  <circle cx="60" cy="48" r="5" fill="#3b2a15"/>
  <path d="M42 62 Q48 68 54 62" stroke="#3b2a15" stroke-width="3" fill="none" stroke-linecap="round"/>
</svg>
```

- [ ] **Step 5: 在 build.py 里实现目录页**

在 `build.py` 的 import 区加 `from html import escape`，然后在 `render_article` 之后追加：

```python
def _card_html(article: dict, label: str) -> str:
    href = f"p/{article['slug']}/"
    title = escape(article["title"])
    cover = ""
    if article.get("cover"):
        cover = (
            f'      <img class="card-cover" loading="lazy" '
            f'src="{href}images/{article["cover"]}" alt="{title}" />\n'
        )
    return (
        f'    <a class="card" href="{href}">\n'
        f"{cover}"
        f'      <div class="card-text">\n'
        f'        <h2 class="card-title">{title}</h2>\n'
        f'        <p class="card-date">{escape(label)}</p>\n'
        f"      </div>\n"
        f"    </a>"
    )


def render_index(articles: list[dict], config: dict, template: str) -> str:
    today = date.today()
    cards = "\n".join(
        _card_html(article, date_label(article["published"], today)) for article in articles
    )
    return Template(template).safe_substitute(
        site_name=escape(config["site_name"]),
        region=escape(config["region"]),
        bio=escape(config["bio"]),
        avatar=config["avatar"],
        count=len(articles),
        cards=cards,
    )
```

在 `build()` 里，`article_template` 那行之后加载目录模板，并在文章循环结束后写出 `index.html`：

```python
    index_template = (templates / "index.html").read_text(encoding="utf-8")
```

（放在 `article_template = ...` 下一行）

```python
    (dist_root / "index.html").write_text(
        render_index(articles, config, index_template), encoding="utf-8"
    )
```

（放在文章 `for` 循环之后、`print(...)` 之前）

- [ ] **Step 6: 追加目录页样式**

追加到 `static/style.css` 末尾：

```css
.profile { display: flex; align-items: center; gap: 14px; padding-top: 12px; }
.avatar { width: 56px; height: 56px; border-radius: 50%; display: block; }
.profile-name { font-size: 22px; font-weight: 600; margin: 0; }
.profile-region { color: var(--muted); font-size: 14px; margin: 2px 0 0; }
.profile-bio { margin: 18px 0 6px; font-size: 16px; }
.profile-stat { color: var(--muted); font-size: 14px; margin: 0 0 28px; }

.cards { display: flex; flex-direction: column; gap: 14px; }

.card {
  display: block;
  background: var(--card);
  border-radius: 10px;
  overflow: hidden;
  color: inherit;
  border: 1px solid var(--line);
}

.card-cover {
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  display: block;
}

.card-text { padding: 14px 16px 16px; }
.card-title { font-size: 17px; font-weight: 500; line-height: 1.45; margin: 0; }
.card-date { color: var(--muted); font-size: 13px; margin: 8px 0 0; }
```

- [ ] **Step 7: 跑测试确认通过**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python -m pytest tests/ -v
```

Expected: 29 passed

- [ ] **Step 8: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add build.py templates/index.html static/avatar.svg static/style.css tests/test_build.py
git commit -m "feat: 仿公众号主页的目录页"
```

---

### Task 6: 抓真实文章并肉眼验收

**Files:**
- Create: `content/2025-09-07-X8no6IXr1-e0GtSaYjhCGA/`（由脚本生成，日期以实际抓到的为准）
- Create: `dist/`（由脚本生成）
- Create: `README.md`
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: `ingest.main`（Task 3）、`build.build`（Task 4、5）
- Produces: 仓库里可直接部署的 `dist/`

- [ ] **Step 1: 抓 Vipassana 那篇**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python ingest.py "https://mp.weixin.qq.com/s/X8no6IXr1-e0GtSaYjhCGA"
```

Expected: 打印 `✓ Vipassana 10日冥想营 → .../content/<slug>`，无 WARNING。

这一步需要网络访问；如果 Bash 被沙箱拦住，请用户放行一次。
如果抓取报 `ArticleUnavailable`，按 `tmp/<id>.html` 里的实际内容判断是被删、需验证、
还是选择器变了，再决定改 `wxparse` 还是请用户手工提供原文。

- [ ] **Step 2: 检查抓下来的东西**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
cat content/*/meta.json
ls content/*/images/ | head -20
grep -c "mmbiz.qpic.cn" content/*/body.html || echo "0 外链，正确"
```

Expected: meta 字段齐全、images 目录非空、body.html 里 `mmbiz.qpic.cn` 计数为 0。

- [ ] **Step 3: 生成 dist 并起本地服务**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site && .venv/bin/python build.py
```

然后后台起服务：

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site/dist && python3 -m http.server 8899
```

- [ ] **Step 4: 用浏览器工具核对**

用 `mcp__Claude_Browser__navigate` 打开 `http://localhost:8899/`，
先 `resize_window` 到 `preset: "mobile"`，截图；再点进文章页截图。逐项确认：

1. 目录页头部：头像、「高小猫」、「越南」、简介、「N篇原创内容」都在，版式接近公众号主页。
2. 卡片有封面图、标题、日期，整张可点。
3. 文章页正文图片全部显示，没有裂图（重点看这一条）。
4. 移动端宽度下没有横向滚动。
5. 用 `resize_window` 的 `colorScheme: "dark"` 再看一遍，深色模式文字可读。

任何一条不过就改 CSS 或模板，改完重跑 `build.py` 再看。

- [ ] **Step 5: 写 README.md 和 CLAUDE.md**

`README.md`：

```markdown
# wechat-site

「高小猫」公众号文章的静态站，托管在 Cloudflare Pages：https://blog.vincentg.net

## 加一篇文章

```bash
.venv/bin/python ingest.py "https://mp.weixin.qq.com/s/xxxxxx"
.venv/bin/python build.py
git add -A && git commit -m "add: 文章标题" && git push
```

推上去 Cloudflare Pages 自动部署，一两分钟后生效。

## 结构

- `ingest.py` — 抓文章、下载全部图片到本地、写 `content/<slug>/`
- `wxparse.py` — 不联网的纯解析函数（字段提取、正文清洗、图片重写）
- `build.py` — `content/` → `dist/` 全量重新生成
- `dist/` — 生成产物，就是线上内容，**要提交进仓库**

## 换头像

把图片放到 `static/`，改 `site.config.json` 的 `avatar` 字段，重跑 `build.py`。

## 开发

```bash
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -v
```
```

`CLAUDE.md`：

```markdown
# wechat-site

微信公众号文章 → 静态站，Cloudflare Pages 托管 blog.vincentg.net。

## 铁律

- `dist/` 是生成产物但**必须提交**——CF Pages 不跑构建，直接 serve 仓库里的 `dist/`。
- 改了 `content/`、`templates/`、`static/`、`site.config.json` 之后必须重跑 `build.py`。
- 图片一律本地化。`body.html` 里出现 `mmbiz.qpic.cn` 就是 bug（微信图床有防盗链）。
- 正文的内联 `style` 属性不要动，微信排版全靠它。
- Python 用 `.venv/bin/python`，不用 Anaconda。
- 临时文件写本目录 `tmp/`。

## 常用命令

```bash
.venv/bin/python ingest.py "<微信链接>"   # 抓一篇
.venv/bin/python build.py                # 重新生成 dist/
.venv/bin/python -m pytest tests/ -v     # 跑测试
cd dist && python3 -m http.server 8899   # 本地预览
```
```

- [ ] **Step 6: 停掉本地服务并提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add -A
git commit -m "feat: 抓取首篇文章并生成 dist，补 README/CLAUDE"
```

---

### Task 7: 推 GitHub 并接入 Cloudflare Pages

**Files:**
- 无新文件；只做 git 远程与外部配置

**Interfaces:**
- Consumes: Task 6 产出的完整仓库（含 `dist/`）
- Produces: 线上站点 `https://blog.vincentg.net`

- [ ] **Step 1: 确保 git 用 HTTPS**

```bash
gh config set git_protocol https
gh config get git_protocol
```

Expected: 打印 `https`

- [ ] **Step 2: 建仓库并推上去**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
gh repo create wechat-site --public --source=. --remote=origin --push
git remote -v
```

Expected: `origin` 是 `https://github.com/xiaomaogy/wechat-site.git`，push 成功。

- [ ] **Step 3: 确认 dist 真的进了仓库**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git ls-files dist | head -10
git ls-files dist | wc -l
```

Expected: 至少包含 `dist/index.html`、`dist/static/style.css` 和文章页；数量大于 5。
如果是 0，说明 `.gitignore` 误伤了，必须修掉再推。

- [ ] **Step 4: 给用户 Cloudflare 后台的操作指引**

把下面这段原样给用户，这几步只能他自己在网页上点：

> 1. 打开 https://dash.cloudflare.com → 左侧 **Workers & Pages** → **Create** → **Pages** → **Connect to Git**
> 2. 授权 GitHub，选 `xiaomaogy/wechat-site` 仓库
> 3. 构建设置：
>    - Project name: `wechat-site`
>    - Production branch: `main`
>    - Framework preset: **None**
>    - Build command: **留空**
>    - Build output directory: `dist`
> 4. 点 **Save and Deploy**，等一两分钟出 `xxx.pages.dev` 地址
> 5. 进这个 Pages 项目 → **Custom domains** → **Set up a custom domain** → 填 `blog.vincentg.net` → 确认
>    （vincentg.net 已经在你的 Cloudflare 账号下，DNS 记录会自动加）

- [ ] **Step 5: 验收线上站点**

等用户说配好之后：

```bash
curl -sI https://blog.vincentg.net | head -3
```

Expected: `HTTP/2 200`

再用 `mcp__Claude_Browser__navigate` 打开 `https://blog.vincentg.net`，截图确认：
目录页正常、点进文章正文图片全部显示（线上图片走的是自己域名，这里是防盗链问题的最终验证）。

- [ ] **Step 6: 更新根目录 CLAUDE.md 的项目表**

在 `/Users/vincentgao/Desktop/claude_code/CLAUDE.md` 的「💻 projects/」表格里追加一行：

```
| `wechat-site/` | 微信公众号文章静态站（Cloudflare Pages，blog.vincentg.net） | 想把某篇公众号文章搬上自己的站时：`ingest.py <链接>` → `build.py` → push 即自动部署 |
```

- [ ] **Step 7: 提交**

```bash
cd /Users/vincentgao/Desktop/claude_code/projects/wechat-site
git add -A && git commit -m "docs: 上线后的收尾" --allow-empty && git push
```

---

## Self-Review

**Spec coverage：**

| Spec 要求 | 对应任务 |
|---|---|
| 零构建、`dist/` 进仓库 | Task 4（build）、Task 7 Step 3（验证 dist 进了 git） |
| 目录结构 | Task 1 Step 1、Task 4、Task 5 |
| slug = 日期 + 微信 id | Task 1（`slug_for` + 测试） |
| 字段提取（标题/时间/正文/封面/作者） | Task 1、Task 2 |
| 正文清洗、保留内联 style | Task 2（`clean_body` + 测试断言） |
| 图片本地化 | Task 2（重写）、Task 3（下载）、Task 6 Step 2（外链计数为 0） |
| 幂等 | Task 3（`test_ingest_is_idempotent`） |
| 抓取失败存原始 HTML 到 tmp/ | Task 3（`test_ingest_saves_raw_html_when_page_unusable`） |
| 单图失败不中断 | Task 3（`test_download_images_reports_failures_without_raising`） |
| 目录页仿公众号主页 | Task 5、Task 6 Step 4 |
| 文章页版式（680px / 17px / 1.75） | Task 4 Step 5 |
| 深浅色跟随系统 | Task 4 Step 5、Task 6 Step 4 |
| 部署与自定义域 | Task 7 |
| 验收 1-4 条 | Task 6 Step 1-4、Task 7 Step 5 |

无遗漏。

**Placeholder scan：** 每个代码步骤都是可直接落盘的完整代码，无 TBD / "类似 Task N" / "加上适当的错误处理"。

**Type consistency：** `ParsedArticle` 六个字段在 Task 1 定义、Task 2 构造、Task 3 消费，名字一致；
`image_filename` 在 Task 2 定义、Task 3 下载与 Task 3 测试断言中使用，签名一致；
`meta.json` 的键在 Task 3 写入、Task 4/5 读取、Task 4/5 测试构造，三处一致；
`build(project_root, content_root, dist_root)` 签名在 Task 4 定义、Task 5 复用、两处测试调用，一致；
模板变量 `$title/$author/$date_label/$body/$source_url/$site_name` 与 `render_article` 的 kwargs 对齐，
`$site_name/$region/$bio/$avatar/$count/$cards` 与 `render_index` 的 kwargs 对齐。
