"""知识图谱 API — 基于本体的实体提取与关系发现"""

from fastapi import APIRouter, HTTPException
import sqlite3, json, os, re
from datetime import datetime
import requests as _requests

DB_PATH = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")

router = APIRouter(tags=["知识图谱"])

# ─── 数据库初始化 ────────────────────────────────────────
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS kg_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '',
            source TEXT DEFAULT 'text',
            content TEXT NOT NULL,
            summary TEXT DEFAULT '',
            entities TEXT DEFAULT '[]',
            relations TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS kg_entity_stats (
            name TEXT PRIMARY KEY,
            entity_type TEXT DEFAULT '',
            category TEXT DEFAULT '',
            count INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS kg_relation_stats (
            source TEXT,
            target TEXT,
            relation TEXT,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (source, target, relation)
        );
    """)
    # 兼容旧表: 如果 entity_type 列不存在则添加
    try:
        c.execute("ALTER TABLE kg_entity_stats ADD COLUMN entity_type TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 已经存在
    # 兼容旧表: 如果 summary 列不存在则添加
    try:
        c.execute("ALTER TABLE kg_articles ADD COLUMN summary TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

_init_db()

# ─── 缓存: stock_info 全表 ──────────────────────────────
_stock_cache = None
_concept_board_cache = None

def _load_stocks():
    global _stock_cache
    if _stock_cache is None:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT code, name, industry, concepts FROM stock_info")
        _stock_cache = [{"code":r[0],"name":r[1],"industry":r[2] or "","concepts":r[3] or ""} for r in c.fetchall()]
        conn.close()
    return _stock_cache

def _load_concept_boards():
    global _concept_board_cache
    if _concept_board_cache is None:
        try:
            import akshare as ak
            df = ak.stock_board_concept_name_em()
            _concept_board_cache = set(df['board_name'].tolist())
        except Exception:
            _concept_board_cache = set()
    return _concept_board_cache

def _load_industry_chains():
    """加载产业链定义"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT industry, chain_data FROM industry_chain")
    chains = {}
    for ind, data in c.fetchall():
        try:
            chains[ind] = json.loads(data)
        except Exception:
            pass
    conn.close()
    return chains

# ─── 实体词库 ────────────────────────────────────────────
# 产品/服务关键词 — 当文本中出现这些词时，提取为 Product 实体
PRODUCT_KEYWORDS = [
    "芯片", "GPU", "CPU", "FPGA", "ASIC", "NPU", "TPU", "存储器",
    "光模块", "光芯片", "光器件", "CPO", "PCB", "传感器",
    "电池", "电机", "电控", "逆变器", "变流器",
    "材料", "硅片", "晶圆", "光刻胶", "靶材", "电解液", "隔膜", "正极材料", "负极材料",
    "设备", "光刻机", "刻蚀设备", "薄膜设备", "检测设备", "封测设备",
    "服务器", "交换机", "路由器", "基站",
    "操作系统", "数据库", "中间件", "SaaS", "PaaS", "IaaS",
    "算法", "大模型", "MLOps", "EDA",
    "液冷", "散热", "电源",
    "镜头", "模组", "屏幕", "面板",
]

# 产业链环节关键词
LINK_KEYWORDS = ["上游", "中游", "下游", "环节", "产业链"]

# 已知非A股企业
KNOWN_ORGS = {
    "百度": "互联网", "阿里": "互联网", "腾讯": "互联网", "华为": "通信设备",
    "字节跳动": "互联网", "美团": "互联网", "京东": "互联网", "拼多多": "互联网",
    "商汤科技": "AI", "旷视科技": "AI", "云从科技": "AI", "依图科技": "AI", "第四范式": "AI",
    "MiniMax": "AI", "月之暗面": "AI", "智谱AI": "AI", "百川智能": "AI", "零一万物": "AI",
    "OpenAI": "AI", "Google": "互联网", "Microsoft": "软件", "Meta": "互联网",
    "NVIDIA": "芯片", "AMD": "芯片", "Intel": "芯片", "ARM": "芯片",
    "英伟达": "芯片", "特斯拉": "新能源汽车",
    "地平线": "AI", "燧原科技": "芯片", "壁仞科技": "芯片", "摩尔线程": "芯片",
}

# ─── 实体提取 ────────────────────────────────────────────
def _extract_entities(text: str) -> list[dict]:
    """提取5类实体: Company / Product / IndustryLink / Concept / Industry"""
    entities = []
    seen = set()
    stocks = _load_stocks()
    board_names = _load_concept_boards()

    # ── 1. Company: 匹配股票代码 ──
    codes = set(re.findall(r'\b(\d{6})\b', text))
    for s in stocks:
        if s["code"] in codes:
            key = f"company:{s['code']}"
            if key not in seen:
                seen.add(key)
                entities.append({
                    "id": key, "name": s["name"], "code": s["code"],
                    "entity_type": "company", "category": s["industry"],
                    "attributes": {"industry": s["industry"], "concepts": s["concepts"]},
                    "source": "stock_code"
                })

    # ── 2. Company: 从 stock_info 匹配公司名称 ──
    for s in stocks:
        key = f"company:{s['code']}"
        if key not in seen and s["name"] in text:
            seen.add(key)
            entities.append({
                "id": key, "name": s["name"], "code": s["code"],
                "entity_type": "company", "category": s["industry"],
                "attributes": {"industry": s["industry"], "concepts": s["concepts"]},
                "source": "stock_name"
            })

    # ── 3. Company: 已知非A股企业 ──
    stock_names = {e["name"] for e in entities if e["entity_type"] == "company"}
    for org, ind in KNOWN_ORGS.items():
        key = f"org:{org}"
        if key not in seen and org in text and org not in stock_names:
            seen.add(key)
            entities.append({
                "id": key, "name": org,
                "entity_type": "company", "category": ind,
                "attributes": {"industry": ind, "concepts": ""},
                "source": "known_org"
            })

    # ── 4. IndustryLink: 从 industry_chain 表和文章标头提取 ──
    chains = _load_industry_chains()
    # 只在文本中提到相关行业时才加载其产业链
    mentioned_industries = set()
    for e in entities:
        ind = e.get("attributes", {}).get("industry", "")
        if ind and ind in chains:
            mentioned_industries.add(ind)
    # 也检查文本中是否出现行业名
    for ind in chains:
        if ind in text:
            mentioned_industries.add(ind)
    # 4a. 从 industry_chain 中提取环节名（仅已提及的行业）
    for industry in mentioned_industries:
        chain_data = chains[industry]
        for stage_name, boards in chain_data.items():
            link_name = re.sub(r'^(上游|中游|下游)[-—]?', '', stage_name) or stage_name
            stage = "上游" if "上游" in stage_name else ("中游" if "中游" in stage_name else ("下游" if "下游" in stage_name else "其他"))
            key = f"link:{industry}-{stage_name}"
            if key not in seen:
                seen.add(key)
                entities.append({
                    "id": key, "name": f"{link_name}",
                    "entity_type": "industry_link",
                    "category": f"{industry}-{stage}",
                    "attributes": {"position": stage, "industry": industry, "boards": boards},
                    "source": "chain_def"
                })

    # 4b. 从文章标头提取环节
    for line in text.split('\n'):
        m = re.match(r'#+\s*(?:(\d+)[.、．]\s*)?(.+?)(?:产业链|环节|领域)', line)
        if m:
            name = m.group(2).strip()
            key = f"link:{name}"
            if key not in seen and 2 <= len(name) <= 20:
                seen.add(key)
                # 尝试判断位置
                pos = "上游" if "上游" in line else ("中游" if "中游" in line else ("下游" if "下游" in line else ""))
                entities.append({
                    "id": key, "name": name,
                    "entity_type": "industry_link",
                    "category": f"产业链{pos}",
                    "attributes": {"position": pos, "industry": "", "boards": []},
                    "source": "header"
                })

    # ── 5. Concept: 从概念板块匹配 ──
    for board in board_names:
        key = f"concept:{board}"
        if key not in seen and board in text:
            seen.add(key)
            entities.append({
                "id": key, "name": board,
                "entity_type": "concept",
                "category": "概念板块",
                "attributes": {},
                "source": "board_match"
            })

    # 5b. 兜底: 从 industry_chain 定义中的 boards 字段匹配
    if not any(e["source"] == "board_match" for e in entities):
        for industry, chain_data in chains.items():
            for stage_name, boards in chain_data.items():
                for board in boards:
                    key = f"concept:{board}"
                    if key not in seen and board in text:
                        seen.add(key)
                        entities.append({
                            "id": key, "name": board,
                            "entity_type": "concept",
                            "category": "概念板块",
                            "attributes": {},
                            "source": "chain_board"
                        })

    # 从 stock_info.concepts 字段提取（公司关联的概念）
    company_entities = [e for e in entities if e["entity_type"] == "company"]
    for ce in company_entities:
        concepts_str = ce["attributes"].get("concepts", "")
        if concepts_str and concepts_str not in ["[]", "{}", "", " "]:
            for cpt in re.split(r'[;；,，、\s]+', concepts_str):
                cpt = cpt.strip().strip('[]"\' ')
                if cpt and len(cpt) >= 2 and cpt not in ["[]", "{}", ""]:
                    key = f"concept:{cpt}"
                    if key not in seen:
                        seen.add(key)
                        entities.append({
                            "id": key, "name": cpt,
                            "entity_type": "concept",
                            "category": "概念板块",
                            "attributes": {},
                            "source": "stock_concept"
                        })

    # ── 6. Concept: 从 AI+xxx 模式提取 ──
    for m in re.finditer(r'AI[+＋]([^，、。\s；;)]+)', text):
        name = f"AI+{m.group(1).strip()}"
        key = f"concept:{name}"
        if key not in seen and 3 <= len(name) <= 25:
            seen.add(key)
            entities.append({
                "id": key, "name": name,
                "entity_type": "concept",
                "category": "AI应用",
                "attributes": {},
                "source": "ai_pattern"
            })

    # ── 7. Industry: 从 stock_info.industry 匹配 ──
    # 收集所有出现在文本中的行业名
    all_industries = set()
    for s in stocks:
        if s["industry"] and s["industry"] in text and s["industry"] != "--":
            all_industries.add(s["industry"])
    for ind in sorted(all_industries):
        key = f"industry:{ind}"
        if key not in seen:
            seen.add(key)
            entities.append({
                "id": key, "name": ind,
                "entity_type": "industry",
                "category": "行业分类",
                "attributes": {},
                "source": "industry_field"
            })

    # ── 8. Product: 从文本中提取产品/服务 ──
    # 从标头提取
    for line in text.split('\n'):
        m = re.match(r'[#*]*\s*(\d+)[.、．]\s*(.+?)(?:概念股|龙头|行业)', line)
        if m:
            name = m.group(2).strip()
            key = f"product:{name}"
            if key not in seen and 2 <= len(name) <= 20:
                seen.add(key)
                entities.append({
                    "id": key, "name": name,
                    "entity_type": "product",
                    "category": "产品/服务",
                    "attributes": {"product_type": ""},
                    "source": "header"
                })

    # 关键词匹配
    for kw in PRODUCT_KEYWORDS:
        if kw.lower() in text.lower():
            key = f"product:{kw}"
            if key not in seen:
                seen.add(key)
                entities.append({
                    "id": key, "name": kw,
                    "entity_type": "product",
                    "category": "产品/服务",
                    "attributes": {"product_type": _guess_product_type(kw)},
                    "source": "keyword"
                })

    # 从"概念股"行提取产品/领域名
    for m in re.finditer(r'(?:[：:]\s*)([\u4e00-\u9fa5\w/+]{2,20})(?:概念股|[：:])', text):
        name = m.group(1).strip()
        key = f"product:{name}"
        if key not in seen and 2 <= len(name) <= 15:
            seen.add(key)
            entities.append({
                "id": key, "name": name,
                "entity_type": "product",
                "category": "产品/服务",
                "attributes": {"product_type": ""},
                "source": "stock_list"
            })

    return entities

def _guess_product_type(name: str) -> str:
    """推测产品类型"""
    upstream_indicators = ["材料", "矿", "原料", "芯片", "硅片", "晶圆", "光刻", "EDA", "IP"]
    midstream_indicators = ["设备", "模组", "组件", "器件", "PCB", "电池", "电机", "模组"]
    downstream_indicators = ["整车", "系统", "应用", "软件", "服务", "解决方案"]
    for kw in upstream_indicators:
        if kw in name: return "原材料"
    for kw in midstream_indicators:
        if kw in name: return "中间品"
    for kw in downstream_indicators:
        if kw in name: return "成品"
    return ""

# ─── 关系提取 ────────────────────────────────────────────
def _extract_relations(text: str, entities: list[dict]) -> list[dict]:
    """提取6类关系"""
    relations = []
    seen_rel = set()

    entity_names = {e["name"] for e in entities}
    entity_by_type = {}
    for e in entities:
        entity_by_type.setdefault(e["entity_type"], []).append(e)

    # ── 方法1: 属于行业 ── Company → Industry ──
    companies = entity_by_type.get("company", [])
    industries = {e["name"]: e for e in entities if e["entity_type"] == "industry"}
    for ce in companies:
        ind_name = ce["attributes"].get("industry", "")
        if ind_name and ind_name in industries:
            key = f"{ce['name']}|{ind_name}|属于行业"
            if key not in seen_rel:
                seen_rel.add(key)
                relations.append({
                    "source": ce["name"], "target": ind_name,
                    "relation": "属于行业", "direction": "forward"
                })
        # 如果公司有industry但不在实体列表里，也建一个
        elif ind_name and ind_name not in ["--", ""]:
            key = f"{ce['name']}|{ind_name}|属于行业"
            if key not in seen_rel:
                seen_rel.add(key)
                relations.append({
                    "source": ce["name"], "target": ind_name,
                    "relation": "属于行业", "direction": "forward"
                })

    # ── 方法2: 属于概念 ── Company → Concept ──
    concepts = {e["name"]: e for e in entities if e["entity_type"] == "concept"}
    for ce in companies:
        concepts_str = ce["attributes"].get("concepts", "")
        if concepts_str and concepts_str not in ["[]", "{}", ""]:
            for cpt in re.split(r'[;；,，、\s]+', concepts_str):
                cpt = cpt.strip().strip('[]"\' ')
                if cpt and len(cpt) >= 2 and cpt in concepts:
                    key = f"{ce['name']}|{cpt}|属于概念"
                    if key not in seen_rel:
                        seen_rel.add(key)
                        relations.append({
                            "source": ce["name"], "target": cpt,
                            "relation": "属于概念", "direction": "forward"
                        })

    # ── 方法3: 文本模式匹配 ──
    sentences = [s.strip() for s in re.split(r'[。！？\n；;]+', text) if s.strip()]

    # 模式: A是B / A是B的C / A生产B / A主营B
    patterns = [
        (r'([^，。！？\s]{2,20})(?:是|属于|为)([^，。！？\s]{2,30})', "属于"),
        (r'([^，。！？\s]{2,20})(?:包括|包含|分为|涵盖|有)([^，。！？\s]{2,30})', "包含"),
        (r'([^，。！？\s]{2,20})(?:生产|制造|供应|研发|提供|主营)([^，。！？\s]{2,30})', "主营产品"),
        (r'([^，。！？\s]{2,20})(?:核心|关键|重要|龙头)([^，。！？\s]{2,20})', "属于"),
        (r'([^，。！？\s]{2,20})(?:供应|采购|上游)([^，。！？\s]{2,30})', "上游供应"),
        (r'([^，。！？\s]{2,20})(?:下游|需求)([^，。！？\s]{2,30})', "下游需求"),
    ]
    for pat, rel_type in patterns:
        for m in re.finditer(pat, text):
            try:
                src = re.sub(r'^[#*\-\s、]+', '', m.group(1).strip())
                tgt = re.sub(r'^[#*\-\s、]+', '', m.group(2).strip())
            except IndexError:
                continue
            if len(src) < 2 or len(tgt) < 2:
                continue
            if src in entity_names or tgt in entity_names:
                key = f"{src}|{tgt}|{rel_type}"
                if key not in seen_rel:
                    seen_rel.add(key)
                    relations.append({
                        "source": src, "target": tgt,
                        "relation": rel_type, "direction": "forward"
                    })

    # ── 方法4: 共现关系 (同一句中出现的实体) ──
    for sent in sentences:
        present = list(dict.fromkeys(e["name"] for e in entities if e["name"] in sent))
        if len(present) >= 2:
            positions = [(sent.index(n), n) for n in present]
            positions.sort()
            for i in range(len(positions) - 1):
                src, tgt = positions[i][1], positions[i+1][1]
                if src == tgt:
                    continue
                key = f"{src}|{tgt}|相关"
                if key not in seen_rel:
                    seen_rel.add(key)
                    relations.append({
                        "source": src, "target": tgt,
                        "relation": "相关", "direction": "forward"
                    })

    # ── 方法5: 环节包含 (从标头推断) ──
    current_stage = None
    for line in text.split('\n'):
        line = line.strip()
        m = re.match(r'#+\s*(?:(\d+)[.、．]\s*)?(.*?)(?:上游|中游|下游|产业链)(.*)', line)
        stage_match = re.search(r'(上游|中游|下游)', line)
        if stage_match:
            current_stage = stage_match.group(1)
        if current_stage and not stage_match and line:
            for e in entities:
                if e["name"] in line and len(e["name"]) >= 2:
                    stage_key = f"{current_stage}链|{e['name']}|处于"
                    if stage_key not in seen_rel:
                        seen_rel.add(stage_key)
                        relations.append({
                            "source": e["name"],
                            "target": f"{current_stage}环节",
                            "relation": "处于", "direction": "forward"
                        })

    return relations

# ─── 文章摘要生成（投资者视角）──────────────────────────────
def _generate_summary(content: str, entities: list[dict], relations: list[dict]) -> str:
    """从文章内容、实体和关系中生成投资视角的结构化摘要"""
    parts = []
    from collections import defaultdict

    # 辅助：提取前N个有意义的非标题行
    def _first_n_lines(n=3):
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('*') and len(line) > 15:
                lines.append(line)
                if len(lines) >= n:
                    break
        return lines

    companies = [e for e in entities if e["entity_type"] == "company"]
    products = [e["name"] for e in entities if e["entity_type"] == "product"]
    concepts = [e["name"] for e in entities if e["entity_type"] == "concept"]
    links = [e["name"] for e in entities if e["entity_type"] == "industry_link"]
    headers = [re.sub(r'^#+\s*', '', l).strip() for l in content.split('\n') if re.match(r'^#{1,3}\s+', l)]

    # --- 1. 行业/赛道判断 ---
    industry_set = set()
    for e in entities:
        ind = e.get("attributes", {}).get("industry", "")
        if ind and ind != "--":
            industry_set.add(ind)
    industry_str = "、".join(sorted(industry_set)[:5]) if industry_set else "待识别"
    stage_phrases = [h for h in headers if any(kw in h for kw in ["上游","中游","下游","景气","周期","拐点"])]
    stage_hint = f"（{'; '.join(stage_phrases[:3])}）" if stage_phrases else ""
    parts.append(f"**行业/赛道**: {industry_str} {stage_hint}")

    # --- 2. 核心逻辑（从前3行有意义的正文提取） ---
    first_lines = _first_n_lines(2)
    if first_lines:
        logic = first_lines[0][:120]
        parts.append(f"**核心逻辑**: {logic}")
    elif headers:
        parts.append(f"**核心逻辑**: 围绕「{' | '.join(headers[:3])}」展开")

    # --- 3. 产业链关键环节（按价值量/稀缺性排序：产品 > 环节 > 概念） ---
    chain_items = []
    # 高价值产品优先
    for p in products:
        chain_items.append(f"📦 {p}")
    # 产业链环节
    for l in links[:5]:
        chain_items.append(f"🔗 {l}")
    # 概念
    for c in concepts[:5]:
        chain_items.append(f"🏷️ {c}")
    if chain_items:
        parts.append(f"**关键环节**: {' | '.join(chain_items[:8])}")

    # --- 4. 竞争格局（company按行业分组，标注地位） ---
    if companies:
        by_ind = defaultdict(list)
        for e in entities:
            if e["entity_type"] == "company":
                ind = e.get("attributes", {}).get("industry", e.get("category", ""))
                by_ind[ind].append(e["name"])
        comp_lines = []
        for ind, names in sorted(by_ind.items()):
            if ind and names:
                comp_lines.append(f"{ind}: {'、'.join(names[:4])}")
        if comp_lines:
            parts.append(f"**竞争格局**: {'; '.join(comp_lines[:5])}")

    # --- 5. 核心标的（从属于/主营产品关系定位） ---
    key_rels = [r for r in relations if r["relation"] in ("属于行业", "主营产品", "属于概念")]
    if key_rels:
        # 按source分组
        by_source = defaultdict(list)
        for r in key_rels:
            by_source[r["source"]].append(f"{r['target']}[{r['relation']}]")
        pick_lines = []
        for src, targets in sorted(by_source.items()):
            pick_lines.append(f"{src}: {', '.join(targets[:3])}")
        if pick_lines:
            parts.append(f"**核心标的**: {'; '.join(pick_lines[:6])}")
    elif companies:
        parts.append(f"**核心标的**: {'、'.join([e['name'] for e in companies[:6]])}")

    # --- 6. 风险关注（从内容中识别风险关键词） ---
    risk_kws = ["风险", "不确定性", "竞争加剧", "价格战", "下行", "过剩", "政策", "制裁",
                "波动", "依赖", "瓶颈", "替代", "降价", "亏损", "下滑", "放缓"]
    risks = []
    for line in content.split('\n'):
        for kw in risk_kws:
            if kw in line and len(line) > 10 and line not in risks:
                risks.append(line.strip()[:80])
                break
    if risks:
        parts.append(f"**风险关注**: {'; '.join(risks[:3])}")
    else:
        parts.append("**风险关注**: 文章未明确提及风险，需自行判断")

    # --- 7. 催化剂（从内容中识别驱动因素） ---
    driver_kws = ["量产", "落地", "大单", "招标", "政策支持", "补贴",
                  "突破", "获批", "上线", "合作", "投资", "扩张", "签约"]
    drivers = []
    for line in content.split('\n'):
        for kw in driver_kws:
            if kw in line and len(line) > 10:
                drivers.append(line.strip()[:80])
                break
    if drivers:
        parts.append(f"**催化剂**: {'; '.join(drivers[:3])}")
    elif first_lines:
        parts.append(f"**催化剂**: {first_lines[-1][:80] if len(first_lines)>1 else first_lines[0][:80]}")

    return '\n'.join(parts)


# ─── API 端点 ────────────────────────────────────────────
@router.post("/extract")
def extract_from_article(body: dict):
    content = body.get("content", "")
    url = body.get("url", "")
    if url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = _requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            content = r.text
        except Exception as e:
            raise HTTPException(400, f"获取URL失败: {e}")
    if not content or len(content) < 10:
        raise HTTPException(400, "内容太短")

    entities = _extract_entities(content)
    relations = _extract_relations(content, entities)

    # 去重
    seen_e = set()
    unique_e = []
    for e in entities:
        if e["id"] not in seen_e:
            seen_e.add(e["id"])
            unique_e.append(e)

    seen_r = set()
    unique_r = []
    for r in relations:
        key = f"{r['source']}|{r['target']}|{r['relation']}"
        if key not in seen_r:
            seen_r.add(key)
            unique_r.append(r)

    title = body.get("title", "")
    if not title:
        for line in content.split('\n'):
            line = line.strip()
            if re.match(r'^#{1,3}\s+', line):
                title = re.sub(r'^#+\s+', '', line)
                break
        if not title:
            title = content[:40].strip() + "..."

    summary = _generate_summary(content, unique_e, unique_r)

    return {"success": True, "data": {
        "title": title, "summary": summary,
        "entities": unique_e, "relations": unique_r,
        "entity_count": len(unique_e), "relation_count": len(unique_r),
        "content_preview": content[:500] + ("..." if len(content) > 500 else ""),
    }}


@router.post("/articles")
def save_article(body: dict):
    title = body.get("title", "").strip()
    source = body.get("source", "text")
    content = body.get("content", "")
    summary = body.get("summary", "").strip()
    entities = json.dumps(body.get("entities", []), ensure_ascii=False)
    relations = json.dumps(body.get("relations", []), ensure_ascii=False)
    if not content:
        raise HTTPException(400, "内容不能为空")
    # 如果没有提供摘要，自动生成
    if not summary:
        try:
            summary = _generate_summary(content, json.loads(entities), json.loads(relations))
        except Exception:
            summary = ""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO kg_articles (title, source, content, summary, entities, relations) VALUES (?,?,?,?,?,?)",
              (title, source, content, summary, entities, relations))
    aid = c.lastrowid
    for e in json.loads(entities):
        cat = e.get("category", "")
        etype = e.get("entity_type", "")
        c.execute("""INSERT INTO kg_entity_stats (name, entity_type, category, count)
            VALUES (?,?,?,1) ON CONFLICT(name) DO UPDATE SET
            count=count+1, entity_type=excluded.entity_type, last_seen=datetime('now','localtime')""",
            (e["name"], etype, cat))
    for r in json.loads(relations):
        c.execute("""INSERT INTO kg_relation_stats (source, target, relation, count)
            VALUES (?,?,?,1) ON CONFLICT(source, target, relation) DO UPDATE SET count=count+1""",
            (r["source"], r["target"], r["relation"]))
    conn.commit()
    conn.close()
    return {"success": True, "msg": f"✅ 文章 [{title}] 保存成功", "id": aid}


@router.get("/articles")
def list_articles():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, source, entities, relations, summary, created_at FROM kg_articles ORDER BY created_at DESC")
    articles = []
    for r in c.fetchall():
        try:
            ec = len(json.loads(r[3] or "[]"))
            rc = len(json.loads(r[4] or "[]"))
        except Exception:
            ec = rc = 0
        articles.append({"id": r[0], "title": r[1], "source": r[2],
                         "entity_count": ec, "relation_count": rc,
                         "summary": r[5] or "", "created_at": r[6]})
    conn.close()
    return {"success": True, "data": articles, "total": len(articles)}


@router.get("/articles/{aid}")
def get_article(aid: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, source, content, entities, relations, summary, created_at FROM kg_articles WHERE id=?", (aid,))
    r = c.fetchone()
    conn.close()
    if not r:
        raise HTTPException(404, "文章不存在")
    return {"success": True, "data": {
        "id": r[0], "title": r[1], "source": r[2],
        "content": r[3], "entities": json.loads(r[4] or "[]"),
        "relations": json.loads(r[5] or "[]"), "summary": r[6] or "",
        "created_at": r[7]
    }}


@router.delete("/articles/{aid}")
def delete_article(aid: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM kg_articles WHERE id=?", (aid,))
    conn.commit()
    deleted = c.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(404, "文章不存在")
    return {"success": True, "msg": "🗑️ 已删除"}


@router.put("/articles/{aid}/summary")
def update_summary(aid: int, body: dict):
    """更新文章摘要"""
    summary = body.get("summary", "").strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE kg_articles SET summary=?, updated_at=datetime('now','localtime') WHERE id=?", (summary, aid))
    conn.commit()
    updated = c.rowcount
    conn.close()
    if not updated:
        raise HTTPException(404, "文章不存在")
    return {"success": True, "msg": "✅ 摘要已更新"}


@router.get("/graph/aggregated")
def get_aggregated_graph(min_count: int = 1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, entity_type, category, count FROM kg_entity_stats WHERE count>=?", (min_count,))
    entities = [{"id": r[0], "name": r[0], "entity_type": r[1] or "", "category": r[2] or "", "weight": r[3]} for r in c.fetchall()]
    c.execute("SELECT source, target, relation, count FROM kg_relation_stats WHERE count>=?", (min_count,))
    relations = [{"source": r[0], "target": r[1], "relation": r[2], "weight": r[3]} for r in c.fetchall()]
    conn.close()
    return {"success": True, "data": {
        "entities": entities, "relations": relations,
        "entity_count": len(entities), "relation_count": len(relations)
    }}

@router.get("/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT entity_type, COUNT(*), SUM(count) FROM kg_entity_stats GROUP BY entity_type")
    rows = c.fetchall()
    conn.close()
    return {"success": True, "data": {r[0]: {"entities": r[1], "total_mentions": r[2]} for r in rows}}
