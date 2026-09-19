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
