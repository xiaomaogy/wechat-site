# 微信公众号文章静态站 — 设计

日期：2026-09-19
状态：待实施

## 目标

把「高小猫」公众号的文章搬到自己的域名下，长期托管。第一篇是
[Vipassana 10 日冥想营](https://mp.weixin.qq.com/s/X8no6IXr1-e0GtSaYjhCGA)。
以后每发一篇公众号文章，跑一条命令就能加到站上。

站点地址：`blog.vincentg.net`（Cloudflare Pages + 自定义域）。

## 非目标

- 不做评论、搜索、订阅、RSS 之外的任何动态功能（RSS 也不在第一版）。
- 不抓取阅读数、点赞数、"N 个朋友在看"——这些是微信侧数据，公开页面拿不到。
- 不做后台管理界面。加文章 = 跑脚本 + git push。

## 关键决策：零构建

Cloudflare Pages 的 build command 留空，output directory 设为 `dist/`。
抓取和 HTML 生成全部在本机完成，生成产物直接提交进仓库。

理由：

1. 微信抓取需要特定 UA、可能要重试和手工兜底，放在 CF 的构建容器里跑不通也难排查。
2. 文章量级在一两百篇，本地全量重新生成是秒级操作，没必要增量构建。
3. `dist/` 进仓库意味着「仓库里是什么，线上就是什么」，出问题一眼能看出来。

代价：仓库里有生成产物，diff 会比较吵。可接受。

## 目录结构

```
projects/wechat-site/
├── ingest.py            微信链接 → content/<slug>/
├── build.py             content/ → dist/
├── templates/
│   ├── index.html       目录页模板
│   └── article.html     文章页模板
├── static/
│   ├── style.css        全站样式
│   └── avatar.png       头像
├── content/
│   └── <slug>/
│       ├── meta.json    标题、发布日期、原文链接、封面文件名
│       ├── body.html    正文（已清洗、图片路径已重写）
│       └── images/      本篇所有图片
├── dist/                ← CF Pages 的 output directory
│   ├── index.html
│   ├── p/<slug>/index.html
│   ├── p/<slug>/images/
│   └── static/
├── site.config.json     站名、简介、头像路径、域名
├── README.md
└── CLAUDE.md
```

`slug` 取微信短链的 id（如 `X8no6IXr1-e0GtSaYjhCGA`）加日期前缀，形如
`2026-09-08-X8no6IXr1-e0GtSaYjhCGA`。保证唯一、可回溯、按名字排序即按时间排序。

## 组件

### ingest.py

输入：一个或多个 `https://mp.weixin.qq.com/s/...` 链接。
输出：`content/<slug>/` 三件套。

步骤：

1. 用桌面版 Chrome UA 抓取页面 HTML。
2. 提取字段：
   - 标题 — `<meta property="og:title">`，回退到页面里的 `var msg_title`
   - 发布时间 — 页面里的 `var ct = "<unix秒>"`，回退到 `#publish_time` 文本
   - 正文 — `#js_content` 元素的内部 HTML
   - 封面 — `<meta property="og:image">`
   - 作者/公众号名 — `<meta property="og:article:author">`
3. 正文清洗：
   - 微信把图片真实地址放在 `data-src` 上、`src` 留空 → 统一改写
   - 去掉 `<script>`、`<style>`、微信自有的 `mp-common-*` 交互元素
   - 保留内联 `style` 属性（微信排版靠它，去掉会散架）
4. **图片本地化**（关键）：正文和封面里所有 `mmbiz.qpic.cn` 图片下载到
   `content/<slug>/images/`，文件名用 URL 的 sha1 前 12 位 + 探测到的扩展名，
   HTML 里的引用改成 `images/<文件名>`。
   微信图床有 Referer 防盗链，外链在自己域名下会裂图，所以必须落地。
5. 写 `meta.json` / `body.html`。

幂等：同一个链接重复跑覆盖同一个 slug 目录，不产生重复条目。

错误处理：
- 抓取返回非 200，或页面含「该内容已被发布者删除」「参数错误」 → 报错退出，
  把拿到的原始 HTML 存到 `tmp/wechat-site/<slug>.html` 供人工排查。
- 单张图片下载失败 → 打 WARNING，该图保留微信原链接，不中断整篇。
  最后汇总打印失败图片数。

### build.py

输入：`content/` 下所有文章 + `site.config.json`。
输出：全量重新生成 `dist/`（先清空再写）。

- 每篇文章渲染成 `dist/p/<slug>/index.html`，`images/` 整个目录拷过去。
- 目录页 `dist/index.html`：按发布日期倒序，按「日期」分组（今天 / 具体日期），
  每条一张大卡片：封面图 + 标题 + 日期，整卡可点。
- `static/` 原样拷到 `dist/static/`。
- 模板用 Python 标准库 `string.Template`，不引入 Jinja2 等依赖。

依赖只有 `requests` + `beautifulsoup4`，装在项目自己的 venv 里。

### 页面设计

目录页照公众号主页的样子做：

- 顶部：圆形头像、「高小猫」、地区「越南」、简介
  「一个我用来向自己和向世界解释为什么的地方」、文章数。
- 下面：按日期分组的卡片流，卡片 = 16:9 封面图 + 标题 + 日期。
- 移动端优先，单列；桌面端限制最大宽度 680px 居中。

文章页：标题 + 公众号名 + 日期 + 正文，底部一行「原文发表于微信公众号」带原链接。
正文宽度同样限制在 680px，字号 17px、行高 1.75——微信阅读体验的常见值。

深浅色跟随系统 `prefers-color-scheme`。

## 部署

1. `projects/wechat-site/` 里 `git init`，推到 GitHub 新建的 public 仓库 `wechat-site`
   （账号 xiaomaogy，HTTPS + gh token）。
2. Cloudflare 后台 Workers & Pages → 连接该仓库：
   - Framework preset: None
   - Build command: 空
   - Build output directory: `dist`
3. Custom domains 里加 `blog.vincentg.net`（vincentg.net 已在 Cloudflare 托管，
   NS = coraline/elmo.ns.cloudflare.com，DNS 记录会自动创建）。

第 2、3 步需要在网页后台点击，由用户操作；我给出逐步指引。

之后加文章的流程：

```bash
python3 ingest.py <微信链接>
python3 build.py
git add -A && git commit -m "add: <标题>" && git push
```

## 验收

1. `ingest.py` 对 Vipassana 那篇跑通，`content/` 下三件套齐全，images 目录非空。
2. `build.py` 生成 `dist/`，本地 `python3 -m http.server` 起服务。
3. 用浏览器工具打开目录页和文章页截图，对照用户提供的微信截图核对版式；
   检查正文图片全部显示（无裂图）、移动端宽度正常、深色模式可读。
4. 推到 GitHub，用户在 CF 后台接入，线上 `blog.vincentg.net` 能打开且图片正常。

## 已知风险

- 微信可能对服务器 IP 做频率限制或要求验证。若首次抓取就被拦，
  退路是用浏览器工具打开文章页取 HTML，或让用户从后台复制原文。
- 微信正文严重依赖内联样式，个别老文章可能排版走样。逐篇发现逐篇修，
  不预先做通用兼容。
