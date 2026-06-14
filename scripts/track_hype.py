#!/usr/bin/env python3
"""HYPE代币跟踪 — 支持中文网络环境

价格源（中国可访问）:
  1. OKX API (可能不通)
  2. 非小号 (可能不通)
  3. 所有API不通时，用脚本本地记录"获取失败"

新闻源（中国可访问）:
  1. Google News RSS (可能不通)
  2. Baidu 搜索 HYPE/Hyperliquid
"""
import sys, json, sqlite3, re
from pathlib import Path
from datetime import datetime, date
from urllib.request import urlopen, Request
from urllib.error import URLError

DB = str(Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db')
REPORT_DIR = Path.home() / 'Jarvis' / 'AI研报'


def _fetch(url: str, timeout: int = 5) -> str | None:
    """通用HTTP GET，短超时"""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*',
        })
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return None


def fetch_price_multi() -> dict | None:
    """多源尝试获取HYPE价格"""
    sources = [
        # OKX
        ('https://www.okx.com/api/v5/market/ticker?instId=HYPE-USDT', 'okx', lambda d: {
            'price': float(d['data'][0]['last']),
            'change_24h': float(d['data'][0].get('change24h', 0) or 0),
            'volume_24h': float(d['data'][0].get('volCcy24h', 0) or 0),
            'source': 'okx',
        }),
        # CoinGecko (中文节点)
        ('https://api.coingecko.com/api/v3/simple/price?ids=hyperliquid&vs_currencies=usd&include_24hr_change=true', 'coingecko', lambda d: {
            'price': d['hyperliquid']['usd'],
            'change_24h': d['hyperliquid'].get('usd_24h_change', 0),
            'source': 'coingecko',
        }),
        # Binance
        ('https://api.binance.com/api/v3/ticker/24hr?symbol=HYPEUSDT', 'binance', lambda d: {
            'price': float(d['lastPrice']),
            'change_24h': float(d['priceChangePercent']),
            'volume_24h': float(d['quoteVolume']),
            'source': 'binance',
        }),
    ]
    for url, name, parser in sources:
        raw = _fetch(url)
        if raw:
            try:
                data = json.loads(raw)
                return parser(data)
            except Exception:
                continue
    return None


def fetch_news_baidu() -> list[dict]:
    """从Baidu搜索HYPE相关新闻"""
    news = []
    try:
        html = _fetch('https://www.baidu.com/s?wd=Hyperliquid+HYPE+crypto&ie=utf-8&rn=10', timeout=6)
        if html and '百度安全验证' not in html and len(html) > 10000:
            titles = re.findall(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
            links = re.findall(r'<a[^>]*href="(http[^"]+)"[^>]*>', html)
            for i, t in enumerate(titles[:8]):
                title = re.sub(r'<[^>]+>', '', t).strip()
                link = links[i] if i < len(links) else ''
                news.append({'title': title, 'source': '百度', 'link': link, 'published': ''})
    except Exception:
        pass
    return news


def fetch_news_odaily() -> list[dict]:
    """从Odaily星球日报搜索HYPE（中文加密新闻，可能有反爬）"""
    news = []
    try:
        # Odaily搜索
        raw = _fetch('https://www.odaily.news/api/search?keyword=HYPE&page=1&size=10', timeout=6)
        if raw:
            data = json.loads(raw)
            for item in data.get('data', {}).get('list', [])[:8]:
                news.append({
                    'title': item.get('title', ''),
                    'source': 'Odaily',
                    'link': f'https://www.odaily.news/post/{item.get("id", "")}',
                    'published': item.get('published_at', ''),
                })
    except Exception:
        pass
    return news


def fetch_news_google() -> list[dict]:
    """从Google News搜索HYPE（中国可能不通，备用）"""
    news = []
    try:
        raw = _fetch('https://news.google.com/rss/search?q=Hyperliquid+HYPE+crypto&hl=zh-CN&gl=CN', timeout=5)
        if raw:
            titles = re.findall(r'<title>(.*?)</title>', raw)
            links = re.findall(r'<link>(.*?)</link>', raw)
            for i, title in enumerate(titles[1:9]):
                link = links[i + 1] if i + 1 < len(links) else ''
                news.append({'title': title, 'source': 'Google News', 'link': link, 'published': ''})
    except Exception:
        pass
    return news


def save_to_db(price_data: dict | None, news: list[dict]):
    """保存跟踪数据"""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if price_data:
        cur.execute('''
            INSERT INTO token_tracking (token_symbol, price, change_24h, volume_24h, market_cap, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('HYPE', price_data.get('price'), price_data.get('change_24h'),
              price_data.get('volume_24h', 0), price_data.get('market_cap', 0),
              price_data.get('source', 'unknown'), now))

    cur.execute('UPDATE kg_tracked_topics SET last_checked = ? WHERE topic_name LIKE ?', (now, '%HYPE%'))
    conn.commit()
    conn.close()


def generate_report(price_data: dict | None, news: list[dict]) -> str:
    """生成Markdown报告"""
    today = date.today().isoformat()
    lines = [f'# HYPE 跟踪日报 · {today}', '']

    # 价格
    if price_data:
        p = price_data['price']
        c = price_data.get('change_24h', 0)
        arrow = '📈' if c >= 0 else '📉'
        lines.append(f'**价格**: ${p}')
        lines.append(f'**24h涨跌**: {arrow} {c:+.2f}%')
        if price_data.get('volume_24h'):
            lines.append(f'**24h成交量**: ${price_data["volume_24h"]:,.0f}')
        lines.append(f'**来源**: {price_data.get("source", "unknown")}')
    else:
        lines.append('**价格**: 获取失败（API受限）')

    # 新闻
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

    # 叙事背景
    lines.append('---')
    lines.append('## 🧠 叙事背景')
    lines.append('')
    lines.append('HYPE是Hyperliquid链的原生代币，Hyperliquid是crypto-native代币化股票赛道的核心基础设施：')
    lines.append('- 提供SpaceX pre-IPO永续合约')
    lines.append('- Felix×Ondo上链股票ETF')
    lines.append('- 与华尔街派(NYSE/Nasdaq)形成竞争生态')
    lines.append('- 属于RWA/代币化叙事阵营')
    lines.append('')
    lines.append(f'*生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}*')

    return '\n'.join(lines)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print(f'🔍 HYPE跟踪 ({mode})...')

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
        print('  📰 获取新闻(百度)...')
        news = fetch_news_baidu()
        if not news:
            print('  📰 获取新闻(Odaily)...')
            news = fetch_news_odaily()
        if not news:
            print('  📰 获取新闻(Google)...')
            news = fetch_news_google()
        print(f'  ✅ {len(news)}条新闻')

    save_to_db(price_data, news)
    print('  💾 已保存')

    report = generate_report(price_data, news)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f'HYPE跟踪_{date.today().isoformat()}.md'
    path.write_text(report, encoding='utf-8')
    print(f'  📄 {path}')

    if price_data:
        print(f'\n📊 HYPE: ${price_data["price"]} ({price_data["change_24h"]:+.2f}%)')
    print(f'📰 新闻: {len(news)}条')


if __name__ == '__main__':
    main()
