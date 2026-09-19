# wechat-site

微信公众号文章 → 静态站，Cloudflare Pages 托管 blog.vincentg.net。

## 铁律

- `dist/` 是生成产物但**必须提交**——CF Pages 不跑构建，直接 serve 仓库里的 `dist/`。
- 改了 `content/`、`templates/`、`static/`、`site.config.json` 之后必须重跑 `build.py`。
- 图片一律本地化。`body.html` 里出现 `mmbiz.qpic.cn` 就是 bug（微信图床有防盗链）。
- 正文的内联 `style` 属性不要动，微信排版全靠它。唯一的例外是亮度过低的 `color`
  声明（`_strip_dark_colors`），那是为了深色模式可读，别把这个逻辑去掉。
- Python 用 `.venv/bin/python`，不用 Anaconda。
- 临时文件写本目录 `tmp/`。

## 常用命令

```bash
.venv/bin/python ingest.py "<微信链接>"   # 抓一篇
.venv/bin/python build.py                # 重新生成 dist/
.venv/bin/python -m pytest tests/ -v     # 跑测试
cd dist && python3 -m http.server 8899   # 本地预览
```

## 设计与计划

`docs/superpowers/specs/` 和 `docs/superpowers/plans/`，动结构之前先看。

## 部署形态（容易搞错）

这个站部署成 **Worker**，不是 Pages。Cloudflare 把两者合并进「Workers & Pages」，
新建时默认走 Worker + 静态资源。功能一样，但后台路径不同：

- Worker URL：https://wechat-site.vincentgao99.workers.dev
- 自定义域：https://blog.vincentg.net
- 绑域名的位置是 **Worker → Settings → Domains & Routes → Add → Custom domain**，
  不是 Pages 的 Custom domains 页面
- 静态资源目录是 `dist`

部署配置在 `wrangler.jsonc`（`assets.directory = ./dist`）。两条部署路径：

- **接了 Git**：push 到 `main` → Workers Builds 跑 `npx wrangler deploy`
- **手动兜底**：本地 `npx wrangler deploy`（首次会开浏览器让你授权 Cloudflare）

改配置后可以用 `npx wrangler deploy --dry-run` 校验，这条不需要登录。
