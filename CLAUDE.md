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

## 踩过的坑：push 不触发构建

症状：push 之后线上不更新，GitHub 上连 check run 都没有（失败的构建也会留记录，
**零记录说明根本没被通知到**）。

原因：Cloudflare 的 GitHub App 安装时选的是 "Only select repositories"，
新建的仓库不在授权列表里，push 通知发不到 Cloudflare。

排查顺序：

1. `gh api repos/xiaomaogy/wechat-site/commits/<sha>/check-runs` —— 有没有构建记录
2. 没有记录 → https://github.com/settings/installations → Cloudflare Workers →
   Repository access 改成 All repositories（或把本仓库加进白名单）
3. 有记录但失败 → 去 Worker 的 Deployments 页看构建日志

验证方法：推一个改动 `dist/` 的 commit，等构建完成，
`fetch('https://blog.vincentg.net/')` 看内容有没有变。

## 批量导入历史文章

文章列表拿不到公开接口，必须登录公众号后台。流程：

1. 浏览器面板打开 `https://mp.weixin.qq.com/`，**让用户扫码**（不要碰凭据）
2. 登录后 URL 里有 `token`，同源 fetch 这个接口翻页：

   `/cgi-bin/appmsgpublish?sub=list&search_field=null&begin=<N>&count=20&query=&fakeid=&type=101_1&free_publish_type=1&sub_action=list_ex&token=<token>&lang=zh_CN&f=json&ajax=1`

   返回的 `publish_page` 是 JSON 字符串，里面 `publish_list[].publish_info`
   又是 JSON 字符串，其中 `appmsgex[]` 才有 `title` / `link` / `create_time`。
   一次群发可能含多篇，所以条数 ≠ 文章数。
3. 链接写进一个文本文件，`batch.py <文件>` 跑。

截图传不到用户那边，要给用户看东西（比如登录二维码）必须用 SendUserFile 发文件。

## 图片扩展名按内容定，不按 URL

微信正文里的装饰图标是 SVG，但 URL 上看不出格式。只按 URL 猜会默认 `.jpg`，
静态托管按扩展名发 `image/jpeg`，浏览器拿到 SVG 内容就裂图。
`wxparse.sniff_ext` 按文件头嗅探真实格式，`download_images` 据此纠正扩展名
并把改名回写进正文和封面字段。别退回只看 URL 的做法。
