#!/usr/bin/env python3
"""SPCX (SpaceX) 股票跟踪 — 支持中文网络环境

价格源:
  1. Yahoo Finance (query1.finance.yahoo.com) — 美股行情主源
  2. 新浪财经 (hq.sinajs.cn) — 中国可访问备选

新闻源:
  1. Google News RSS
  2. Baidu 搜索 SpaceX/SPCX

依赖: yfinance (pip install yfinance)
"""
import sys, json, re
from pathlib import Path
from datetime import datetime, date
from urllib.request import urlopen, Request
from urllib.error import URLError

REPORT_DIR = Path.home() / 'Jarvis' / 'AI研报'

YAHOO_QUOTE = "https://query1.finance.yahoo.com/v8/finance/chart/SPCX?range=1d&interval=1d"
YAHOO_INFO = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/SPCX?modules=summaryDetail,price"


def _fetch(url: str, timeout: int = 10) -> str | None:
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None


def fetch_price_yahoo() -> dict | None:
    """从Yahoo Finance获取SPCX实时行情"""
    raw = _fetch(YAHOO_QUOTE, timeout=10)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        result = data.get('chart', {}).get('result', [])
        if not result:
            return None
        meta = result[0].get('meta', {})
        indicators = result[0].get('indicators', {})
        quote = (indicators.get('quote', [{}])[0] or {})
        closes = quote.get('close', [])
        volumes = quote.get('volume', [])
        current_price = meta.get('regularMarketPrice') or meta.get('chartPreviousClose') or (closes[-1] if closes else None)
        prev_close = meta.get('chartPreviousClose') or (closes[-2] if len(closes) >= 2 else current_price)
        change_24h = ((current_price - prev_close) / prev_close * 100) if (current_price and prev_close) else 0
        volume = int(volumes[-1]) if volumes else 0
        return {
            'price': round(current_price, 2) if current_price else 0,
            'change_24h': round(change_24h, 2),
            'volume': volume,
            'prev_close': round(prev_close, 2) if prev_close else 0,
            'source': 'yahoo',
        }
    except Exception:
        return None


def fetch_price_sina() -> dict | None:
    """从新浪财经获取SPCX行情（us_SPCX）"""
    raw = _fetch('https://hq.sinajs.cn/list=us_SPCX', timeout=8)
    if raw:
        try:
            # 格式: var hq_str_us_SPCX="SpaceX,...";
            match = re.search(r'"(.*?)"', raw)
            if match:
                parts = match.group(1).split(',')
                if len(parts) >= 4:
                    name = parts[0]
                    price = float(parts[1]) if parts[1] else 0
                    change_pct = float(parts[4]) if len(parts) > 4 else 0
                    volume = int(parts[5]) if len(parts) > 5 else 0
                    return {
                        'price': price,
                        'change_24h': change_pct,
                        'volume': volume,
                        'source': 'sina',
                        'name': name,
                    }
        except Exception:
            pass
    return None


def fetch_price_multi() -> dict | None:
    sources = [
        ('yahoo', fetch_price_yahoo),
        ('sina', fetch_price_sina),
    ]
    for name, fn in sources:
        result = fn()
        if result and result.get('price', 0) > 0:
            return result
    return None


def fetch_news_google() -> list[dict]:
    news = []
    try:
        raw = _fetch('https://news.google.com/rss/search?q=SpaceX+SPXC+stock&hl=en-US&gl=US', timeout=6)
        if raw:
            titles = re.findall(r'<title>(.*?)</title>', raw)
            links = re.findall(r'<link>(.*?)</link>', raw)
            seen = set()
            for i, title in enumerate(titles[1:12]):
                title_clean = title.strip()
                if title_clean and title_clean not in seen:
                    seen.add(title_clean)
                    link = links[i + 1] if i + 1 < len(links) else ''
                    news.append({'title': title_clean, 'source': 'Google News', 'link': link})
    except Exception:
        pass
    return news


def fetch_news_baidu() -> list[dict]:
    news = []
    try:
        html = _fetch('https://www.baidu.com/s?wd=SpaceX+SPCX+IPO&ie=utf-8&rn=10', timeout=8)
        if html and '百度安全验证' not in html and len(html) > 10000:
            titles = re.findall(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
            links = re.findall(r'<a[^>]*href=\"(http[^\"]+)\"[^>]*>', html)
            for i, t in enumerate(titles[:8]):
                title = re.sub(r'<[^>]+>', '', t).strip()
                link = links[i] if i < len(links) else ''
                news.append({'title': title, 'source': '百度', 'link': link})
    except Exception:
        pass
    return news


def generate_report(price_data: dict | None, news: list[dict]) -> str:
    today = date.today().isoformat()
    lines = [f'# SPCX (SpaceX) 跟踪日报 · {today}', '']

    if price_data:
        p = price_data['price']
        c = price_data.get('change_24h', 0)
        arrow = '📈' if c >= 0 else '📉'
        lines.append(f'**价格**: ${p}')
        lines.append(f'**涨跌幅**: {arrow} {c:+.2f}%')
        lines.append(f'**昨收**: ${price_data.get("prev_close", "-")}')
        if price_data.get('volume'):
            lines.append(f'**成交量**: {price_data["volume"]:,}')
        lines.append(f'**来源**: {price_data.get("source", "unknown")}')
    else:
        lines.append('**价格**: 获取失败（API受限）')

    lines.append('')
    lines.append('---')
    lines.append('## 📰 相关新闻')
    if news:
        for n in news:
            lines.append(f'- **{n["title"]}**')
            lines.append(f'  {n["source"]}')
            if n.get('link'):
                lines.append(f'  [链接]({n["link"]})')
            lines.append('')
    else:
        lines.append('暂无新闻（搜索源受限）')
        lines.append('')

    lines.append('---')
    lines.append('## 🧠 叙事背景')
    lines.append('')
    lines.append('SpaceX (SPCX) 于2026年6月在纳斯达克上市，代码SPCX：')
    lines.append('- IPO定价$135，首日收$161.11（+19%），估值$2T+')
    lines.append('- Starlink（星链）：500万+用户，已盈利，营收主力')
    lines.append('- 发射服务：全球70%商业发射份额（Falcon 9/Falcon Heavy）')
    lines.append('- Starship：下一代超重型火箭，即将商业运营')
    lines.append('- Dragon：NASA唯一认证商业载人飞船')
    lines.append('- 创始人/CEO: Elon Musk')
    lines.append('')
    lines.append(f'*生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}*')

    return '\n'.join(lines)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print(f'🔍 SPCX跟踪 ({mode})...')

    price_data = None
    news = []

    if mode in ('all', 'price'):
        print('  📊 获取价格...')
        price_data = fetch_price_multi()
        if price_data:
            print(f'  ✅ ${price_data["price"]} ({price_data["change_24h"]:+.2f}%) [{price_data["source"]}]')
        else:
            print('  ⚠️ 全部价格源不通')

    if mode in ('all', 'news'):
        print('  📰 获取新闻(Google)...')
        news = fetch_news_google()
        if not news:
            print('  📰 获取新闻(百度)...')
            news = fetch_news_baidu()
        print(f'  ✅ {len(news)}条新闻')

    report = generate_report(price_data, news)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f'SPCX跟踪_{date.today().isoformat()}.md'
    path.write_text(report, encoding='utf-8')
    print(f'  📄 {path}')

    if price_data:
        print(f'\n📊 SPCX: ${price_data["price"]} ({price_data["change_24h"]:+.2f}%)')
    print(f'📰 新闻: {len(news)}条')


if __name__ == '__main__':
    main()
