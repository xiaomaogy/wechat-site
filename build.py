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
