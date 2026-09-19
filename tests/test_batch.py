from pathlib import Path

import pytest

import batch
import ingest

URLS = [
    "https://mp.weixin.qq.com/s/AAAAAAAAAAAAAAAAAAAAAA",
    "https://mp.weixin.qq.com/s/BBBBBBBBBBBBBBBBBBBBBB",
    "https://mp.weixin.qq.com/s/CCCCCCCCCCCCCCCCCCCCCC",
]


@pytest.fixture
def recorder(monkeypatch):
    """记录 ingest 调用和 sleep 时长，全程不联网。"""
    calls = {"ingest": [], "sleeps": []}

    def fake_ingest(url, content_root, skip_existing=False):
        calls["ingest"].append(url)
        out = content_root / f"2026-01-01-{url.rsplit('/', 1)[-1]}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    monkeypatch.setattr(ingest, "ingest", fake_ingest)
    calls["sleeper"] = lambda seconds: calls["sleeps"].append(seconds)
    return calls


def test_read_urls_ignores_blanks_comments_and_duplicates(tmp_path):
    listing = tmp_path / "articles.txt"
    listing.write_text(
        "\n".join(["# 注释", "", URLS[0], URLS[1], URLS[0], "   "]), encoding="utf-8"
    )

    assert batch.read_urls(listing) == [URLS[0], URLS[1]]


def test_run_ingests_every_url(tmp_path, recorder):
    result = batch.run(URLS, tmp_path, sleeper=recorder["sleeper"])

    assert recorder["ingest"] == URLS
    assert result["done"] == URLS
    assert result["failed"] == []


def test_run_sleeps_between_articles_only(tmp_path, recorder):
    batch.run(URLS, tmp_path, sleeper=recorder["sleeper"])
    assert len(recorder["sleeps"]) == len(URLS) - 1

    recorder["sleeps"].clear()
    batch.run(URLS[:1], tmp_path / "solo", sleeper=recorder["sleeper"])
    assert recorder["sleeps"] == []


def test_run_delays_land_in_configured_range(tmp_path, recorder):
    batch.run(URLS, tmp_path, sleeper=recorder["sleeper"], min_delay=2.0, max_delay=4.0)
    assert all(2.0 <= s <= 4.0 for s in recorder["sleeps"])


def test_run_skips_already_downloaded_without_calling_ingest(tmp_path, recorder):
    (tmp_path / "2026-01-01-AAAAAAAAAAAAAAAAAAAAAA").mkdir(parents=True)

    result = batch.run(URLS, tmp_path, sleeper=recorder["sleeper"])

    assert result["skipped"] == [URLS[0]]
    assert recorder["ingest"] == URLS[1:]
    assert len(recorder["sleeps"]) == 1


def test_run_records_failures_and_keeps_going(tmp_path, monkeypatch, recorder):
    def flaky(url, content_root, skip_existing=False):
        recorder["ingest"].append(url)
        if url == URLS[1]:
            raise RuntimeError("抓取失败 429")
        out = content_root / f"2026-01-01-{url.rsplit('/', 1)[-1]}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    monkeypatch.setattr(ingest, "ingest", flaky)
    result = batch.run(URLS, tmp_path, sleeper=recorder["sleeper"])

    assert recorder["ingest"] == URLS
    assert result["done"] == [URLS[0], URLS[2]]
    assert [url for url, _ in result["failed"]] == [URLS[1]]
    assert "429" in result["failed"][0][1]
