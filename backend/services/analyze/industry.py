"""
行业前瞻分析服务
行业景气周期、产业链供需矛盾、概念板块匹配、量化预测
"""
from __future__ import annotations

import json
import os
import sqlite3
import re
from datetime import date
from typing import Any

import pandas as pd

from backend.services.financial_service import get_concept_board_data
from backend.services.external.csv_client import get_industry_data

DB_PATH = os.path.expanduser("~/Jarvis/ai_trading/stock_archive.db")

# ====== 行业产业链硬编码映射（SQLite兜底失败时使用） ======
INDUSTRY_CHAIN_MAP = {
    "电池": {
        "上游-资源": ["锂矿概念"],
        "中游-材料": ["锂电池概念"],
        "下游-应用": ["新能源车", "储能概念", "充电桩"],
        "相关": ["固态电池", "动力电池回收"],
    },
    "半导体": {
        "上游-设备材料": ["半导体概念", "光刻机(胶)"],
        "中游-设计制造": ["国产芯片", "第三代半导体"],
        "下游-封测应用": ["先进封装", "汽车芯片", "AI芯片"],
        "相关": ["存储芯片", "第四代半导体"],
    },
    "汽车零部件": {
        "上游-原材料": ["汽车热管理", "汽车轻量化"],
        "中游-零部件": ["汽车零部件", "一体化压铸"],
        "下游-整车": ["汽车整车", "新能源汽车"],
        "相关": ["汽车电子", "无人驾驶"],
    },
    "光伏设备": {
        "上游-原材料": ["硅能源", "有机硅"],
        "中游-电池组件": ["光伏概念", "HJT电池", "TOPCon电池"],
        "下游-运营": ["绿色电力"],
        "相关": ["储能概念", "碳中和"],
    },
    "白酒": {
        "上游-粮食": ["农业种植"],
        "中游-生产": ["白酒概念"],
        "下游-渠道": ["新零售", "电子商务"],
        "相关": ["食品饮料", "大消费"],
    },
    "证券": {
        "相关-同行": ["证券概念"],
        "相关-市场": ["参股券商", "互联网金融"],
    },
    "医疗器械": {
        "上游-材料": ["医疗耗材", "生物材料"],
        "中游-设备": ["医疗器械概念", "体外诊断"],
        "下游-服务": ["医疗服务", "互联网医疗"],
        "相关": ["医药电商"],
    },
    "军工电子Ⅱ": {
        "上游-元器件": ["军工", "军民融合", "大飞机"],
        "中游-系统设备": ["军工", "军工信息化", "军工电子"],
        "下游-整机装备": ["航空发动机", "无人机", "商业航天"],
        "相关": ["国产航母", "船舶制造", "卫星导航"],
    },
    "软件开发": {
        "上游-基础设施": ["国产软件", "信创", "操作系统"],
        "相关-应用": ["人工智能", "数字经济", "云计算", "大数据"],
        "下游-行业": ["金融科技", "智慧政务"],
    },
    "电力": {
        "上游-发电": ["绿色电力", "风电", "光伏概念"],
        "中游-传输": ["智能电网", "特高压"],
        "下游-服务": ["储能概念", "电力物联网"],
        "相关": ["碳中和", "充电桩"],
    },
    "化学制品": {
        "上游-原料": ["氟化工", "磷化工", "煤化工"],
        "中游-生产": ["化工", "化工合成材料"],
        "下游-应用": ["可降解塑料", "电子化学品"],
        "相关": ["锂电池概念", "新材料"],
    },
}

# cycle分析结果缓存（按(sector, date)）
_cycle_analysis_cache: dict[tuple, dict] = {}


class IndustryAnalyzer:
    """行业前瞻分析 — 景气周期/产业链供需/量化预测"""

    # ── 产业链配置管理 ──────────────────────────────────

    @staticmethod
    def get_chain_def(industry: str) -> dict | None:
        """从SQLite获取产业链配置，无记录则用INDUSTRY_CHAIN_MAP兜底"""
        if not industry:
            return None
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chain_data FROM industry_chain WHERE industry=?", (industry,))
            row = c.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return INDUSTRY_CHAIN_MAP.get(industry)

    @staticmethod
    def get_all_chain_industries() -> list[dict]:
        """获取所有已配置产业链的行业列表"""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT industry, chain_data, updated_at, notes FROM industry_chain ORDER BY industry")
            rows = c.fetchall()
            conn.close()
            result = []
            for r in rows:
                try:
                    d = json.loads(r[1])
                except Exception:
                    d = {}
                result.append({
                    "industry": r[0],
                    "chains": d,
                    "updated_at": r[2],
                    "notes": r[3] or "",
                })
            return result
        except Exception:
            return []

    @staticmethod
    def save_chain_def(industry: str, chain_data: dict, notes: str = "") -> bool:
        """保存产业链配置到SQLite"""
        try:
            from datetime import datetime
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO industry_chain (industry, chain_data, updated_at, notes)
                VALUES (?, ?, ?, ?)
            """, (industry, json.dumps(chain_data, ensure_ascii=False),
                  datetime.now().isoformat(timespec="seconds"), notes))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    @staticmethod
    def delete_chain_def(industry: str) -> bool:
        """删除产业链配置"""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM industry_chain WHERE industry=?", (industry,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    # ── 行业数据 ────────────────────────────────────────

    @staticmethod
    def get_industry_data(sector: str | None) -> dict | None:
        """行业板块数据（排名/平均涨幅/龙头股）"""
        return get_industry_data(sector)

    # ── 概念板块匹配 ────────────────────────────────────

    @staticmethod
    def _normalize(name: str) -> str:
        """去除标点符号+空格+小写"""
        return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", name).lower()

    @staticmethod
    def lookup_board(board_name: str, board_data: dict) -> dict | None:
        """智能模糊匹配概念板块名称"""
        if not board_name or not board_data:
            return None

        # 1. 精确匹配
        if board_name in board_data:
            info = board_data[board_name]
            return {
                "change_pct": info.get("change_pct", 0),
                "up_count": info.get("up_count", 0),
                "down_count": info.get("down_count", 0),
                "leader": info.get("leader", "--"),
                "leader_chg": info.get("leader_chg"),
            }

        # 2. 归一化匹配
        norm_query = IndustryAnalyzer._normalize(board_name)
        norm_map = {IndustryAnalyzer._normalize(k): k for k in board_data}
        if norm_query in norm_map:
            info = board_data[norm_map[norm_query]]
            return {
                "change_pct": info.get("change_pct", 0),
                "up_count": info.get("up_count", 0),
                "down_count": info.get("down_count", 0),
                "leader": info.get("leader", "--"),
                "leader_chg": info.get("leader_chg"),
            }

        # 3. 模糊匹配（评分：字包含 + 长度接近）
        best_score = 0
        best_match = None
        for key in board_data:
            score = 0
            for ch in board_name:
                if ch in key:
                    score += 1
            # 长度接近加分
            len_diff = abs(len(key) - len(board_name))
            score -= len_diff * 0.5
            if score > best_score:
                best_score = score
                best_match = key

        if best_score >= 5:
            info = board_data[best_match]
            return {
                "change_pct": info.get("change_pct", 0),
                "up_count": info.get("up_count", 0),
                "down_count": info.get("down_count", 0),
                "leader": info.get("leader", "--"),
                "leader_chg": info.get("leader_chg"),
            }
        return None

    @staticmethod
    def compute_board_from_stocks(board_name: str) -> dict | None:
        """从个股行情聚合计算概念板块指标（兜底：CSV关键词匹配 → akshare）"""
        # 方案1: CSV关键词匹配（akshare挂掉时最可靠的方案）
        try:
            from backend.services.external.csv_client import find_latest_csv, _read_csv
            csv_path = find_latest_csv()
            if csv_path:
                df = _read_csv(csv_path)
                if df is not None and not df.empty:
                    raw = board_name
                    stripped = re.sub(r"(概念|板块|行业|产业|相关|应用|服务|材料|设备|制造|运营)$", "", raw).strip()
                    if not stripped:
                        stripped = raw
                    keywords = set()
                    if stripped:
                        keywords.add(stripped)
                    for i in range(0, len(stripped) - 1, 1):
                        bigram = stripped[i:i+2]
                        if len(bigram) >= 2:
                            keywords.add(bigram)
                    mask = pd.Series([False] * len(df))
                    for kw in keywords:
                        if len(kw) < 2:
                            continue
                        mask |= df["所属行业"].astype(str).str.contains(kw, na=False)
                        mask |= df["名称"].astype(str).str.contains(kw, na=False)
                    matched = df[mask].copy()
                    valid = matched[matched["涨幅"].notna()]
                    if not valid.empty:
                        avg = round(float(valid["涨幅"].mean()), 2)
                        up = int((valid["涨幅"] > 0).sum())
                        down = int((valid["涨幅"] < 0).sum())
                        sorted_s = valid.nlargest(5, "涨幅")
                        return {
                            "change_pct": avg, "up_count": up, "down_count": down,
                            "leader": sorted_s.iloc[0]["名称"] if not sorted_s.empty else "--",
                            "leader_chg": float(sorted_s.iloc[0]["涨幅"]) if not sorted_s.empty else None,
                            "_fallback": True, "_fallback_source": "csv_keyword",
                            "_matched_count": len(valid),
                        }
        except Exception:
            pass

        # 方案2: akshare（兜底兜底）
        from backend.services.external.csv_client import get_board_stocks_detail
        try:
            stocks = get_board_stocks_detail(board_name)
            if stocks:
                changes = [s.get("change_pct") for s in stocks if s.get("change_pct") is not None]
                if changes:
                    avg = round(sum(changes) / len(changes), 2)
                    up = sum(1 for c in changes if c > 0)
                    down = sum(1 for c in changes if c < 0)
                    leaders = sorted(stocks, key=lambda s: float(s.get("change_pct", 0) or 0), reverse=True)
                    return {
                        "change_pct": avg, "up_count": up, "down_count": down,
                        "leader": leaders[0].get("name", "--") if leaders else "--",
                        "leader_chg": leaders[0].get("change_pct") if leaders else None,
                        "_fallback": True,
                    }
        except Exception:
            pass
        return None

    # ── 行业景气周期 + 供需矛盾 + 量化预测 ──────────────

    @classmethod
    def analyze_cycle(cls, sector: str, industry_data: dict | None) -> dict | None:
        """行业景气周期 + 供需矛盾分析 + 量化预测"""
        if not industry_data:
            return None
        today = str(date.today())
        cache_key = (sector, today)
        cached = _cycle_analysis_cache.get(cache_key)
        if cached is not None:
            return cached

        avg_chg = industry_data.get("avg_change", 0) or 0
        up_ratio = industry_data.get("up_ratio", 0) or 0
        down_ratio = industry_data.get("down_ratio") or 0
        rank = industry_data.get("rank")
        total = industry_data.get("total_sectors", 100) or 100
        stock_count = industry_data.get("stock_count", 0) or 0
        divergence = industry_data.get("divergence", 0) or 0
        top_avg_chg = industry_data.get("top_avg_change", 0) or 0
        bottom_avg_chg = industry_data.get("bottom_avg_change", 0) or 0
        bottom_stocks = industry_data.get("bottom_stocks", []) or []

        # 1. 行业景气周期判定（含退潮/分化因子）
        rank_pct = round(rank / total * 100, 1) if rank else 50

        # 分化惩罚：龙头涨但多数跌 → 板块内部严重分化，实际强度低于表面涨幅
        divergence_penalty = 0
        if divergence > 15:
            divergence_penalty = 20  # 分化极大，龙头失真
            divergence_risk = "⚠️ 严重分化"
            divergence_desc = f"龙头涨幅{top_avg_chg:.1f}% vs 最差{bottom_avg_chg:.1f}%，板块内部极度割裂，幸存者偏差严重"
        elif divergence > 8:
            divergence_penalty = 10
            divergence_risk = "⚡ 明显分化"
            divergence_desc = f"龙头涨{top_avg_chg:.1f}% vs 弱势跌{bottom_avg_chg:.1f}%，仅少数股撑门面，多数在跌"
        elif divergence > 4:
            divergence_penalty = 5
            divergence_risk = "📊 轻度分化"
            divergence_desc = f"个股间有分化但不严重，板块整体方向可信"
        else:
            divergence_risk = "✅ 普涨/普跌"
            divergence_desc = f"个股步调一致，板块整体方向明确，无幸存者偏差"

        # 退潮检查：下跌占比高或最差股跌幅大
        if down_ratio > 60:
            receding_flag = "⚠️ 普跌格局"
            receding_desc = f"{down_ratio:.0f}%的个股下跌，赚钱效应差"
        elif down_ratio > 40:
            receding_flag = "📉 涨少跌多"
            receding_desc = f"跌多涨少（下跌占比{down_ratio:.0f}%），仅少数上涨"
        else:
            receding_flag = "✅ 涨多跌少"
            receding_desc = f"多数个股上涨（下跌仅{down_ratio:.0f}%），赚钱效应良好"

        # 综合判断：在原有判定上增加分化修正
        if avg_chg > 3 and up_ratio > 70 and rank_pct < 20:
            cycle_stage = "过热期 🔥"
            cycle_score = 90
            cycle_desc = "板块涨幅大、上涨占比高、排名靠前，市场情绪亢奋，需警惕过热后回调风险"
            cycle_risk = "追高风险大，不建议新建仓位"
        elif avg_chg > 1 and up_ratio > 60 and rank_pct < 35:
            cycle_stage = "扩张期 🚀"
            cycle_score = 75
            cycle_desc = "板块整体强势，上涨家数占优，处于主升浪阶段，资金持续流入"
            cycle_risk = "趋势延续概率大，但需关注量能变化"
        elif avg_chg > 0 and up_ratio > 45:
            cycle_stage = "复苏期 🌱"
            cycle_score = 55
            cycle_desc = "板块温和上涨，涨跌接近平衡，但排名在改善，可能处于底部区域"
            cycle_risk = "方向未明，适合逐步建仓，不宜重仓"
        elif avg_chg > -2 and up_ratio > 30:
            cycle_stage = "调整期 📉"
            cycle_score = 35
            cycle_desc = "板块小幅下跌，市场情绪偏弱，可能是上升趋势中的正常调整"
            cycle_risk = "关注是否企稳，避免左侧抄底"
        else:
            cycle_stage = "衰退期 ❄️"
            cycle_score = 20
            cycle_desc = "板块明显下跌，多数个股走弱，资金流出明显，处于下行趋势"
            cycle_risk = "不宜参与，等待反转信号"

        # 分化修正：如果板块表象较好但内部分化严重，下调评分
        effective_score = max(cycle_score - divergence_penalty, 10)
        if effective_score < cycle_score:
            cycle_score = effective_score
            # 在desc末尾追加幸存者偏差提示
            cycle_desc += f" ⚠️ 实际强度受分化拖累（{divergence_risk}，{divergence_desc}）"
            cycle_risk += f" | 注意{receding_flag}，{receding_desc}"

        # 2. 产业链供需矛盾分析
        chain_map = cls.get_chain_def(sector) or {}
        board_data = get_concept_board_data()
        chain_analysis = []
        chain_scores = []

        for stage_name, boards in chain_map.items():
            stage_items = []
            total_chg = 0
            valid_boards = 0

            for board in boards:
                info = cls.lookup_board(board, board_data)
                if not info:
                    info = cls.compute_board_from_stocks(board)
                if info:
                    up_count = info.get("up_count", 0)
                    down_count = info.get("down_count", 0)
                    up_ratio_b = up_count / max(up_count + down_count, 1) * 100
                    stage_items.append({
                        "name": board,
                        "change_pct": info["change_pct"],
                        "up_ratio": round(up_ratio_b, 1),
                        "leader": info.get("leader", "--"),
                        "leader_chg": info.get("leader_chg"),
                        "_fallback": info.get("_fallback", False),
                    })
                    total_chg += info["change_pct"]
                    valid_boards += 1
                else:
                    stage_items.append({
                        "name": board,
                        "change_pct": None, "up_ratio": None,
                        "leader": "--", "leader_chg": None,
                    })

            avg_stage_chg = round(total_chg / valid_boards, 2) if valid_boards > 0 else None

            # 判定环节供需状态
            if avg_stage_chg is not None and avg_stage_chg > 3 and any(
                i.get("up_ratio", 0) and i["up_ratio"] > 75 for i in stage_items if i["up_ratio"]
            ):
                status, status_score = "供不应求 🏭", 85
                status_desc = f"资金集中涌入，{valid_boards}个概念板块普涨，短期需求旺盛"
                opp_risk = "⚠️ 过热风险：涨幅过大可能短期回调，不宜追高"
            elif avg_stage_chg is not None and avg_stage_chg > 1:
                status, status_score = "需求旺盛 📈", 70
                status_desc = "环节整体上涨，资金流入积极，供需格局向好"
                opp_risk = "✅ 机会：环节景气度高，关注领先股回调后机会"
            elif avg_stage_chg is not None and avg_stage_chg > -1:
                status, status_score = "供需平衡 =", 50
                status_desc = "环节表现平稳，无明显供需失衡"
                opp_risk = "➡️ 中性：此环节暂不是主要矛盾，等待催化剂"
            elif avg_stage_chg is not None and avg_stage_chg > -3:
                status, status_score = "供给偏松 📉", 30
                status_desc = "环节小幅下跌，供给略大于需求，短期承压"
                opp_risk = "🔍 关注：如果是上游环节走弱可能传导至下游"
            else:
                status, status_score = "供过于求 📦", 15
                status_desc = "环节明显下跌，供给过剩或需求萎缩，资金流出"
                opp_risk = "🚫 风险：该环节产能过剩或需求不足，回避为主"

            chain_scores.append(status_score)
            chain_analysis.append({
                "stage": stage_name,
                "avg_change": avg_stage_chg,
                "status": status,
                "status_score": status_score,
                "desc": status_desc,
                "opp_risk": opp_risk,
                "boards": stage_items,
            })

        # 汇总供需矛盾
        if chain_analysis:
            supply_score = round(sum(c["status_score"] for c in chain_analysis) / len(chain_analysis), 1)
            tightest = max(chain_analysis, key=lambda c: c["status_score"])
            loosest = min(chain_analysis, key=lambda c: c["status_score"])
            bottleneck = f"卡脖子环节在「{tightest['stage']}」（{tightest['status']}），"
            bottleneck += (
                f"最薄弱环节在「{loosest['stage']}」（评分{loosest['status_score']}）"
                if loosest['stage'] != tightest['stage']
                else "整条链同向，需要重点关注"
            )
            supply_demand = f"产业链评分{supply_score}分"
            supply_desc = bottleneck
            stages_status = []
            for c in chain_analysis:
                stages_status.append(c['status'])
            supply_outlook = " → ".join(
                [f"{chain_analysis[i]['stage']}→{chain_analysis[i]['status']}" for i in range(min(3, len(chain_analysis)))]
            )
        else:
            supply_score = 50
            supply_demand = "无产业链数据"
            supply_desc = "该行业暂未建立产业链映射"
            supply_outlook = ""

        # 3. 量化预测
        rank_score = max(0, 100 - rank_pct * 1.5) if rank else 50
        outlook_score = round(cycle_score * 0.5 + supply_score * 0.3 + rank_score * 0.2, 1)

        if outlook_score >= 75:
            outlook_label, outlook_dir = "偏乐观 ✅", "上涨 ↗️"
        elif outlook_score >= 55:
            outlook_label, outlook_dir = "中性偏多 📈", "震荡偏强 ↗️"
        elif outlook_score >= 35:
            outlook_label, outlook_dir = "中性偏弱 📉", "震荡偏弱 ↘️"
        else:
            outlook_label, outlook_dir = "偏悲观 ❌", "下跌 ↘️"

        # 近期走势判断（加入退潮股信息）
        if bottom_stocks:
            worst_stocks_str = ", ".join(
                [f"{s.get('name','?')}({s.get('change_pct',0):+.1f}%)" for s in bottom_stocks[:3]]
            )
            receding_stocks_info = f"退潮代表：{worst_stocks_str}"
        else:
            receding_stocks_info = ""

        if avg_chg > 2 and up_ratio > 65:
            short_term = f"近期走势强劲（涨幅{avg_chg:.1f}% + 上涨占比{up_ratio:.0f}%），短期惯性上冲概率大，但需注意{max(1, round(avg_chg - 1, 1))}%左右的获利盘回吐压力"
        elif avg_chg > 0 and up_ratio > 50:
            short_term = f"稳中有升（涨幅{avg_chg:.1f}%，上涨占比{up_ratio:.0f}%），短期有望延续温和上涨趋势"
        elif avg_chg > -1:
            short_term = f"窄幅整理（涨幅{avg_chg:.1f}%），多空力量均衡，短期方向待选择，关注成交量变化"
        else:
            short_term = f"走势偏弱（涨幅{avg_chg:.1f}%），短期承压，建议观望等待企稳信号"

        if receding_stocks_info:
            short_term += f" | {receding_stocks_info}"

        result = {
            # 景气周期
            "cycle_score": cycle_score,
            "cycle_stage": cycle_stage,
            "cycle_desc": cycle_desc,
            "cycle_risk": cycle_risk,
            # 分歧/退潮研判
            "divergence_score": divergence,
            "divergence_risk": divergence_risk,
            "divergence_desc": divergence_desc,
            "receding_flag": receding_flag,
            "receding_desc": receding_desc,
            "receding_stocks": bottom_stocks[:3],  # 退潮代表股（前3只最差）
            "up_ratio": round(up_ratio, 1),
            "down_ratio": round(down_ratio, 1),
            # 供需矛盾
            "supply_score": supply_score,
            "supply_demand": supply_demand,
            "supply_desc": supply_desc,
            "supply_outlook": supply_outlook,
            "chain_analysis": chain_analysis,
            # 量化预测
            "outlook_score": outlook_score,
            "outlook_label": outlook_label,
            "outlook_dir": outlook_dir,
            "short_term": short_term,
        }

        _cycle_analysis_cache[cache_key] = result
        return result
