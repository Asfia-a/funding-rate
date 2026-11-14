"""资金费率跨交易所对比站 · 完整版

产出（site/ 目录，可直接上传 Cloudflare Pages / GitHub Pages）：
  index.html      主页面（跨交易所对比）
  data.json       原始数据（供二次开发）
  sitemap.xml     SEO 站点地图
  robots.txt      SEO 爬虫规则
  about.html      说明页（提 AdSense 审核需要）

差异点（别人没有的）
------------------
主流同类站只显示单一交易所。这里把 Binance / OKX / Bybit 三家同一币种的
资金费率并排放，并标出「哪家最值得做空收租」——这是套利者的真实决策依据。

用法
----
    python build_site.py              # 三交易所全量
    python build_site.py --quick      # 只用 Binance，快速验证
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

PROXY = os.environ.get("HTTP_PROXY") or None   # 本地跑设环境变量；GitHub Actions 在国外不需要代理
OUT = Path("site")

EXCHANGES = [
    # (ccxt id, 中文名, 英文名, defaultType)
    # OKX 的 defaultType 必须用 swap，否则 fetch_tickers 只返回交割合约（USD:USD-YYMMDD），拿不到 USDT 永续
    ("binance", "币安", "Binance", "future"),
    ("okx", "欧易", "OKX", "swap"),
    ("bybit", "Bybit", "Bybit", "future"),
]
TOP_N = 60


def make_ex(ex_id: str, default_type: str = "future") -> ccxt.Exchange:
    return getattr(ccxt, ex_id)({
        "enableRateLimit": True,
        "timeout": 30000,
        "proxies": {"http": PROXY, "https": PROXY},
        "options": {"defaultType": default_type},
    })


def _quote_volume(t: dict) -> float:
    """各交易所 ticker 字段不一致，这里做多级回退，避免因缺少 quoteVolume 漏掉全部标的。"""
    try:
        v = float(t.get("quoteVolume") or 0)
        if v > 0:
            return v
    except Exception:  # noqa: BLE001
        pass
    try:
        bv = float(t.get("baseVolume") or 0)
        last = float(t.get("last") or 0)
        if bv > 0 and last > 0:
            return bv * last
    except Exception:  # noqa: BLE001
        pass
    info = t.get("info") or {}
    try:
        v = float(info.get("volCcy24h") or info.get("quote_volume") or 0)
        last = float(t.get("last") or 0)
        if v > 0 and last > 0:
            return v * last
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def fetch_one(ex_id: str, top_n: int = TOP_N, default_type: str = "future") -> pd.DataFrame:
    """返回该交易所 funding 数据：code / funding_pct / ann_pct / mark"""
    ex = make_ex(ex_id, default_type)
    ex.load_markets()
    tickers = ex.fetch_tickers()

    rows = []
    for sym, t in tickers.items():
        m = ex.markets.get(sym)
        if not m or m.get("type") not in ("swap", "future") or not m.get("active"):
            continue
        if m.get("quote") != "USDT":
            continue
        qv = _quote_volume(t)
        if qv > 0:
            rows.append((sym, qv))

    rows.sort(key=lambda x: x[1], reverse=True)
    targets = [s for s, _ in rows[:top_n]]

    out = []
    for sym in targets:
        try:
            fr = ex.fetch_funding_rate(sym)
            rate = float(fr.get("fundingRate") or 0)
            if rate == 0:
                continue
            info = fr.get("info") or {}
            mark = float(info.get("markPrice") or 0) or float(fr.get("markPrice") or 0) or 0.0
            base = sym.split("/")[0]
            out.append({
                "code": base,
                "funding_pct": rate * 100,
                "ann_pct": rate * 3 * 365 * 100,
                "mark": mark,
            })
            time.sleep(0.1)
        except Exception:  # noqa: BLE001
            continue

    df = pd.DataFrame(out)
    if df.empty:
        raise RuntimeError(f"{ex_id} 无数据")
    return df.drop_duplicates("code", keep="first")


def build_grid(quick: bool = False) -> tuple[pd.DataFrame, list[str], dict]:
    use = EXCHANGES[:1] if quick else EXCHANGES
    frames = {}
    stats = {}
    use_full = use if isinstance(use[0], tuple) and len(use[0]) == 4 else [(e, z, en, 'future') for e, z, en in use]
    for ex_id, zh, en, dtype in use_full:
        try:
            df = fetch_one(ex_id, TOP_N, dtype)
            frames[zh] = df.set_index("code")["ann_pct"]
            stats[zh] = {"count": len(df), "ok": True}
            print(f"  {zh:6s} {len(df):3d} 个币种  最高 {df['ann_pct'].max():+.2f}%")
        except Exception as exc:  # noqa: BLE001
            stats[zh] = {"count": 0, "ok": False, "err": str(exc)[:80]}
            print(f"  {zh:6s} 失败: {type(exc).__name__}")

    if not frames:
        raise RuntimeError("所有交易所都取数失败")

    grid = pd.DataFrame(frames)
    grid["count"] = grid.notna().sum(axis=1)
    grid["best"] = grid[[c for c in frames]].max(axis=1)
    grid = grid.sort_values(["count", "best"], ascending=[False, False])
    return grid, list(frames), stats


def build_html(grid: pd.DataFrame, cols: list[str], stats: dict, now: str) -> str:
    total = len(grid)
    pos = int((grid["best"] > 0).sum())
    spread_rows = grid[grid["count"] >= 2]

    rows = []
    for code, r in grid.iterrows():
        cells = []
        for c in cols:
            v = r.get(c)
            if pd.isna(v):
                cells.append('<td class="num na">—</td>')
            else:
                cls = "pos" if v > 0 else "neg"
                cells.append(f'<td class="num {cls}">{v:+.2f}%</td>')
        best = r["best"]
        bcls = "pos" if best > 0 else "neg"
        hint = "做空收租" if best > 0 else "做多收租"
        rows.append(
            f'<tr><td class="sym">{code}</td>{"".join(cells)}'
            f'<td class="num {bcls} strong">{best:+.2f}%</td>'
            f'<td class="hint">{hint}</td></tr>'
        )

    # 交易所之间差距最大的币（真正的套利机会）
    arb = []
    if len(spread_rows):
        tmp = spread_rows.copy()
        vcols = [c for c in cols if c in tmp.columns]
        tmp["spread"] = tmp[vcols].max(axis=1) - tmp[vcols].min(axis=1)
        tmp = tmp.sort_values("spread", ascending=False).head(8)
        for code, r in tmp.iterrows():
            vals = " / ".join(
                f"{c} {r[c]:+.2f}%" for c in vcols if not pd.isna(r.get(c))
            )
            arb.append(f"<li><b>{code}</b>　{vals}　<span class='gap'>差 {r['spread']:.2f}%</span></li>")

    stat_cards = "".join(
        f'<div class="stat"><div class="k">{zh}</div>'
        f'<div class="v">{"—" if not s["ok"] else s["count"]}</div></div>'
        for zh, s in stats.items()
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>永续合约资金费率对比 · 币安/OKX/Bybit 实时排行</title>
<meta name="description" content="实时对比币安、OKX、Bybit 三大交易所的永续合约资金费率，按年化排序，标出做空收租收益最高和跨所价差最大的币种。每 10 分钟更新。">
<meta name="keywords" content="资金费率,funding rate,永续合约,套利,币安,OKX,Bybit,做空收租">
<meta property="og:title" content="永续合约资金费率对比 · 币安/OKX/Bybit">
<meta property="og:description" content="一眼看出哪个币做空收租收益最高，哪家交易所费率最划算。">
<meta property="og:type" content="website">
<link rel="canonical" href="./">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Dataset",
 "name":"永续合约资金费率对比数据",
 "description":"币安/OKX/Bybit USDT 永续合约资金费率，按年化排序",
 "temporalCoverage":"{now[:10]}",
 "creator":{{"@type":"Organization","name":"FundingRate Compare"}}}}
</script>
<style>
:root{{--bg:#0a0e14;--card:#12171f;--line:#1e252f;--fg:#e6edf3;--muted:#7d8590;
      --pos:#3fb950;--neg:#f85149;--accent:#58a6ff;--gold:#d29922}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--fg);font:14px/1.65 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;padding:24px 16px}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:21px;font-weight:600;margin-bottom:6px;letter-spacing:-.2px}}
.sub{{color:var(--muted);font-size:13px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:18px 0}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}}
.stat .k{{color:var(--muted);font-size:12px;margin-bottom:2px}}
.stat .v{{font-size:19px;font-weight:600}}
.tip{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:6px;padding:12px 14px;margin:16px 0;color:var(--muted);font-size:13px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:16px 0}}
.panel h2{{font-size:14px;font-weight:600;margin-bottom:10px;color:var(--gold)}}
.panel ul{{list-style:none;font-size:13px}}
.panel li{{padding:5px 0;border-bottom:1px dashed var(--line);color:var(--muted)}}
.panel li:last-child{{border:none}}
.panel b{{color:var(--fg)}}
.gap{{color:var(--gold);font-weight:600}}
table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:8px;overflow:hidden;margin-top:8px}}
thead{{background:#171d26}}
th{{text-align:left;padding:10px 12px;font-size:12px;color:var(--muted);font-weight:500}}
td{{padding:9px 12px;border-top:1px solid var(--line)}}
tr:hover td{{background:#171d26}}
.sym{{font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.num.strong{{font-weight:600}}
.na{{color:#484f58}}
.pos{{color:var(--pos)}} .neg{{color:var(--neg)}}
.hint{{color:var(--muted);font-size:12px}}
footer{{margin-top:26px;color:var(--muted);font-size:12px;line-height:1.9}}
footer a{{color:var(--accent);text-decoration:none}}
@media(max-width:640px){{.hide-sm{{display:none}}h1{{font-size:17px}}th,td{{padding:8px 6px;font-size:13px}}}}
</style>
</head>
<body>
<div class="wrap">
  <h1>永续合约资金费率对比</h1>
  <div class="sub">币安 · OKX · Bybit ｜ 按年化排序 ｜ 更新于 {now}</div>

  <div class="stats">
    {stat_cards}
    <div class="stat"><div class="k">覆盖币种</div><div class="v">{total}</div></div>
    <div class="stat"><div class="k">正费率</div><div class="v">{pos}</div></div>
  </div>

  <div class="tip">
    资金费率为正 → 做多的人付钱给做空的人。<b>现货买入 + 永续做空</b>可对冲价格风险，只收这笔「租金」。
    年化 3% 以上通常值得做；同一币种在不同交易所费率不同，<b>挑最高的那家做</b>。
  </div>

  {f'<div class="panel"><h2>跨所价差 Top 8（同一币，不同交易所差多少）</h2><ul>{"".join(arb)}</ul></div>' if arb else ''}

  <table>
    <thead>
      <tr>
        <th>币种</th>
        {''.join(f'<th class="num">{c}</th>' for c in cols)}
        <th class="num">最高</th>
        <th class="hide-sm">方向</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <footer>
    数据来源：各交易所公共 API，每 10 分钟自动更新。<br>
    本页仅作数据展示，不构成投资建议。合约交易有风险，请自行判断。<br>
    <a href="./about.html">关于本站</a>
  </footer>
</div>
</body>
</html>"""


def build_about(now: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>关于本站 · 资金费率对比</title>
<style>
body{{background:#0a0e14;color:#e6edf3;font:14px/1.8 -apple-system,"PingFang SC",sans-serif;
     max-width:760px;margin:0 auto;padding:32px 20px}}
h1{{font-size:20px;margin-bottom:16px}} h2{{font-size:15px;margin:22px 0 8px;color:#d29922}}
p{{color:#8b949e;margin-bottom:10px}} a{{color:#58a6ff}}
</style>
</head>
<body>
<h1>关于本站</h1>

<h2>这是什么</h2>
<p>一个把币安、OKX、Bybit 三家交易所的永续合约资金费率放在一起对比的页面。
按年化收益排序，标出哪个币做空收租收益最高、哪家交易所费率最划算。</p>

<h2>资金费率是什么</h2>
<p>永续合约没有到期日，为了让合约价格贴近现货，交易所每 8 小时在多头和空头之间收付一笔费用，这就是资金费率。
费率为正时多头付钱给空头；为负时反过来。</p>

<h2>怎么用这个数据</h2>
<p>常见做法是「现货买入 + 永续做空」等量对冲：价格涨跌互相抵消，只稳定收取资金费。
年化 3% 以上通常值得做，低于 1% 扣掉手续费就不划算了。</p>

<h2>数据来源与更新</h2>
<p>全部数据来自各交易所公开 API，未经人工修改。页面每 10 分钟自动重新生成。更新于 {now}。</p>

<h2>免责声明</h2>
<p>本站仅作数据展示，不构成任何投资建议。加密货币与合约交易存在高风险，可能导致本金全部损失。
请自行判断并承担相应风险。</p>

<p style="margin-top:28px"><a href="./">← 返回首页</a></p>
</body>
</html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只拉 Binance（快速验证）")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print("[1/3] 拉取各交易所资金费率…")
    grid, cols, stats = build_grid(args.quick)

    print(f"\n[2/3] 生成页面（{len(grid)} 个币种，{len(cols)} 家交易所）…")
    OUT.mkdir(parents=True, exist_ok=True)
    html = build_html(grid, cols, stats, now)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "about.html").write_text(build_about(now), encoding="utf-8")

    print("[3/3] SEO 文件…")
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", encoding="utf-8"
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>/</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>\n'
        f'  <url><loc>/about.html</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.5</priority></url>\n'
        '</urlset>\n',
        encoding="utf-8",
    )

    records = []
    for code, r in grid.iterrows():
        rec = {"code": code}
        for c in cols:
            v = r.get(c)
            rec[c] = None if pd.isna(v) else round(float(v), 4)
        rec["best"] = round(float(r["best"]), 4)
        records.append(rec)
    (OUT / "data.json").write_text(
        json.dumps({"updated": now, "rows": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n完成！产物在 {OUT.resolve()}")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name:14s} {f.stat().st_size:>8,} 字节")


if __name__ == "__main__":
    main()

