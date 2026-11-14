# 上线三步（全程免费，20 分钟）

> 这个站已经做完了。你要做的只有：注册账号 → 上传 → 打开开关。
> 之后它每天自动更新，不用你再管。

---

## 第 1 步：注册 GitHub（3 分钟）

打开 https://github.com/signup

- 邮箱注册，起个用户名（比如 `funding-rate-cn`）
- 验证邮箱

---

## 第 2 步：建仓库并上传（10 分钟）

### 2.1 新建仓库

点右上角 **+** → **New repository**

- Repository name：`funding-rate`
- 选 **Public**（公开，免费 Pages 需要）
- 不要勾 "Add a README file"
- 点 **Create repository**

### 2.2 上传文件

进入刚建的仓库 → 点 **uploading an existing file**

把 `E:\Myproject\接单变现\toolsite\` 里的这些**上传上去**：

```
build_site.py
requirements.txt
.github/workflows/update.yml     ← 注意：这个要在 .github/workflows/ 目录下
```

> `.github` 文件夹用网页上传比较麻烦。更简单的方法：装 [GitHub Desktop](https://desktop.github.com/)，
> 把整个 `toolsite` 文件夹拖进去，点 Publish，一次搞定。

### 2.3 开启自动更新

1. 仓库 → **Settings** → 左侧 **Actions** → **General**
2. 拉到最下面 **Workflow permissions** → 选 **Read and write permissions** → Save
3. 仓库 → **Settings** → 左侧 **Pages**
4. **Source** 选 **GitHub Actions**（不是 Deploy from a branch）→ Save
5. 仓库 → **Actions** 标签页 → 左侧 **Update funding rates** → 右侧 **Run workflow** → 绿色按钮

等 1–2 分钟，Actions 出现绿色 ✓ 就成功了。

### 2.4 拿到网址

**Settings → Pages** 顶部会显示：

```
Your site is live at https://你的用户名.github.io/funding-rate/
```

这个网址就是你的站，**每 10 分钟自动更新一次**。

---

## 第 3 步：让搜索引擎找到它（可选，但重要）

站点有了，但没人知道。这一步决定有没有流量。

### 3.1 提交给 Google（10 分钟）

1. 打开 https://search.google.com/search-console
2. 添加资源 → 选「网址前缀」→ 填你的 GitHub Pages 网址
3. 验证方式选「HTML 标记」，把给的那行 `<meta>` 复制到 `build_site.py` 的 `<head>` 里
4. 回到 Search Console 点验证
5. 左侧「网址检查」→ 输入你的首页 → 点「请求编入索引」

### 3.2 提交 sitemap

Search Console → 左侧 **Sitemap** → 填 `sitemap.xml` → 提交

（站点已经自动生成好了 `sitemap.xml`，不用额外做）

### 3.3 等

Google 收录通常 **3 天到 2 周**。Bing 更快（https://www.bing.com/webmasters 同样操作）。

---

## 什么时候能开始赚钱

| 阶段 | 时间 | 要做什么 |
|---|---|---|
| 有站点 | 今天 | 上面三步 |
| 被收录 | 3 天–2 周 | 等，同时在 Search Console 看有没有索引 |
| 有自然流量 | 1–3 个月 | 持续更新（自动的），偶尔发外链 |
| 能挂广告 | 日 UV > 100 | 申请 Google AdSense（需要审核，站点要有 about 页——已经做了） |

**AdSense 申请条件**：有独立域名（`xxx.pages.dev` 或 GitHub Pages 子域名基本过不了）、有内容、有隐私政策页。

所以要真正变现，**还得买个域名**（60–80 元/年）。这是唯一的成本。

---

## 想更快变现？两条替代路

### 路 A：挂交易所邀请链接（不用等收录）

在 `build_site.py` 的页脚加一行：

```html
<a href="https://www.binance.com/zh-CN/register?ref=你的邀请码" target="_blank" rel="nofollow">
  注册币安（本站读者专享）
</a>
```

别人从你链接注册并交易，你拿交易手续费返佣（20%–40%）。**这个不需要 AdSense 审核，有流量就有收入。**

### 路 B：卖数据订阅

在页面上加一句「想要实时推送/历史数据/API 访问，加微信 xxx」。

有人来问就报 9.9/月 或 99/年，你手动发数据过去。**零技术成本，纯人工。**

---

## 本地怎么跑（调试用）

```powershell
cd E:\Myproject\接单变现\toolsite
$env:HTTP_PROXY = "http://127.0.0.1:7897"     # 国内需要代理
D:\Anaconda3\python.exe build_site.py
# 产物在 site\index.html，双击打开
```

`--quick` 参数只拉币安，速度快（调试用）。

---

## 常见问题

**Q：Actions 报错 `ccxt` 装不上？**
检查 `requirements.txt` 是否有 `ccxt` 和 `pandas`。

**Q：Actions 跑成功但页面没更新？**
Pages 的 Source 要选 **GitHub Actions**，不是 Deploy from a branch。

**Q：页面打开是 404？**
仓库名是 `funding-rate` 的话，网址要带 `/funding-rate/` 后缀。

**Q：cron 没按时跑？**
GitHub Actions 的 cron 有 5–15 分钟延迟，正常。高峰期可能跳过一两次，下次会补上。
