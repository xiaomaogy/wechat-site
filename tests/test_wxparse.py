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


def _page(body_inner: str, title: str = "标题甲") -> str:
    return (
        f'<html><head><meta property="og:title" content="{title}"/></head><body>'
        '<script>var ct = "1757174400";</script>'
        f'<div id="js_content">{body_inner}</div>'
        "</body></html>"
    )


def test_parse_drops_leading_heading_that_repeats_title():
    article = wxparse.parse(_page("<h1>标题甲</h1><p>正文</p>"))
    assert "标题甲" not in article.body_html
    assert "正文" in article.body_html


def test_parse_drops_repeated_title_ignoring_whitespace():
    article = wxparse.parse(_page("<h1> 标题 甲 </h1><p>正文</p>"))
    assert "<h1>" not in article.body_html


def test_parse_keeps_leading_heading_that_differs_from_title():
    article = wxparse.parse(_page("<h1>另一个小标题</h1><p>正文</p>"))
    assert "另一个小标题" in article.body_html


def test_parse_only_drops_the_first_element():
    article = wxparse.parse(_page("<p>引言</p><h1>标题甲</h1>"))
    assert "标题甲" in article.body_html


def test_clean_body_strips_dark_inline_colors():
    article = wxparse.parse(_page('<p style="color: rgb(36, 42, 38);text-indent: 2em;">正文</p>'))
    assert "rgb(36, 42, 38)" not in article.body_html
    assert "text-indent: 2em" in article.body_html


def test_clean_body_strips_dark_green_heading_color():
    article = wxparse.parse(_page('<h2 style="color: rgb(19, 64, 52);">小标题</h2>'))
    assert "rgb(19, 64, 52)" not in article.body_html
    assert "小标题" in article.body_html


def test_clean_body_keeps_bright_inline_colors():
    article = wxparse.parse(_page('<p style="color: rgb(255, 120, 0);">正文</p>'))
    assert "rgb(255, 120, 0)" in article.body_html


def test_clean_body_strips_dark_hex_colors():
    article = wxparse.parse(_page('<p style="color:#242a26;">正文</p>'))
    assert "#242a26" not in article.body_html


def test_clean_body_drops_style_attribute_when_nothing_left():
    article = wxparse.parse(_page('<p style="color: #000;">正文</p>'))
    assert "style" not in article.body_html


def test_clean_body_keeps_non_color_styles_untouched():
    article = wxparse.parse(_page('<p style="margin: 16px 0px;">正文</p>'))
    assert 'style="margin: 16px 0px;"' in article.body_html


def test_sniff_ext_recognises_binary_formats():
    assert wxparse.sniff_ext(b"\xff\xd8\xff\xe0 jpeg body") == "jpg"
    assert wxparse.sniff_ext(b"\x89PNG\r\n\x1a\n body") == "png"
    assert wxparse.sniff_ext(b"GIF89a body") == "gif"
    assert wxparse.sniff_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"


def test_sniff_ext_recognises_svg_with_and_without_prolog():
    assert wxparse.sniff_ext(b'  <svg version="1.1" xmlns="x"></svg>') == "svg"
    assert wxparse.sniff_ext(b'<?xml version="1.0"?>\n<svg xmlns="x"></svg>') == "svg"


def test_sniff_ext_returns_none_when_unrecognised():
    assert wxparse.sniff_ext(b"not an image at all") is None
