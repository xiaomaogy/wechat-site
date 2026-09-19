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
                "fetched_at": "2026-09-19T10:00:00+08:00",
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
