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
