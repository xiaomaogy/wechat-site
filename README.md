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

## 抓取时会自动做的两件清洗

- **去掉正文开头重复的标题**：微信编辑器里作者常把标题在正文里再写一遍。
- **剥掉写死的深色文字色**：微信给每段都盖上 `color: rgb(36,42,38)` 这类近黑色，
  深色模式下会看不见。亮度低于阈值的 `color` 声明会被去掉，改用站点主题色；
  亮色（作者真正想强调的）保留。其余内联样式一律不动。

## 换头像

把图片放到 `static/`，改 `site.config.json` 的 `avatar` 字段，重跑 `build.py`。

## 封面图的限制

微信公众页只暴露分享用的缩略图（这篇是 299×127），拿不到原图。
铺到卡片上会略糊，跟微信 App 里看到的是同一张。
想要更清晰的封面，就把自己的图放进 `content/<slug>/images/`，
再把 `meta.json` 的 `cover` 改成那个文件名。

## 开发

```bash
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -v
```

本地预览：

```bash
cd dist && python3 -m http.server 8899
```
