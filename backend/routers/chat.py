"""
股票AI聊天 API — 嵌入在个股分析页面的对话助手
"""
from fastapi import APIRouter
from pydantic import BaseModel
from backend.routers.analysis import analyze_stock as _do_analysis
from backend.routers.fundamental import fundamental_analysis as _do_fundamental
from openai import OpenAI
import json
import yaml
from pathlib import Path
from backend.stock_db import save_chat_message, get_chat_history, save_ai_analysis, get_ai_analysis

router = APIRouter()

# 从 Hermes 配置读取 API Key
def _get_deepseek_client():
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        # 优先 custom providers
        providers = cfg.get("custom_providers", [])
        for p in providers:
            if p.get("name") == "deepseek-v4-flash":
                return OpenAI(api_key=p["api_key"], base_url=p["base_url"])
        # fallback: 顶层配置
        return OpenAI(
            api_key=cfg.get("model", {}).get("api_key", ""),
            base_url=cfg.get("model", {}).get("base_url", "https://api.deepseek.com"),
        )
    except Exception:
        return OpenAI(api_key="", base_url="https://api.deepseek.com")

SYSTEM_PROMPT = """你是一位专业的A股投资分析助手，帮助用户分析股票。

回答原则：
1. 基于提供的实时数据回答，数据准确才能给建议
2. 不提供具体买卖建议，只做客观分析
3. 从技术面、基本面、行业面多个角度分析
4. 指出风险和机会，保持中立
5. 回答简洁清晰，用中文
6. 如果数据不足，明确告知用户

你会收到当前股票的技术面数据、基本面数据和行业数据。
"""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": "..."}]


@router.post("/{code}")
def chat_with_stock(code: str, req: ChatRequest):
    """与AI助手对话，分析指定股票"""

    # 获取股票数据作为上下文
    tech_data = _do_analysis(code)
    fund_data = {}
    try:
        fund_data = _do_fundamental(code)
    except Exception:
        pass

    t = tech_data.get("technical") or {}
    rc = tech_data.get("risk_check") or {}
    fin = fund_data.get("financial_summary") or {}
    records = fin.get("records") or []
    ind = fund_data.get("industry_outlook") or {}
    name = tech_data.get("name", "") or fund_data.get("name", "")

    # 构建上下文
    ctx_lines = [f"股票: {name} ({code})"]
    ctx_lines.append("")

    # 技术面
    ctx_lines.append("【技术面数据】")
    ctx_lines.append(f"  现价: {t.get('current_price', '--')}")
    ctx_lines.append(f"  涨跌幅: {t.get('change_pct', '--')}%")
    ctx_lines.append(f"  MA5={t.get('ma5', '--')} MA10={t.get('ma10', '--')} MA20={t.get('ma20', '--')} MA60={t.get('ma60', '--')} MA200={t.get('ma200', '--')}")
    ctx_lines.append(f"  RSI(14): {t.get('rsi_14', '--')}")
    ctx_lines.append(f"  均线多头: {'是' if t.get('bullish_alignment') else '否'}")
    ctx_lines.append(f"  MACD: DIF={t.get('macd', {}).get('dif', '--')} DEA={t.get('macd', {}).get('dea', '--')} HIST={t.get('macd', {}).get('hist', '--')}")
    ctx_lines.append("")

    # 风控
    ctx_lines.append("【风控检查】")
    ctx_lines.append(f"  结果: {'✅ 通过' if rc.get('passed') else '❌ 禁止买入'}")
    for check in rc.get("checks", []):
        ctx_lines.append(f"  - {check.get('rule', '')}: {check.get('detail', '')} [{check.get('status', '')}]")
    ctx_lines.append("")

    # 基本面
    if records:
        last = records[-1]
        ctx_lines.append("【最新财务数据】")
        ctx_lines.append(f"  报告期: {last.get('报告期', '--')}")
        ctx_lines.append(f"  营收: {last.get('营业总收入', '--')} (同比{last.get('营业总收入同比增长率', '--')})")
        ctx_lines.append(f"  净利: {last.get('净利润', '--')} (同比{last.get('净利润同比增长率', '--')})")
        ctx_lines.append(f"  毛利率: {last.get('销售毛利率', '--')}")
        ctx_lines.append(f"  ROE: {last.get('净资产收益率', '--')}")
        ctx_lines.append(f"  EPS: {last.get('基本每股收益', '--')}")
        ctx_lines.append("")

    # 行业
    if ind:
        ctx_lines.append(f"【行业数据】")
        ctx_lines.append(f"  板块: {fund_data.get('sector', '--')}")
        ctx_lines.append(f"  板块排名: #{ind.get('rank', '--')}/{ind.get('total_sectors', '--')}")
        ctx_lines.append(f"  板块平均涨幅: {ind.get('avg_change', '--')}%")
        top = ind.get("top_stocks", [])
        if top:
            ctx_lines.append(f"  龙头股: {' '.join([s.get('name', '') for s in top[:3]])}")
        ctx_lines.append("")

    ctx_lines.append("请在回答中引用上面的数据，帮助用户理解这只股票当前的情况。")

    context = "\n".join(ctx_lines)

    # 构建消息
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"这是 {name}({code}) 的当前数据分析：\n\n{context}\n\n---\n用户问题：{req.message}"},
    ]

    # 如果有历史对话，插入前面（最多保留最近3轮）
    if req.history:
        history_msgs = []
        for h in req.history[-6:]:  # 最近3轮（6条消息）
            role = "user" if h.get("role") == "user" else "assistant"
            history_msgs.append({"role": role, "content": h.get("content", "")})
        # 把历史插在 system 和 当前问题之间
        messages = [messages[0]] + history_msgs + [messages[1]]

    try:
        # 先保存用户消息
        save_chat_message(code, "user", req.message, name)

        ai_client = _get_deepseek_client()
        resp = ai_client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            max_tokens=2048,
            temperature=0.7,
        )
        answer = resp.choices[0].message.content
        # 保存 AI 回复
        save_chat_message(code, "assistant", answer, name)
        return {"code": code, "name": name, "reply": answer}
    except Exception as e:
        return {"code": code, "name": name, "reply": f"抱歉，AI分析暂时不可用。错误：{str(e)}", "error": True}


@router.get("/{code}/history")
def get_stock_chat_history(code: str, limit: int = 50):
    """获取某只股票的聊天记录"""
    records = get_chat_history(code, limit)
    return {"code": code, "records": records, "count": len(records)}


@router.delete("/{code}/history")
def clear_stock_chat_history(code: str):
    """清空某只股票的聊天记录"""
    from backend.stock_db import get_db
    conn = get_db()
    conn.execute("DELETE FROM chat_history WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"已清空 {code} 的聊天记录"}


SUMMARY_SYSTEM_PROMPT = """你是一位专业的A股投研分析师。请根据以下用户与AI的对话记录，结合该股票的实时数据，整理一份简洁的「AI分析要点」。

要求：
1. 提取对话中所有有价值的分析结论
2. **结合提供的实时数据**，补充对话中未提及但重要的信息，按以下分类整理：
   - 「技术面」：均线排列、RSI、MACD、量价关系
   - 「基本面」：最新财报营收/净利、毛利率、ROE、同比变化
   - 「风险提示」：风控检查结果、超买/超卖、估值风险
   - 「机会点」：均线突破、板块强势、回调企稳信号
3. 每条要点用一句话概括，附上关键数据
4. 忽略闲聊和重复内容
5. 格式：用 Markdown 要点列表，保持专业简洁"""


@router.post("/{code}/summarize")
def summarize_chat_to_analysis(code: str):
    """将聊天记录整理成AI分析要点"""
    from backend.routers.analysis import analyze_stock as _do_analysis
    from backend.routers.fundamental import fundamental_analysis as _do_fundamental

    # 获取技术面 + 基本面数据
    tech_data = _do_analysis(code)
    fund_data = {}
    try:
        fund_data = _do_fundamental(code)
    except Exception:
        pass

    t = tech_data.get("technical") or {}
    rc = tech_data.get("risk_check") or {}
    fin = fund_data.get("financial_summary") or {}
    records = fin.get("records") or []
    ind = fund_data.get("industry_outlook") or {}
    name = tech_data.get("name", "") or fund_data.get("name", "")

    # 获取聊天记录
    chats = get_chat_history(code, 50)

    # 组装数据上下文
    ctx_parts = [f"股票: {name} ({code})\n"]

    ctx_parts.append("【技术面数据】")
    ctx_parts.append(f"  现价: {t.get('current_price', '--')}")
    ctx_parts.append(f"  涨跌幅: {t.get('change_pct', '--')}%")
    ctx_parts.append(f"  MA5={t.get('ma5','--')} MA10={t.get('ma10','--')} MA20={t.get('ma20','--')} MA60={t.get('ma60','--')} MA200={t.get('ma200','--')}")
    ctx_parts.append(f"  RSI(14): {t.get('rsi_14','--')}  均线多头: {'是' if t.get('bullish_alignment') else '否'}")
    ctx_parts.append(f"  MACD: DIF={t.get('macd',{}).get('dif','--')} DEA={t.get('macd',{}).get('dea','--')} HIST={t.get('macd',{}).get('hist','--')}")
    ctx_parts.append("")

    ctx_parts.append("【风控检查】")
    ctx_parts.append(f"  结果: {'✅ 通过' if rc.get('passed') else '❌ 禁止买入'}")
    for check in rc.get("checks", []):
        ctx_parts.append(f"  - {check.get('rule','')}: {check.get('detail','')} [{check.get('status','')}]")
    ctx_parts.append("")

    if records:
        last = records[-1]
        ctx_parts.append("【最新财务数据】")
        ctx_parts.append(f"  报告期: {last.get('报告期', '--')}")
        ctx_parts.append(f"  营收: {last.get('营业总收入', '--')} (同比{last.get('营业总收入同比增长率', '--')})")
        ctx_parts.append(f"  净利: {last.get('净利润', '--')} (同比{last.get('净利润同比增长率', '--')})")
        ctx_parts.append(f"  毛利率: {last.get('销售毛利率', '--')}  净利率: {last.get('销售净利率', '--')}")
        ctx_parts.append(f"  ROE: {last.get('净资产收益率', '--')}  EPS: {last.get('基本每股收益', '--')}  BPS: {last.get('每股净资产', '--')}")
        ctx_parts.append(f"  负债率: {last.get('资产负债率', '--')}  流动比: {last.get('流动比率', '--')}")
        ctx_parts.append("")

    if ind:
        ctx_parts.append("【行业数据】")
        ctx_parts.append(f"  板块: {fund_data.get('sector','--')}")
        ctx_parts.append(f"  板块排名: #{ind.get('rank','--')}/{ind.get('total_sectors','--')}")
        ctx_parts.append(f"  板块平均涨幅: {ind.get('avg_change','--')}%")
        top = ind.get("top_stocks", [])
        if top:
            ctx_parts.append(f"  龙头股: {' '.join([s.get('name','') for s in top[:3]])}")

    data_context = "\n".join(ctx_parts)

    # 组装对话文本
    if chats:
        dialog_parts = ["\n\n【用户与AI对话记录】"]
        for c in chats:
            role = "用户" if c["role"] == "user" else "AI助手"
            dialog_parts.append(f"[{role}] {c['content']}")
        dialog_text = "\n".join(dialog_parts)
    else:
        dialog_text = "\n\n（暂无对话记录，请仅基于实时数据进行分析）"

    full_prompt = f"这是 {name}({code}) 的实时数据：\n\n{data_context}{dialog_text}\n\n请结合以上实时数据和对话记录，整理一份AI分析要点。"

    # 调用AI整理
    try:
        ai_client = _get_deepseek_client()
        resp = ai_client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            max_tokens=3072,
            temperature=0.5,
        )
        summary = resp.choices[0].message.content
    except Exception as e:
        summary = f"AI分析生成失败：{str(e)}"

    # 保存到数据库
    save_ai_analysis(code, name, summary, len(chats))

    return {"code": code, "name": name, "summary": summary, "chat_count": len(chats)}


@router.get("/{code}/analyses")
def get_stock_ai_analyses(code: str, limit: int = 5):
    """获取某只股票的AI分析记录"""
    records = get_ai_analysis(code, limit)
    return {"code": code, "records": records, "count": len(records)}


@router.delete("/{code}/analyses")
def clear_stock_ai_analyses(code: str):
    """清空某只股票的AI分析"""
    from backend.stock_db import get_db
    conn = get_db()
    conn.execute("DELETE FROM ai_analysis WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"已清空 {code} 的AI分析"}
