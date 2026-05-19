"""
思维模型库 + 每日训练 + 行业涨跌分化追踪
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import date, timedelta
import json
import sqlite3
import numpy as np
import pandas as pd

from backend.services.db_client import get_db, DB_PATH
from backend.config import MARKET_DATA_DIR
from backend.routers.market import _load_csv
from openai import OpenAI
import yaml
from pathlib import Path

router = APIRouter()

# ============================================================
# 1. 思维模型库
# ============================================================

# ---- 初始化种子数据 ----
SEED_MODELS = [
    # ========== 投资决策 ==========
    {
        "name": "安全边际",
        "icon": "🛡️",
        "category": "投资决策",
        "description": "以低于内在价值的价格买入，为判断错误留出缓冲空间。格雷厄姆称为「投资的核心」",
        "application": "买入决策：只有当价格低于合理估值下限时才出手，确保即使判断部分错误也不会亏钱",
        "scenario": "当PE/PB处于历史低位、市场恐慌时；或当你发现一个优质公司因短期利空被错杀时",
        "example": "某公司内在价值100元，你等到跌到70元才买入。即使估值偏差30%，你依然不亏本金",
        "detail": "## 核心理念\n\n安全边际是价值投资的基石。它不是追求「买在最低点」，而是买在「即便错了也不会亏」的位置。\n\n## 两层含义\n1. **估值保护**：买入价 < 合理价值 × (1 - 误差率)\n2. **容错空间**：为不可预见的风险留出缓冲\n\n## 实战应用\n- 关注PB < 1.5 + PE处于历史20%分位以下\n- 现金充裕 + 负债率低 + 经营稳定 → 安全边际更厚\n- 当安全边际变薄（如涨幅过高），逐步减仓\n\n## 与A股的结合\n- **牛市陷阱**：安全边际思维在牛市中常被嘲笑，但它是防止牛市综合征的关键\n- **结构性机会**：A股板块轮动剧烈，安全边际帮你区分「贵但还能涨」vs「便宜但该跌了」",
        "tags": "[\"core\",\"value\",\"buy\"]"
    },
    {
        "name": "能力圈",
        "icon": "🎯",
        "category": "投资决策",
        "description": "清楚知道自己懂什么、不懂什么，只在自己能理解的领域做决策。巴菲特：「重要的是知道你的能力圈边界」",
        "application": "选股前先自问：我是否真正理解这家公司的商业模式、竞争壁垒和行业前景？",
        "scenario": "面对热门概念股、技术复杂的企业、或你不熟悉的行业时",
        "example": "彼得·林奇：只买自己日常能接触到产品/服务的公司。如果你喝了它的酸奶觉得好，比你研究3天财报更有价值",
        "detail": "## 核心理念\n\n能力圈不是固定不变的，可以逐步扩展，但关键是知道边界在哪。\n\n## 如何划定能力圈\n1. **两句话测试**：能否用两句话说清这家公司怎么赚钱？\n2. **竞争对手测试**：能说出它的前3个竞争对手及其差异吗？\n3. **5年测试**：能预见这家公司5年后大概是什么样吗？\n\n## 常见陷阱\n- 看了几篇研报就以为懂了（知道 ≠ 理解）\n- 涨了就觉得在能力圈内（幸存者偏差）\n- 「这次不一样」的心态\n\n## A股实战\n- 科技股：你真的懂芯片设计/封装/制造的差异吗？\n- 医药股：仿制药和创新药的估值逻辑完全不同\n- 周期股：你需要理解产能周期，不只是看PE低",
        "tags": "[\"core\",\"value\",\"selection\"]"
    },
    {
        "name": "复利效应",
        "icon": "📈",
        "category": "投资决策",
        "description": "持续的小收益通过时间积累产生指数级增长。爱因斯坦称之为「世界第八大奇迹」",
        "application": "关注长期持有优质资产、减少交易摩擦、让收益再投资",
        "scenario": "当你考虑频繁交易 vs 长期持有、选择成长股时",
        "example": "年化15%的收益，持有20年即增长16倍。频繁交易每年损耗3%收益，20年只剩约一半",
        "detail": "## 核心理念\n\n复利的关键不是单期收益率有多高，而是不间断、不亏大钱。\n\n## 三大要素\n1. **本金**：投资的基础\n2. **收益率**：长期可持续的回报率\n3. **时间**：最强的变量——越早开始，复利效果越显著\n\n## 复利的敌人\n- **回撤**：跌50%需要涨100%才能回本\n- **交易成本**：每次买卖都在消耗复利\n- **频繁换仓**：打断复利连续性\n\n## A股应用\n- 长期持有优质消费/医药龙头的复利效果显著\n- 但A股波动大，要学会在泡沫时减仓、低谷时加仓\n- 红利再投资是A股中最容易被忽视的复利来源",
        "tags": "[\"core\",\"growth\",\"long-term\"]"
    },
    {
        "name": "机会成本",
        "icon": "📐",
        "category": "投资决策",
        "description": "每选择A就意味着放弃B、C、D的最高收益。真正的成本不是你付了多少钱，而是你放弃了什么",
        "application": "持仓对比：永远问自己「如果不持有这只股票，我会买什么？那个选择比现在更好吗？」",
        "scenario": "评估是否卖出持仓、选择多个标的时",
        "example": "持有某股年化8%，但发现同行业的龙头股预期收益15%——持有它的机会成本是每年少赚7%",
        "detail": "## 核心理念\n\n机会成本是经济学第一课，但投资中最容易被忽略。持仓不动不是因为「它没问题」，而是因为没找到更好的替代。\n\n## 实战清单\n1. 这个仓位的机会成本是多少？（对比现金/ETF/其他个股）\n2. 如果现在是空仓，我会买入这只股票吗？\n3. 我持有它是因为看好，还是因为懒得换？\n\n## A股应用\n- 板块轮动频繁，机会成本意识帮你捕捉结构性机会\n- 弱势股补仓的机会成本可能是错失了龙头股加仓时机\n- 现金也是一种选择——在市场高估时持有现金没有机会成本",
        "tags": "[\"portfolio\",\"sell\",\"compare\"]"
    },
    {
        "name": "第二层思维",
        "icon": "🧠",
        "category": "投资决策",
        "description": "第一层思维看表象（「这家公司好，买它」）；第二层思维看预期差（「大家都觉得它好，所以已经price in了」）",
        "application": "买入前必问：市场当前的定价在反映什么预期？我的观点与市场预期有何不同？",
        "scenario": "当热门股票大涨、市场一致性预期极强时",
        "example": "第一层：「芯片短缺利好，买芯片股」；第二层：「市场已经给芯片股极高估值，如果短缺缓解，这些公司的盈利能力还能支撑当前估值吗？」",
        "detail": "## 核心理念\n\n投资是预期差的游戏。市场已经定价的信息不是机会；只有你发现了市场尚未反映的信息才是。\n\n## 三层递进\n1. 市场在price in什么？（共识）\n2. 我有什么不同看法？（差异）\n3. 我的差异是对的吗？（验证）\n\n## 常见错误\n- 把「看好」等同于「会涨」\n- 忽略市场已经反映的正面信息\n- 过度自信自己的差异化判断\n\n## A股实战\n- 当散户一致性看多时（如雪球热帖），恰恰要警惕\n- 当机构大幅调仓而你理解了调仓逻辑时，可能发现第二层机会\n- 利空出尽=利好，利好落地=利空，也是第二层思维的体现",
        "tags": "[\"psychology\",\"contrarian\",\"entry\"]"
    },

    # ========== 系统思维 ==========
    {
        "name": "二阶效应",
        "icon": "🔄",
        "category": "系统思维",
        "description": "一个行为不仅产生直接结果（一阶），还会通过系统反馈产生间接结果（二阶）。「事情比看起来更复杂」",
        "application": "在板块轮动中思考资金流向的二阶效应：资金从哪流出？下一站可能去哪？",
        "scenario": "板块暴涨/暴跌时、政策出台时、市场风格切换时",
        "example": "降息（一阶）→ 地产股涨（二阶）→ 地产带动的产业链（家电/建材）受益（三阶）",
        "detail": "## 核心理念\n\n每个行为都会引发连锁反应，只看一阶效应会忽略真正的风险或机会。\n\n## 投资中的二阶效应\n1. **政策**：不是为了刺激，而是为了「让大家觉得会被刺激」\n2. **资金流向**：跟随资金买入（一阶）→ 更多人追随（二阶）→ 获利了结引发踩踏（三阶）\n3. **板块轮动**：A板块涨了，资金需要卖B来买A，所以B会跌\n\n## A股实战\n- 北向资金净流入≠立即买入，要考虑内资会如何应对\n- 一个板块涨停潮的二阶效应：同概念发散、龙头带动产业链\n- 监管政策的二阶效应往往比政策本身影响更大",
        "tags": "[\"system\",\"cycle\",\"macro\"]"
    },
    {
        "name": "反馈回路",
        "icon": "🔁",
        "category": "系统思维",
        "description": "系统中的因果关系不是线性的，而是回路式的：A影响B，B反过来影响A，形成正反馈（加速）或负反馈（稳定）",
        "application": "识别股价趋势中的自强化（正反馈）和均值回归（负反馈）信号",
        "scenario": "股价连续上涨/下跌时、判断趋势持续性时",
        "example": "股价涨 → 更多人买 → 股价继续涨 → FOMO入场（正反馈，直到耗尽）",
        "detail": "## 核心理念\n\n市场由无数正反馈和负反馈回路构成。正反馈制造趋势和泡沫，负反馈带来均值回归和稳定。\n\n## 两种回路\n- **正反馈**：上涨强化上涨 → 趋势加速 → 终将崩溃\n- **负反馈**：上涨引发卖压 → 价格回归均值 → 系统稳定\n\n## 识别信号\n| 正反馈信号 | 负反馈信号 |\n|------------|------------|\n| 成交量持续放大 | 涨多了回吐 |\n| 媒体热议 | 估值修复完成 |\n| 融资余额攀升 | 技术指标超买 |\n\n## A股应用\n- A股散户占比较高，正反馈效应更强烈（涨更猛、跌更狠）\n- 量化策略加剧了正反馈——趋势跟踪策略不断强化已有趋势\n- 识别正反馈衰竭点是择时关键",
        "tags": "[\"system\",\"trend\",\"cycle\"]"
    },
    {
        "name": "涌现",
        "icon": "🦅",
        "category": "系统思维",
        "description": "个体简单规则通过大量交互产生整体层面的复杂行为。个股走势简单，但市场整体行为不可预测",
        "application": "不从单个股票去预测大盘，而是从整体结构去理解市场状态",
        "scenario": "市场情绪分析、板块联动分析时",
        "example": "每只蚂蚁只是遵循简单规则，蚁群却能建出复杂蚁穴。同样，每个交易者都在各自决策，却产生了「市场情绪」这个涌现现象",
        "detail": "## 核心理念\n\n市场是一个典型的涌现系统：无数个体独立决策，却产生了整体行情、板块轮动、风格切换等宏观现象。\n\n## 投资启示\n1. **不要预测市场**：涌现系统本质不可精确预测\n2. **理解结构**：关注整体模式（涨跌比、板块分化、资金流向）而非具体点位\n3. **利用而非对抗**：当涌现模式出现时，顺势而为更有效\n\n## A股应用\n- 涨停潮是典型的涌现现象\n- 板块轮动的涌现规律：科技→消费→周期→防御\n- 市场情绪的涌现指标：涨跌比、涨停家数、连板高度",
        "tags": "[\"system\",\"macro\",\"complexity\"]"
    },
    {
        "name": "熵增定律",
        "icon": "⚡",
        "category": "系统思维",
        "description": "封闭系统总是从有序走向无序。企业如果不注入外部能量（创新/改革），必然走向衰败",
        "application": "判断企业护城河是否在被侵蚀、竞争优势是否可持久",
        "scenario": "分析长期持有的标的、判断竞争格局时",
        "example": "曾经的诺基亚——没有外部创新注入，系统持续熵增，最终被市场淘汰",
        "detail": "## 核心理念\n\n热力学第二定律在商业中的投射：所有系统都趋向混乱。企业需要持续「做功」才能维持秩序。\n\n## 投资应用\n1. **护城河的本质**：不是壁垒本身，而是抵抗熵增的能力\n2. **持续创新的必要性**：不进步的「价值股」终将被侵蚀\n3. **管理团队评估**：优秀的管理层是注入负熵的关键\n\n## A股实战\n- 传统行业龙头的熵增更慢（如白酒、银行）\n- 科技行业熵增速率极快——今天的护城河明天可能消失\n- 资产重组/管理层变革可能是注入负熵的信号",
        "tags": "[\"system\",\"moat\",\"long-term\"]"
    },

    # ========== 风险管理 ==========
    {
        "name": "反脆弱",
        "icon": "🛡️",
        "category": "风险管理",
        "description": "有些东西在波动、冲击和混乱中不但不受损，反而受益。不仅是「扛住」波动，而是「从波动中获利」",
        "application": "仓位管理：你的组合在极端行情中是受益还是受损？设计「有下限无上限」的结构",
        "scenario": "市场波动加大时、不确定性高时、构建投资组合时",
        "example": "在投资组合中加入尾部对冲期权——如果市场平稳，损失有限；但如果暴跌，则大赚。这就是反脆弱结构",
        "detail": "## 核心理念\n\n塔勒布的「三体分类」：\n- **脆弱**：害怕波动——多数高杠杆/高负债企业\n- **坚韧**：扛住波动——优质蓝筹股\n- **反脆弱**：从波动中受益——波动率策略、危机买入\n\n## 三个策略\n1. **杠铃策略**：90%极度安全 + 10%极度风险\n2. **减少脆弱性**：识别并降低组合中的脆弱因素\n3. **利用压力**：市场恐慌时正是反脆弱者出手时机\n\n## A股实战\n- 暴跌中选加仓标的：不是所有跌的都能买，要找反脆弱的（行业景气+龙头+好价格）\n- 分散不一定是反脆弱——相关系数为1的分散是伪分散\n- 港股/A股如果相关性低，配置两者才是真反脆弱",
        "tags": "[\"risk\",\"blackswan\",\"tail\"]"
    },
    {
        "name": "杠铃策略",
        "icon": "🏋️",
        "category": "风险管理",
        "description": "放弃平庸的中间地带，将资产分布在两个极端：极度安全 + 极度冒险。中间地带才是真正的风险区",
        "application": "资产配置：90%低风险（国债/指数ETF）+ 10%高风险（期权/创投/小盘成长股）",
        "scenario": "构建投资组合、不确定市场方向时",
        "example": "塔勒布建议：90%的资产放在零风险的国债里，10%放在高风险高回报的投机中。中间地带的「中等风险」资产其实最危险——它们给你虚假安全感",
        "detail": "## 核心理念\n\n中间地带（「中等风险」资产）给你一种「我还好」的假象，实际上既不能带来足够的安全，也放弃了高收益的可能性。\n\n## 投资组合应用\n- **安全端**：国债、高等级债券、指数ETF、现金\n- **风险端**：个股期权、创投、小盘成长股、加密货币\n- **放弃**：中等风险的「偏股基金」「结构化理财产品」\n\n## A股实战\n- 安全端：沪深300 ETF + 高股息个股\n- 风险端：热门概念/成长股/FD期权\n- 杠铃策略的核心是两侧仓位严格分离，不发生漂移",
        "tags": "[\"risk\",\"portfolio\",\"allocation\"]"
    },
    {
        "name": "路径依赖",
        "icon": "🚂",
        "category": "风险管理",
        "description": "过去的决策会限制未来的选择空间，即使当前的路径不是最优的，转换成本也使得你难以改变",
        "application": "反省自己的持仓是否因沉没成本而舍不得卖、是否有「因为一直这么做所以继续」的惯性",
        "scenario": "持有亏损股票犹豫是否止损时、长期维持某种交易模式时",
        "example": "买了某股后持续下跌，但「已经亏了这么多，现在卖不就真亏了吗」——这就是路径依赖：因为过去投入而影响当下理性判断",
        "detail": "## 核心理念\n\n路径依赖是理性的敌人。沉没成本不应该影响未来决策，但人类大脑很难做到。\n\n## 三种表现\n1. **沉没成本**：因为投入了，所以不舍得放弃\n2. **惯性持仓**：因为「一直在持有」，所以继续持有\n3. **习惯性行为**：因为「上次这么做赚了」，所以这次也这么做\n\n## 打破的方法\n- **清零思维**：假设今天空仓，我会买它吗？\n- **外部视角**：如果我是一个旁观者，会怎么评价这个决策？\n- **情景测试**：如果明天停牌一年，我的决定会变吗？\n\n## A股实战\n- 套牢后一直死扛是最常见的路径依赖\n- 「价值投资」成&apos;了死扛的借口——价值投资≠不止损\n- 主动打破路径依赖：每季度重新审阅所有持仓的理由",
        "tags": "[\"risk\",\"psychology\",\"stop\"]"
    },
    {
        "name": "黑天鹅",
        "icon": "🦢",
        "category": "风险管理",
        "description": "具有三个特征的罕见事件：①不可预测 ②冲击巨大 ③事后人们会试图解释它本应可预测",
        "application": "不为不可能发生的极端事件做精确预测，而是确保组合能扛住任何黑天鹅",
        "scenario": "当市场一切平稳、波动率极低时（黑天鹅往往在大家最安心时降临）",
        "example": "2008年金融危机、2020年新冠疫情——每次黑天鹅前都有人说「这次不一样」",
        "detail": "## 核心理念\n\n黑天鹅不是「如果发生怎么办」，而是「什么时候发生」。关键不是预测，是做好准备。\n\n## 四个应对原则\n1. **承认无知**：我们无法预测下一次黑天鹅\n2. **减少脆弱性**：确保黑天鹅来临时你不会被摧毁（不加杠杆）\n3. **利用正向黑天鹅**：某些科技股的机会就是正向黑天鹅\n4. **别被解释欺骗**：事后大家都会说「这是显而易见的」\n\n## A股实战\n- **负向黑天鹅**：财务造假、政策突变、债务危机 → 分散配置\n- **正向黑天鹅**：技术突破、政策利好 → 保持仓位灵活\n- 最危险的时候是「一切都很好」的时候\n- 最低风险准备金：永远保留30%现金或等价物",
        "tags": "[\"risk\",\"blackswan\",\"tail\"]"
    },

    # ========== 行为金融 ==========
    {
        "name": "锚定效应",
        "icon": "⚓",
        "category": "行为金融",
        "description": "人类在做判断时过度依赖最先获得的信息（「锚」），即使这个信息与当下决策无关",
        "application": "避免被买入价/历史高点锚定。估值应该基于当下价值，而非你当初买入的价格",
        "scenario": "持有亏损股不舍得卖（等回本）、评估当前价格贵不贵时",
        "example": "某股从100跌到60，你买入成本是90。现在问你60贵不贵——你心里想的是「比90便宜」，但合理估值可能是50。被买入价锚定了",
        "detail": "## 核心理念\n\n锚定效应是投资中最顽固的偏误之一。那个最初的数字会持续影响你的判断。\n\n## 常见的锚\n1. **买入价锚**：「等回本就卖」\n2. **历史高点锚**：「从高点跌了这么多，便宜了」\n3. **分析师目标价锚**：「目标价100，现在80，还有空间」\n4. **同行估值锚**：「同行业PE都是30，它25，便宜」\n\n## 破解方法\n- 不看买入价，只看当前价格与内在价值的关系\n- 用「如果明天停牌3年，我现在会买吗？」来转换视角\n- 看多个估值模型（PE/PB/DCF/历史分位），避免单一锚\n\n## A股实战\n- 「从高点跌了50%」不是买入理由\n- 「等回本」是最差的卖出理由——它和投资毫无关系\n- 每笔交易都要有独立的买/卖逻辑，不关联历史价格",
        "tags": "[\"psychology\",\"bias\",\"sell\"]"
    },
    {
        "name": "确认偏误",
        "icon": "🔄",
        "category": "行为金融",
        "description": "人们倾向于寻找、注意和相信那些证实自己已有信念的信息，忽视反面证据",
        "application": "做研究时主动寻找反面论据：列出3个「我不该买这只股票」的理由，反驳自己",
        "scenario": "买入后、持仓中不断寻找利好数据时、研究报告中",
        "example": "你买入某股后，只关注关于它的好消息，坏消息来了你会想「这只是短期扰动」——你正在巩固自己的判断，而不是检验它",
        "detail": "## 核心理念\n\n确认偏误是理性决策的头号杀手。它让你永远觉得自己是对的，直到市场来纠正你。\n\n## 防御机制\n1. **反向清单**：每次买卖前写3个「不应该这么做」的理由\n2. **外部视角**：如果我的朋友买了这只股票，我会怎么评价？\n3. **对抗性研究**：专门找否定你观点的文章来读\n\n## 三种场景\n- **选中时**：只看到利好，忽略风险\n- **持有中**：把每根阳线都解读为「验证了我的判断」\n- **卖出后**：如果涨了→「卖早了」；如果跌了→「卖对了」\n\n## A股实战\n- 雪球/股吧的「回声室效应」会极大强化确认偏误\n- 机构研报80%是正向的——这就是确认偏误的商业化\n- 最好的防御：建立并遵守交易系统，减少主观判断",
        "tags": "[\"psychology\",\"bias\",\"research\"]"
    },
    {
        "name": "从众效应",
        "icon": "🐑",
        "category": "行为金融",
        "description": "个体在群体压力下放弃独立思考，跟随大多数人的行为——即使大多数可能是错的",
        "application": "当所有人都在讨论某只股票时，警惕。真正的机会往往在无人问津处",
        "scenario": "热门概念炒作时、媒体报道铺天盖地时、集体看多/看空时",
        "example": "2020年的「茅指数」——所有人都在买核心资产，形成正反馈。但当资金耗尽，从众效应反方向发威，踩踏式下跌",
        "detail": "## 核心理念\n\n从众在进化上是有利的——在原始社会，脱离群体意味着死亡。但在投资市场，脱离群体往往是盈利的来源。\n\n## 识别从众信号\n1. **媒体密度**：同一话题连篇累牍\n2. **周边讨论**：非投资圈朋友开始谈论\n3. **情绪极端**：要么极度乐观要么极度悲观\n4. **交易拥挤**：成交量/融资余额异常放大\n\n## 应对策略\n- **逆势思考**：当所有人都看多时警惕，看空时关注\n- **但不要逆势操作**：知道大家都在买≠你就要卖，趋势可能延续\n- **等待拥挤消散**：等成交量回落后再评估\n\n## A股实战\n- A股散户比例高，从众效应更显著\n- 涨停板上的「排队买入」是极端的从众行为\n- 利用从众：在恐慌时买入（逆向），在狂热时卖出（顺势）",
        "tags": "[\"psychology\",\"bias\",\"crowd\"]"
    },
    {
        "name": "幸存者偏差",
        "icon": "📊",
        "category": "行为金融",
        "description": "只看到成功者（幸存者），忽略了失败者（沉默的样本），导致高估成功的概率",
        "application": "看研报/业绩回顾时警惕：只展示成功案例，失败案例被选择性遗忘",
        "scenario": "看到某人的投资战绩辉煌时、研究某一策略的胜率时",
        "example": "你看到10个靠炒股致富的故事，心想「我也行」——但你没看到那1000个亏光了的人。媒体只报道成功者",
        "detail": "## 核心理念\n\n你看到的样本不是全量样本——失败者没有得到展示的机会。这导致你高估了胜率。\n\n## 投资中的表现\n1. **策略回溯**：只看历史成功的策略，忽略失效的\n2. **大师滤镜**：巴菲特成功了就学他的方法，但和他做同样事的人99%没成功\n3. **牛股回顾**：「早知道就买了」——你只看到了涨了的，没看到那100只没涨的\n\n## 防御方法\n- 问「失败案例是怎样的？」\n- 看行业的整体成功率，而非头部案例\n- 缩小样本：在时间维度上看自己所有交易，别只记得赚的那几笔\n\n## A股实战\n- 淘股吧/雪球上的「实盘大赛」冠军有极高的幸存者偏差\n- 「一年十倍」的故事背后是上千个一年亏50%的沉默样本\n- 回测时要算上交易成本、滑点、无法成交的情况",
        "tags": "[\"psychology\",\"bias\",\"statistics\"]"
    },

    # ========== 博弈竞争 ==========
    {
        "name": "纳什均衡",
        "icon": "♟️",
        "category": "博弈竞争",
        "description": "所有参与者都已选定最优策略，没有人可以通过单方面改变自己的策略获得更好结果",
        "application": "分析对手盘：如果你的对手是机构/量化基金，他们的最优策略是什么？你如何利用？",
        "scenario": "判断机构行为、分析量化策略博弈时",
        "example": "机构都在买同一个赛道 → 均衡被打破 → 有人先跑 → 踩踏。在均衡打破前或打破后行动，不要和人群一起行动",
        "detail": "## 核心理念\n\n每个参与者都在做对自己最有利的事，但整体结果可能对所有人都不是最优的——这就是「囚徒困境」。\n\n## 对手盘分析\n1. **机构**：大批量、流动性要求高、季度考核\n2. **游资**：快进快出、追涨杀跌、情绪驱动\n3. **量化**：策略趋同、因子拥挤、反转快\n4. **散户**：情绪化、追高杀低、反应慢\n\n## 策略\n- 识别当前市场的「均衡点」在哪里\n- 判断这个均衡是否可持续\n- 在均衡被打破前/后被动作，不要和所有人一起行动\n\n## A股实战\n- 量化基金的火爆导致「因子拥挤」——大家都用的策略会失效\n- 机构抱团是典型的纳什均衡：谁先走谁吃亏，但没人走了就要崩\n- 打破均衡的催化剂：黑天鹅、政策变化、业绩爆雷",
        "tags": "[\"game\",\"institution\",\"strategy\"]"
    },
    {
        "name": "红皇后效应",
        "icon": "🏃",
        "category": "博弈竞争",
        "description": "在这个世界，你必须拼命奔跑才能保持在原地。竞争越激烈，生存门槛越高",
        "application": "评估企业的竞争可持续性：它的竞争对手在做什么？它的优势能维持多久？",
        "scenario": "分析高竞争行业的龙头股、判断护城河深度时",
        "example": "智能手机行业：每年都要推出更强的芯片、更好的相机、更快的充电，只是因为「不做就落后了」——这种被迫创新就是红皇后效应",
        "detail": "## 核心理念\n\n出自《爱丽丝镜中奇遇》：红皇后说「在这里，你必须尽力奔跑才能停在原地」。在商业竞争中，进步是常态，不进步就意味着倒退。\n\n## 投资应用\n1. **高竞争行业**（科技/消费电子）：利润被持续投入研发，股东回报低\n2. **低竞争行业**（公用事业/白酒/烟草）：躺着也能赚钱\n3. **判断标准**：这家公司的护城河是否在免于红皇后效应？\n\n## A股实战\n- 锂电行业就是典型的红皇后效应——技术迭代快，产能过剩\n- 白酒不是——品牌壁垒让新进入者几乎无法挑战\n- 投资红皇后行业要买龙头（唯一幸存者），且不能长期持有\n- 投资免于红皇后效应的行业可以长期持有",
        "tags": "[\"game\",\"moat\",\"competition\"]"
    },
    {
        "name": "生态位",
        "icon": "🌿",
        "category": "博弈竞争",
        "description": "每个企业都有其独特的生态位——在行业中占据的特定位置和角色。找不到生态位的企业会被淘汰",
        "application": "找「在某个细分领域独一无二」的公司，避开「什么都做但什么都做不精」的公司",
        "scenario": "分析中小市值公司、寻找细分龙头时",
        "example": "一个专做汽车传感器芯片的小公司，虽然市场份额只有5%，但技术壁垒极高，高端客户离不开它——这就是一个牢固的生态位",
        "detail": "## 核心理念\n\n大自然的生态位原则：两种物种不能永久占据同一生态位。商业上，没有独特生态位的企业必然被淘汰。\n\n## 三种生态位\n1. **价格领先**（成本最低）——如格力、美的\n2. **差异化**（无可替代）——如茅台（品牌）、海天（渠道）\n3. **聚焦细分**（小而精）——专精特新\n\n## 判断方法\n- 如果这家公司明天倒闭，谁会受损？他们的损失有多大？\n- 替代这家公司的难度有多大？\n- 这家公司在行业中是否有一个独特的「没有人做得更好」的位置？\n\n## A股实战\n- 小盘股必须有清晰的生态位才值得投资\n- 「专精特新」本质就是生态位投资\n- 不要投「行业里排第四、第五」的公司——它的生态位不牢固\n- 判断生态位是否在扩大（增长）还是被侵蚀（萎缩）",
        "tags": "[\"game\",\"moat\",\"niche\"]"
    },
    {
        "name": "创造性破坏",
        "icon": "💥",
        "category": "博弈竞争",
        "description": "新事物通过摧毁旧事物来实现进步。旧公司的灭亡是新公司崛起的前提",
        "application": "投资颠覆者，而非被颠覆者。判断一个行业是否正在被技术/模式颠覆",
        "scenario": "技术变革期、传统行业升级转型时、新兴产业投资时",
        "example": "电动车对燃油车的颠覆、互联网对传统零售的颠覆、移动支付对银行的颠覆——每一次创造性破坏都创造了巨大的投资机会",
        "detail": "## 核心理念\n\n熊彼特的洞见：经济进步不是渐进的，而是通过「创造性的毁灭风暴」实现的。旧的结构被打破，新的结构建立。\n\n## 投资启示\n1. **辨别谁是颠覆者**：技术/模式领先，成本结构更优\n2. **识别谁将被颠覆**：商业模式脆弱、技术落后、客户流失\n3. **时机是关键**：太早进入会被「旧势力」熬死，太晚进入已错过最大涨幅\n\n## 三个信号\n- 颠覆者的产品达到主流用户的「够好用」门槛\n- 被颠覆者的利润开始下降\n- 传统龙头开始做同样的事（但他们往往太慢了）\n\n## A股实战\n- A股的创造性破坏通常来得很猛（政策+市场双重驱动）\n- 光伏行业的平价上网就是创造性破坏的典型案例\n- 投资颠覆者时不要用传统估值（PE/PB不适用）\n- 注意监管可能保护旧行业、抑制创造性破坏",
        "tags": "[\"game\",\"innovation\",\"disruption\"]"
    },
    {
        "name": "均值回归",
        "icon": "↩️",
        "category": "投资决策",
        "description": "极端的表现会随着时间回归平均水平。不仅是统计学规律，也是金融市场的核心力量",
        "application": "股价大幅偏离均线时、估值处于历史极端分位时、连续大涨/大跌后",
        "scenario": "连续大涨想追高时、连续大跌想抄底时、想判断趋势是否持续时",
        "example": "某PE从15倍涨到40倍（远超历史均值）→ 即使公司没变差，估值大概率会回归。反之，恐慌性暴跌到PE=8倍时，也是均值回归的机会",
        "detail": "## 核心理念\n\n均值回归不是数学必然，但在金融市场上极为普遍。人性中的贪婪和恐惧导致价格总是偏离价值，然后回归。\n\n## 适用范围\n| 强均值回归 | 弱均值回归 |\n|------------|------------|\n| PE/PB估值 | 营收增速 |\n| 情绪指标 | 利润增速 |\n| 波动率 | 市场份额 |\n| 板块相对收益 | 竞争格局 |\n\n## 实战应用\n- **超买超卖**：RSI>70或<30时，回归概率大\n- **估值分位**：PE处于历史90%分位以上 → 警惕回归\n- **板块轮动**：连续跑赢的板块可能回调，连续跑输的板块可能反弹\n\n## A股实战\n- A股的均值回归比美股更剧烈（散户情绪化导致超调）\n- 但「这次不一样」在A股也可能成立——结构性变化会改变均值\n- 牛市中的均值回归不是顶部——等出现了顶部信号再做判断\n- 均线（尤其是MA60/MA200）是均值回归的重要参考位",
        "tags": "[\"value\",\"cycle\",\"reversal\"]"
    },
]

# -----------------------------------------------------------
# API: 思维模型库
# -----------------------------------------------------------

@router.get("/models")
def list_models(category: str = Query(None), tag: str = Query(None)):
    """获取思维模型列表，支持按分类/标签筛选"""
    conn = get_db()
    sql = "SELECT * FROM mental_models"
    params = []
    where = []
    if category:
        where.append("category = ?")
        params.append(category)
    if tag:
        where.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/models/{model_id}")
def get_model(model_id: int):
    """获取单个模型的完整详情"""
    conn = get_db()
    row = conn.execute("SELECT * FROM mental_models WHERE id = ?", (model_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "模型不存在")
    return dict(row)


@router.get("/categories")
def list_categories():
    """获取模型分类列表"""
    conn = get_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM mental_models GROUP BY category ORDER BY category"
    ).fetchall()
    conn.close()
    return [{"category": r["category"], "count": r["count"]} for r in rows]


# -----------------------------------------------------------
# API: 每日思维模型训练
# -----------------------------------------------------------

@router.get("/daily-training")
def get_daily_training(date_str: str = Query(None, alias="date")):
    """获取指定日期的训练记录（如无则自动创建）"""
    today = date_str or date.today().isoformat()

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM model_trainings WHERE training_date = ? ORDER BY id DESC LIMIT 1",
        (today,)
    ).fetchone()

    if existing:
        conn.close()
        return dict(existing)

    # 自动创建今日训练
    training = _create_daily_training(today, conn)
    conn.close()
    return training


def _create_daily_training(today: str, conn: sqlite3.Connection) -> dict:
    """自动创建今日思维模型训练：选择一个模型 + 结合今日行情"""
    from backend.routers.market import _load_csv

    # 随机选一个模型（基于今日特征+轮询）
    row = conn.execute(
        "SELECT id, name, icon, category, description, application, scenario, example, detail, tags FROM mental_models ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    if not row:
        return {"error": "思维模型库为空"}
    model = dict(row)

    # 获取今日行情
    today_date = date.today().isoformat()
    df = _load_csv(today_date, "close")
    market_summary = {}
    if df is not None:
        valid = df[df["change_pct"].notna()]
        up_count = int((valid["change_pct"] > 0).sum())
        down_count = int((valid["change_pct"] < 0).sum())
        avg_chg = round(float(valid["change_pct"].mean()), 2)
        max_up = round(float(valid["change_pct"].max()), 2)
        max_down = round(float(valid["change_pct"].min()), 2)
        market_summary = {
            "total": len(valid),
            "up": up_count, "down": down_count,
            "avg_change": avg_chg,
            "max_up": max_up, "max_down": max_down,
            "up_ratio": round(up_count / len(valid) * 100, 1) if len(valid) > 0 else 0,
        }

    # 构建训练答案：将模型连接今日行情
    training_answer = _build_training_answer(model, market_summary, today)

    # 生成预测（基于模型逻辑对明天的判断）
    prediction = _build_prediction(model, market_summary)

    # 保存
    now = date.today().isoformat()
    market_json = json.dumps(market_summary, ensure_ascii=False)
    conn.execute(
        """INSERT INTO model_trainings 
           (model_name, training_date, market_context, training_answer, prediction, market_context_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (model["name"], today, market_json, training_answer, prediction, now)
    )
    conn.commit()

    result = conn.execute(
        "SELECT * FROM model_trainings WHERE training_date = ? ORDER BY id DESC LIMIT 1",
        (today,)
    ).fetchone()
    return dict(result) if result else {"error": "创建失败"}


def _build_training_answer(model: dict, market: dict, today: str) -> str:
    """生成训练答案：模型解释 + 今日行情结合 + 训练题"""
    model_name = model["name"]
    model_icon = model.get("icon", "🧠")
    model_category = model.get("category", "")
    model_desc = model["description"]
    model_application = model.get("application", "")
    model_scenario = model.get("scenario", "")
    model_example = model.get("example", "")
    model_detail = model.get("detail", "")

    # 从 detail 中提取核心理念（第一段）
    core_concept = ""
    if "核心理念" in model_detail:
        parts = model_detail.split("## 核心理念")
        if len(parts) > 1:
            core_part = parts[1].split("##")[0].strip()
            # 取前150字
            core_concept = core_part[:200]
    if not core_concept:
        core_concept = model_desc

    # 从 detail 中提取 A股实战
    a_share_tip = ""
    for section_title in ["A股实战", "A股应用", "实战应用"]:
        if section_title in model_detail:
            parts = model_detail.split(f"## {section_title}")
            if len(parts) > 1:
                a_share_part = parts[1].split("##")[0].strip()
                a_share_tip = a_share_part[:200]
                break

    model_question = _get_model_question(model_name)

    if not market:
        return f"""## {model_icon} 今日思维模型：{model_name}

**分类：** {model_category}

### 📖 模型解释

**是什么：** {model_desc}

**核心理念：** {core_concept}

**如何应用：** {model_application}

**何时使用：** {model_scenario}

**案例：** {model_example}

### ✍️ 训练题

{model_question}

---

*今日无行情数据，但模型学习不受影响。思考上面问题并记录你的答案。*"""

    up = market.get("up", 0)
    down = market.get("down", 0)
    avg_chg = market.get("avg_change", 0)
    max_up = market.get("max_up", 0)
    max_down = market.get("max_down", 0)
    up_ratio = market.get("up_ratio", 0)
    total = market.get("total", 0)

    # 判断市场状态
    if up_ratio >= 70:
        market_state = "🔥 强势普涨"
    elif up_ratio >= 55:
        market_state = "📈 震荡偏强"
    elif up_ratio >= 40:
        market_state = "⚖️ 震荡格局"
    elif up_ratio >= 20:
        market_state = "📉 震荡偏弱"
    else:
        market_state = "❄️ 全面走弱"

    model_insight = _get_model_insight(model_name, market)

    # A股实战 tip
    a_share_section = ""
    if a_share_tip:
        a_share_section = f"""

### 🎯 今日A股实战提示

{a_share_tip}

"""

    answer = f"""## {model_icon} 今日思维模型训练：{model_name}

**分类：** {model_category}

---

### 📖 模型解释

**🧩 是什么？**

{model_desc}

**💡 核心理念**

{core_concept}

**🛠️ 如何应用在投资中？**

{model_application}

**📌 什么时候用？**

{model_scenario}

**📝 案例**

{model_example}
{a_share_section}
---

### 📊 今日市场状态

| 指标 | 数值 |
|------|------|
| 全市场状态 | {market_state} |
| 上涨/下跌 | {up}/{down} |
| 涨跌比 | {up_ratio}% |
| 平均涨跌幅 | {avg_chg:+.2f}% |
| 日内最强 | {max_up:+.2f}% |
| 日内最弱 | {max_down:+.2f}% |

### 🔗 模型如何连接今日行情？

{model_insight}

### ✍️ 今日训练题

{model_question}

---
*明天会基于今日行情自动生成反思。好好思考上面的问题，看看现实的答案是什么。*"""
    return answer


def _build_prediction(model: dict, market: dict) -> str:
    """基于模型逻辑生成对明天的预测"""
    name = model["name"]
    up_ratio = market.get("up_ratio", 50)
    avg_chg = market.get("avg_change", 0)
    max_up = market.get("max_up", 0)
    max_down = market.get("max_down", 0)

    predictions = {
        "均值回归": f"今日涨跌比{up_ratio}%，{'偏热' if up_ratio > 60 else '偏冷' if up_ratio < 40 else '均衡'}。均值回归思维提示：明日可能出现{'回调' if up_ratio > 60 else '反弹' if up_ratio < 40 else '延续震荡'}",
        "反脆弱": f"今日波动{'较大' if abs(avg_chg) > 1.5 else '较小'}。如果明日波动加大，反脆弱结构将从中受益。关注明日波动率是否上升",
        "反馈回路": f"今日涨跌比{up_ratio}%，{'正反馈强化中，明日可能延续趋势' if up_ratio > 60 or up_ratio < 30 else '负反馈主导，明日可能出现均值回归'}",
        "二阶效应": f"关注今日强势板块明日的资金流向二阶效应——资金从哪来、会不会扩散到关联板块",
        "从众效应": f"今日涨跌比{up_ratio}%显示{'一致性偏强，警惕明日反转' if abs(up_ratio - 50) > 20 else '市场分歧不大，明日可能延续'}",
        "锚定效应": f"投资者可能被今日的{'上涨' if avg_chg > 0 else '下跌'}锚定，影响明日开盘判断。关注明日开盘是否与今日收盘有显著差异",
        "纳什均衡": f"今日格局下的均衡状态是否可持续？关注明日是否有打破均衡的催化事件",
        "安全边际": f"今日{'普涨' if up_ratio > 60 else '下跌'}后关注估值安全边际的变化——{'上涨压缩安全边际，明日追高风险加大' if up_ratio > 60 else '下跌创造安全边际，可筛选被错杀的标的'}",
        "机会成本": f"今日市场格局下，当前持仓的机会成本是否发生变化？关注明日是否出现更好的替代方向",
        "第二层思维": f"市场对今日行情的共识是什么？明日是否会出现与共识相反的走势——关注盘前预期差",
        "能力圈": f"今日{'热点较多' if up_ratio > 60 else '板块分化明显'}，能力圈要求你只做自己懂的。预测：明日非能力圈内的追涨行为大概率亏损，守住熟悉领域的个股",
        "复利效应": f"今日{'上涨' if avg_chg > 0 else '下跌'}幅度{abs(avg_chg):.1f}%，一次涨跌不是问题，复利看连续性。预测：明日市场斜率可能放缓，关键在于不出现大回撤",
        "路径依赖": f"今日行情延续了近期的{'强势' if up_ratio > 55 else '弱势'}格局。预测：除非出现外部催化打破路径，否则明日趋势大概率延续",
        "黑天鹅": f"今日市场{'相对平静' if abs(avg_chg) < 1 else '波动较大'}，但平静期恰是黑天鹅最容易被忽视的时候。预测：关注明日可能出现的预期外事件",
        "确认偏误": f"今日{'涨多跌少' if up_ratio > 50 else '跌多涨少'}的环境容易强化看{'多' if up_ratio > 50 else '空'}者的确认偏误。预测：明日应主动寻找反向信号，警惕一致性预期被打破",
        "幸存者偏差": f"今日涨幅榜上的明星股吸引眼球，但幸存者偏差让你看不到更多下跌的股票。预测：明日关注跌幅榜中被错杀的标的，而非追涨今日的幸存者",
        "红皇后效应": f"今日{'强势板块与其他板块差距拉大' if abs(max_up) > 3 else '板块间差距不大'}。红皇后效应下你必须比别人跑得更快才能保持位置。预测：明日弱势板块可能有修复性反弹",
        "生态位": f"今日市场生态中，不同市值和风格的板块占据不同生态位。预测：明日大小盘风格可能发生切换，关注资金从拥挤生态位流向冷门生态位",
        "创造性破坏": f"今日{'领涨板块体现了创新驱动的特征' if up_ratio > 50 else '市场虽弱但部分创新品值得关注'}。预测：明日新技术/新政策相关板块可能成为破坏性创新的受益者",
        "杠铃策略": f"今日{'波动较大' if abs(avg_chg) > 1.5 else '波动温和'}，杠铃策略（极致保守+极致进取）优于中间仓位。预测：明日若波动加大，杠铃结构将跑赢大盘",
        "涌现": f"今日上涨{market.get('up',0)}/下跌{market.get('down',0)}，市场行为是个股行为的涌现结果。预测：关注今日走强的板块中是否有涌现出来的细分方向",
        "熵增定律": f"今日市场{'趋于混乱' if abs(avg_chg) > 1.5 else '趋于有序'}。预测：明日可能从{'高熵回归有序' if abs(avg_chg) > 1.5 else '低熵走向混沌'}，做好预案",
    }

    return predictions.get(name, f"基于「{name}」模型观察明日市场如何演绎")


def _get_model_question(model_name: str) -> str:
    """返回与模型对应的思考题"""
    questions = {
        "安全边际": "**思考题：** 当前你的持仓中有多少安全边际？如果明天跌5%，你还会继续持有吗？",
        "能力圈": "**思考题：** 选一只你持有的股票，你能用两句话说清楚它怎么赚钱吗？它的三个竞争对手是谁？",
        "复利效应": "**思考题：** 你今天的交易决策是增加了复利还是损耗了复利？交易成本、税费、情绪化操作——哪些在消耗你的复利？",
        "机会成本": "**思考题：** 如果不持有当前仓位，今天你会买入什么？那个选择的预期收益比现在高吗？",
        "第二层思维": "**思考题：** 今天市场最大的共识是什么？你的观点与共识有什么不同？你的不同是对的吗？",
        "二阶效应": "**思考题：** 今天领涨板块上涨后，资金从哪流出？下一个受益板块可能是谁？",
        "反馈回路": "**思考题：** 识别今天市场中的一个正反馈循环——这个循环什么时候会衰竭？",
        "涌现": "**思考题：** 今天市场整体表现是哪些个股/板块的涌现结果？有没有新的涌现模式正在形成？",
        "熵增定律": "**思考题：** 你的持仓企业在做哪些「抵抗熵增」的努力？这些努力有效吗？",
        "反脆弱": "**思考题：** 如果明日市场反向波动5%，你的组合是受益还是受损？你设计了反脆弱结构吗？",
        "杠铃策略": "**思考题：** 你的资产分布是杠铃型的还是中间型的？中间地带的风险你注意到了吗？",
        "路径依赖": "**思考题：** 你当前的持仓中，有哪些是因为「一直拿着所以没卖」而不是因为「仍然看好」？",
        "黑天鹅": "**思考题：** 今天市场一片平静，但什么事件会让你的组合遭受重创？你有预案吗？",
        "锚定效应": "**思考题：** 你今天的判断被什么数字「锚住」了？是买入价？历史高点？还是某个目标价？",
        "确认偏误": "**思考题：** 今天你做的所有交易决策中，有没有主动寻找反面论据？如果没有，你可能陷入了确认偏误。",
        "从众效应": "**思考题：** 今天市场上最热门的讨论是什么？你参与了吗？这是独立判断还是跟风？",
        "幸存者偏差": "**思考题：** 看看今天涨跌幅榜——你注意到跌的股票了吗？你的注意力是倾向于看涨的还是看跌的？",
        "纳什均衡": "**思考题：** 如果你今天交易的对手是量化基金，他们会怎么做？你的策略和他们的最优策略一致吗？",
        "红皇后效应": "**思考题：** 你的持仓公司今天做的「被迫创新」是什么？这些投入真的能转化为股东回报吗？",
        "生态位": "**思考题：** 选择一只观察池中的股票，它在行业中占据什么样的生态位？这个位置牢固吗？",
        "创造性破坏": "**思考题：** 今天哪个板块最热？这是创造性破坏还是短期炒作？如果是真变革，颠覆者是谁？",
        "均值回归": "**思考题：** 今天市场中哪些指标或板块处于极端位置？均值回归的可能性有多大？",
    }
    return questions.get(model_name, f"**思考题：** 运用「{model_name}」模型反思今天的一个交易决策。做得对吗？为什么？")


def _get_model_insight(model_name: str, market: dict) -> str:
    """将模型与今日行情结合，生成有深度的连接分析"""
    up_ratio = market.get("up_ratio", 50)
    avg_chg = market.get("avg_change", 0)
    max_up = market.get("max_up", 0)
    max_down = market.get("max_down", 0)

    insights = {
        "安全边际": f"今日全市场平均涨跌{avg_chg:+.2f}%，{'上涨压缩安全边际' if avg_chg > 0 else '下跌创造安全边际'}。在今日行情中，寻找那些因为短期情绪而非基本面变化而下跌的股票，它们正在创造安全边际。",
        "能力圈": f"今日{'普涨' if up_ratio > 60 else '分化' if up_ratio > 40 else '普跌'}行情中，最容易犯的错误是 {'追涨不懂的板块' if up_ratio > 60 else '恐慌抛售理解的公司'}。用能力圈框定自己，今日行情之外的噪声可以忽略。",
        "复利效应": f"今日市场{'上涨' if avg_chg > 0 else '下跌'}，一次{'大赚' if avg_chg > 2 else '亏损'}看起来不错，但复利看的是持续性。问自己：今天的行为是可持续的还是侥幸的？",
        "机会成本": f"今日涨跌比{up_ratio}%，{'普涨' if up_ratio > 60 else '分化'}行情是检验机会成本的最佳时刻——你的持仓是否跑赢了今日强势板块？如果不是，机会成本在上升。",
        "第二层思维": f"今日涨跌比{up_ratio}%{'偏热' if up_ratio > 60 else '偏冷' if up_ratio < 40 else '均衡'}。市场的第一层思维是{'追涨' if up_ratio > 60 else '恐慌'}。第二层思维是：{'什么因素可能让这种情绪在明天反转' if up_ratio > 60 or up_ratio < 40 else '今天的均衡是否会被什么催化打破'}？",
        "二阶效应": f"今日最强板块涨幅{max_up:+.2f}%，最弱板块跌幅{max_down:+.2f}%。资金从弱者流向强者，二阶效应是什么？明日这些强势板块的供应链/关联板块可能受益。",
        "反馈回路": f"今日{'涨' if avg_chg > 0 else '跌'}幅居前的板块中，识别哪些存在正反馈（越涨越买/越跌越卖）。正反馈驱动的趋势持续性可能超出你的预期，但终将衰竭。",
        "从众效应": f"今日涨跌比{up_ratio}%，{'一致性偏强' if abs(up_ratio-50) > 20 else '分歧明显'}。{'从众信号已亮——大家都在做同一件事' if abs(up_ratio-50) > 20 else '当前从众效应不显著，可以保持独立思考'}。",
        "纳什均衡": f"今日行情格局下，机构的「最优策略」是什么？游资呢？量化呢？你的策略和他们的一致吗？如果机构在{'买入' if avg_chg > 0 else '卖出'}而你也在做同样的事，你是在搭便车还是在接盘？",
        "均值回归": f"今日{'涨' if avg_chg > 0 else '跌'}幅较大的板块和个股，正站在均值回归的起点还是终点？识别那些偏离均值最远的标的——回归的势能最大。",
        "反脆弱": f"今日波动{'较大' if abs(avg_chg) > 1 else '较小'}。反脆弱思维不是预测明日涨跌，而是无论涨跌都能应对。你的组合是脆弱的（害怕波动）还是反脆弱的（利用波动）？",
    }
    return insights.get(model_name, f"今日全市场涨跌比{up_ratio}%（涨{market.get('up')}家/跌{market.get('down')}家），平均涨跌{avg_chg:+.2f}%。运用「{model_name}」模型审视今日行情，思考其中蕴含的市场信息。")

@router.get("/daily-training/history")
def get_training_history(limit: int = Query(30, le=100)):
    """获取训练历史"""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, model_name, training_date, prediction, user_prediction, next_day_result, accuracy, reflection, user_answer FROM model_trainings ORDER BY training_date DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/daily-training/{training_id}")
def get_training_detail(training_id: int):
    """获取单条训练记录完整详情"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM model_trainings WHERE id = ?", (training_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="训练记录不存在")
    return dict(row)


@router.put("/daily-training/{training_id}/verify")
def verify_training(training_id: int, next_day_result: str = "", accuracy: str = "", reflection: str = ""):
    """验证前一日训练的预测结果"""
    conn = get_db()
    conn.execute(
        "UPDATE model_trainings SET next_day_result = ?, accuracy = ?, reflection = ? WHERE id = ?",
        (next_day_result, accuracy, reflection, training_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "id": training_id}


@router.put("/daily-training/{training_id}/prediction")
def save_user_prediction(training_id: int, user_prediction: str = ""):
    """保存用户的预测内容（同时清除旧评价，等待次日重新反思）"""
    conn = get_db()
    conn.execute(
        "UPDATE model_trainings SET user_prediction = ?, accuracy = '', reflection = '', next_day_result = '' WHERE id = ?",
        (user_prediction, training_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "id": training_id}


@router.put("/daily-training/{training_id}/answer")
def save_training_answer(training_id: int, user_answer: str = ""):
    """保存训练题的答案"""
    conn = get_db()
    conn.execute(
        "UPDATE model_trainings SET user_answer = ? WHERE id = ?",
        (user_answer, training_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "id": training_id}


@router.delete("/daily-training/{training_id}")
def delete_training(training_id: int):
    """删除训练记录"""
    conn = get_db()
    conn.execute("DELETE FROM model_trainings WHERE id = ?", (training_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted": training_id}


# -----------------------------------------------------------
# API: 行业涨跌分化追踪
# -----------------------------------------------------------

@router.get("/sector-dispersion/date/{date_str}")
def get_sector_dispersion(date_str: str):
    """获取指定日期所有行业的涨跌分化指标"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sector_dispersion WHERE date = ? ORDER BY abs(std_change) DESC",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/sector-dispersion/trend")
def sector_dispersion_trend(
    start: str = Query(None),
    end: str = Query(None),
    sector: str = Query(None)
):
    """获取行业分化指标的时间序列"""
    today = date.today()
    start_date = start or (today - timedelta(days=60)).isoformat()
    end_date = end or today.isoformat()

    conn = get_db()
    sql = "SELECT * FROM sector_dispersion WHERE date >= ? AND date <= ?"
    params = [start_date, end_date]
    if sector:
        sql += " AND sector = ?"
        params.append(sector)
    sql += " ORDER BY date, sector"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    # 按日期聚合
    from collections import defaultdict
    by_date = defaultdict(list)
    for r in rows:
        d = dict(r)
        by_date[d["date"]].append({
            "sector": d["sector"],
            "avg_change": d["avg_change"],
            "std_change": d["std_change"],
            "up_pct": d["up_pct"],
            "stock_count": d["stock_count"],
        })

    result = []
    for d in sorted(by_date.keys()):
        sectors = by_date[d]
        avg_std = round(float(np.mean([s["std_change"] for s in sectors])), 2) if sectors else 0
        max_std = round(float(max(s["std_change"] for s in sectors)), 2) if sectors else 0
        sector_stats = sorted(sectors, key=lambda s: s["std_change"], reverse=True)[:10]
        result.append({
            "date": d,
            "avg_dispersion": avg_std,
            "max_dispersion": max_std,
            "sectors": sector_stats,
            "sector_count": len(sectors),
        })

    return result


@router.post("/sector-dispersion/refresh")
def refresh_sector_dispersion(date_str: str = Query(None, alias="date")):
    """从当日行情CSV计算并刷新所有行业的涨跌分化指标"""
    from backend.routers.market import _load_csv

    target_date = date_str or date.today().isoformat()
    df = _load_csv(target_date, "close")
    if df is None:
        raise HTTPException(404, f"{target_date} 无行情数据")

    valid = df[df["change_pct"].notna() & df["sector"].notna() & (df["sector"] != "--")].copy()
    if valid.empty:
        raise HTTPException(404, f"{target_date} 无有效行业数据")

    conn = get_db()
    # 删除该日旧数据
    conn.execute("DELETE FROM sector_dispersion WHERE date = ?", (target_date,))
    inserted = 0

    for sector_name, group in valid.groupby("sector"):
        changes = group["change_pct"].dropna()
        if len(changes) < 3:
            continue
        avg_c = round(float(changes.mean()), 2)
        std_c = round(float(changes.std()), 2)
        pct_up = round(float((changes > 0).sum() / len(changes) * 100), 1)
        max_c = round(float(changes.max()), 2)
        min_c = round(float(changes.min()), 2)
        conn.execute(
            """INSERT INTO sector_dispersion 
               (date, sector, avg_change, std_change, up_pct, stock_count, max_change, min_change)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (target_date, sector_name, avg_c, std_c, pct_up, len(changes), max_c, min_c)
        )
        inserted += 1

    conn.commit()
    conn.close()
    return {"date": target_date, "sectors": inserted, "status": "ok"}


# -----------------------------------------------------------
# API: 板块周期分析（普涨/分化/冰点/冰点反弹/启动）
# -----------------------------------------------------------

@router.get("/sector-cycles")
def get_sector_cycles(date_str: str = Query(None, alias="date"), days: int = Query(3, le=10)):
    """分析各板块当前所处的市场周期阶段（优先读持久化，无则实时计算+自动保存）"""
    target_date = date_str or date.today().isoformat()
    conn = get_db()

    # 检查请求日期是否有 sector_dispersion，没有则 fallback
    has_data = conn.execute(
        "SELECT 1 FROM sector_dispersion WHERE date = ? LIMIT 1", (target_date,)
    ).fetchone()
    if not has_data:
        latest = conn.execute(
            "SELECT date FROM sector_dispersion ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if latest:
            target_date = latest["date"]
        else:
            conn.close()
            return {"date": target_date, "sectors": [], "message": "无行业分化数据，请先调用 refresh 生成"}

    # fallback 后再查缓存（确保命中）
    cached = conn.execute(
        "SELECT date FROM sector_cycles WHERE date = ? LIMIT 1", (target_date,)
    ).fetchone()
    if cached:
        rows = conn.execute(
            "SELECT * FROM sector_cycles WHERE date = ? ORDER BY phase_order, sector",
            (target_date,)
        ).fetchall()
        conn.close()
        if rows:
            return {
                "date": target_date,
                "total_sectors": len(rows),
                "sectors": [dict(r) for r in rows],
                "summary": _summarize_cycles([dict(r) for r in rows]),
                "source": "cache",
            }

    # 无缓存 → 从 sector_dispersion 实时计算
    today_rows = conn.execute(
        "SELECT * FROM sector_dispersion WHERE date = ? ORDER BY sector", (target_date,)
    ).fetchall()
    if not today_rows:
        conn.close()
        return {"date": target_date, "sectors": [], "message": "当日无行业分化数据"}

    # 获取前日数据用于冰点反弹/启动判定
    prev_date = (date.fromisoformat(target_date) - timedelta(days=days)).isoformat()
    prev_rows = conn.execute(
        "SELECT sector, avg_change FROM sector_dispersion WHERE date >= ? AND date < ? ORDER BY date DESC",
        (prev_date, target_date)
    ).fetchall()
    conn.close()

    prev_map = {}
    for r in prev_rows:
        d = dict(r)
        if d["sector"] not in prev_map:
            prev_map[d["sector"]] = d["avg_change"]

    phase_order = {"高潮🎯": 0, "普涨🚀": 1, "启动🔥": 2, "冰点反弹🌱": 3, "筑底🏗️": 4,
                   "酝酿🌋": 5, "分化⚡": 6, "退潮🌊": 7, "防御🛡️": 8, "冰点❄️": 9,
                   "普跌📉": 10, "震荡⚖️": 11}

    result = []
    for r in today_rows:
        d = dict(r)
        phase, icon, color, desc = _classify_sector_phase(
            d["avg_change"], d["std_change"], d["up_pct"], prev_map.get(d["sector"])
        )
        result.append({
            "sector": d["sector"],
            "avg_change": d["avg_change"],
            "dispersion": d["std_change"],
            "up_pct": d["up_pct"],
            "stock_count": d["stock_count"],
            "max_change": d["max_change"],
            "min_change": d["min_change"],
            "phase": phase, "icon": icon, "color": color, "desc": desc,
        })

    result.sort(key=lambda x: phase_order.get(x["phase"], 99))

    # 自动持久化
    conn2 = get_db()
    conn2.execute("DELETE FROM sector_cycles WHERE date = ?", (target_date,))
    for s in result:
        conn2.execute(
            """INSERT OR IGNORE INTO sector_cycles
               (date, sector, avg_change, dispersion, up_pct, stock_count, max_change, min_change, phase, icon, phase_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (target_date, s["sector"], s["avg_change"], s["dispersion"], s["up_pct"],
             s["stock_count"], s["max_change"], s["min_change"],
             s["phase"], s["icon"], phase_order.get(s["phase"], 99))
        )
    conn2.commit()
    conn2.close()

    return {
        "date": target_date,
        "total_sectors": len(result),
        "sectors": result,
        "summary": _summarize_cycles(result),
        "source": "computed",
    }


@router.get("/sector-cycles/dates")
def get_sector_cycle_dates():
    """返回所有有周期研判数据的日期（降序）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT date FROM sector_cycles ORDER BY date DESC"
    ).fetchall()
    conn.close()
    dates = [r["date"] for r in rows]
    return {"dates": dates, "latest": dates[0] if dates else None}


@router.get("/sector-stocks")
def get_sector_stocks(
    sector: str = Query(...),
    date_str: str = Query(None, alias="date"),
):
    """获取指定行业/板块在指定日期的所有个股行情"""
    target_date = date_str or date.today().isoformat()
    df = _load_csv(target_date, "close")
    if df is None:
        df = _load_csv(target_date, "noon")
    if df is None:
        raise HTTPException(404, f"{target_date} 无行情数据")
    
    stocks = df[df["sector"] == sector].copy()
    if stocks.empty:
        raise HTTPException(404, f"{target_date} 行业 '{sector}' 无数据")
    
    result = []
    for _, row in stocks.iterrows():
        result.append({
            "code": str(row.get("code", "")),
            "name": str(row.get("name", "")),
            "close": float(row["close"]) if pd.notna(row.get("close")) else None,
            "change_pct": float(row["change_pct"]) if pd.notna(row.get("change_pct")) else None,
            "change": float(row["change"]) if pd.notna(row.get("change")) else None,
            "amount": round(float(row["amount"]) / 100_000_000, 2) if pd.notna(row.get("amount")) else None,
            "market_cap": float(row["market_cap"]) if pd.notna(row.get("market_cap")) else None,
            "turnover": float(row["turnover"]) if pd.notna(row.get("turnover")) else None,
            "pe": float(row["pe"]) if pd.notna(row.get("pe")) else None,
        })
    
    # 按涨跌幅排序
    result.sort(key=lambda x: x["change_pct"] or 0, reverse=True)
    
    return {
        "date": target_date,
        "sector": sector,
        "total": len(result),
        "stocks": result,
    }


@router.get("/sector-cycles/history")
def get_sector_cycle_history(
    sector: str = Query(...),
    start: str = Query(None),
    end: str = Query(None)
):
    """获取单个板块的周期历史"""
    today = date.today()
    start_date = start or (today - timedelta(days=60)).isoformat()
    end_date = end or today.isoformat()

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sector_dispersion WHERE sector = ? AND date >= ? AND date <= ? ORDER BY date DESC",
        (sector, start_date, end_date)
    ).fetchall()
    conn.close()

    # 获取前一天数据辅助判断
    prev_avg = None
    result = []
    for r in rows:
        d = dict(r)
        phase, icon, color, desc = _classify_sector_phase(
            d["avg_change"], d["std_change"], d["up_pct"], prev_avg
        )
        result.append({
            "date": d["date"],
            "avg_change": d["avg_change"],
            "dispersion": d["std_change"],
            "up_pct": d["up_pct"],
            "stock_count": d["stock_count"],
            "phase": phase,
            "icon": icon,
            "color": color,
            "desc": desc,
        })
        prev_avg = d["avg_change"]

    return {"sector": sector, "history": result}


def _classify_sector_phase(avg_change, dispersion, up_pct, prev_avg=None):
    """将板块当日指标分类为周期相位（完整12周期体系）"""

    # === 过热阶段 ===
    # 高潮🎯：极致普涨但分歧开始扩大 → 情绪顶点
    if avg_change > 3.5 and up_pct > 80 and dispersion > 3.5:
        return ("高潮🎯", "🎯", "#f56c6c",
                f"板块情绪高潮，涨幅{avg_change:+.2f}%，{up_pct:.0f}%个股上涨但分歧已现(σ={dispersion})，警惕转折")

    # 普涨🚀：强势普涨，分歧小 → 共识阶段
    if avg_change > 2.5 and up_pct > 75 and dispersion < 4:
        return ("普涨🚀", "🚀", "#67c23a",
                f"板块强势普涨，涨幅{avg_change:+.2f}%，{up_pct:.0f}%个股上涨，内部分歧小")

    # === 复苏阶段 ===
    # 启动🔥：前日弱势，今日放量上涨 → 转折信号
    if prev_avg is not None and prev_avg < 0.3 and avg_change > 1.5 and up_pct > 60:
        return ("启动🔥", "🔥", "#e6a23c",
                f"从弱势转强势启动，前日{prev_avg:+.2f}%→今日{avg_change:+.2f}%，上涨占比{up_pct:.0f}%")

    # === 衰退阶段 ===
    # 冰点❄️：深度回调 → 极端悲观
    if avg_change < -2.5 and up_pct < 25:
        return ("冰点❄️", "❄️", "#409eff",
                f"板块深度回调，跌幅{avg_change:+.2f}%，仅{up_pct:.0f}%个股上涨")

    # 普跌📉：广泛下跌但不算冰点
    if avg_change < -1.5 and up_pct < 35:
        return ("普跌📉", "📉", "#909399",
                f"板块普跌，跌幅{avg_change:+.2f}%，仅{up_pct:.0f}%个股上涨")

    # 退潮🌊：分化后的资金撤退，跌幅中等
    if avg_change < -0.3 and avg_change >= -1.5 and up_pct > 25 and up_pct < 55:
        return ("退潮🌊", "🌊", "#909399",
                f"板块退潮回落，跌幅{avg_change:+.2f}%，上涨占比{up_pct:.0f}%，资金在撤退")

    # === 底部阶段 ===
    # 冰点反弹🌱：前日为冰点/弱势，今日明显回暖
    if prev_avg is not None and prev_avg < -1.5 and avg_change > 1:
        return ("冰点反弹🌱", "🌱", "#67c23a",
                f"冰点后反弹，前日{prev_avg:+.2f}%→今日{avg_change:+.2f}%，上涨占比{up_pct:.0f}%")

    # 筑底🏗️：反弹后横盘夯实，涨跌微小但分歧低
    if prev_avg is not None and prev_avg >= -0.5 and prev_avg <= 0.5 and abs(avg_change) < 0.5 \
            and up_pct > 40 and up_pct < 60 and dispersion < 3:
        return ("筑底🏗️", "🏗️", "#67c23a",
                f"板块筑底夯实，两日振幅极小(前{prev_avg:+.2f}%→今{avg_change:+.2f}%)，分歧低(σ={dispersion})")

    # === 分歧阶段 ===
    # 分化⚡：内部分歧显著
    if dispersion > 4 and up_pct > 25 and up_pct < 75:
        return ("分化⚡", "⚡", "#f56c6c",
                f"板块内部分化严重，离散度{dispersion}，上涨占比仅{up_pct:.0f}%")

    # === 蓄势阶段 ===
    # 酝酿🌋：小幅上涨，分歧低，蓄势特征
    if avg_change > 0.5 and up_pct > 50 and up_pct < 75 and dispersion < 4:
        return ("酝酿🌋", "🌋", "#e6a23c",
                f"板块蓄势酝酿，涨幅{avg_change:+.2f}%，上涨占比{up_pct:.0f}%，分歧低(σ={dispersion})")

    # === 防守阶段 ===
    # 防御🛡️：微跌或微涨，上涨占比适中 → 防守特征
    if avg_change < 0 and up_pct > 35 and up_pct < 60:
        return ("防御🛡️", "🛡️", "#909399",
                f"板块窄幅偏弱，涨跌{avg_change:+.2f}%，上涨占比{up_pct:.0f}%，呈防御特征")

    # 震荡⚖️：无明显方向（兜底）
    return ("震荡⚖️", "⚖️", "#909399",
            f"板块震荡整理，涨跌{avg_change:+.2f}%，上涨占比{up_pct:.0f}%，离散度{dispersion}")



# ═══════════════════════════════════════════════════════════
# 主题主线定义（8条主线，每条包含若干细分行业）
# ═══════════════════════════════════════════════════════════
THEME_DEFINITIONS = [
    {
        "name": "科技线",
        "sectors": ["半导体", "软件开发", "IT服务Ⅱ", "消费电子", "计算机设备",
                    "游戏Ⅱ", "通信设备", "通信服务", "计算机应用", "云服务"],
        "description": "AI算力、软件、半导体等科技成长方向",
    },
    {
        "name": "有色资源线",
        "sectors": ["贵金属", "小金属", "工业金属", "能源金属", "金属新材料",
                    "焦炭Ⅱ", "冶钢原料", "化学原料"],
        "description": "有色金属、贵金属及上游原材料",
    },
    {
        "name": "地产基建线",
        "sectors": ["房地产开发", "基础建设", "装修建材", "工程机械", "装修装饰Ⅱ",
                    "水泥", "玻璃玻纤", "房屋建设Ⅱ"],
        "description": "房地产、基建、建材链",
    },
    {
        "name": "新能源线",
        "sectors": ["光伏设备", "电池", "电网设备", "风电设备", "储能",
                    "其他电源设备Ⅱ", "环保设备Ⅱ", "综合环境治理"],
        "description": "光伏、风电、锂电池、储能等新能源产业链",
    },
    {
        "name": "医药生物线",
        "sectors": ["化学制药", "中药Ⅱ", "生物制品", "医疗器械", "医疗服务",
                    "医药商业", "医药研发外包"],
        "description": "创新药、中药、医疗器械等大健康方向",
    },
    {
        "name": "消费线",
        "sectors": ["白酒Ⅱ", "食品加工", "家电零部件Ⅱ", "调味发酵品Ⅱ", "饮料乳品",
                    "服装家纺", "美容护理", "互联网电商", "专业连锁Ⅱ"],
        "description": "食品饮料、家电、服饰等大消费",
    },
    {
        "name": "军工线",
        "sectors": ["航天装备Ⅱ", "航空装备Ⅱ", "地面装备Ⅱ", "军工电子Ⅱ",
                    "航海装备Ⅱ", "军工信息化"],
        "description": "航空航天、国防装备",
    },
    {
        "name": "汽车线",
        "sectors": ["汽车零部件", "乘用车", "商用车", "汽车服务",
                    "摩托车及其他", "汽车电子"],
        "description": "整车、零部件、汽车后市场产业链",
    },
]


def _get_deepseek_client():
    """复用已有 DeepSeek API 客户端"""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        providers = cfg.get("custom_providers", [])
        for p in providers:
            if p.get("name") == "deepseek-v4-flash":
                return OpenAI(api_key=p["api_key"], base_url=p["base_url"])
        return OpenAI(
            api_key=cfg.get("model", {}).get("api_key", ""),
            base_url=cfg.get("model", {}).get("base_url", "https://api.deepseek.com"),
        )
    except Exception:
        return OpenAI(api_key="", base_url="https://api.deepseek.com")


def _summarize_cycles(sectors: list) -> dict:
    """生成全市场周期总结（含前瞻预判分析）"""

    # ── 1. 各相位板块计数 ──
    phases = {}
    by_phase = {}
    for s in sectors:
        p = s["phase"]
        phases[p] = phases.get(p, 0) + 1
        by_phase.setdefault(p, []).append(s)

    summary_parts = []
    for p in ["高潮🎯", "普涨🚀", "启动🔥", "冰点反弹🌱", "筑底🏗️", "酝酿🌋",
               "分化⚡", "退潮🌊", "防御🛡️", "冰点❄️", "普跌📉", "震荡⚖️"]:
        cnt = phases.get(p, 0)
        if cnt > 0:
            summary_parts.append(f"{p} {cnt}个")
    summary = " | ".join(summary_parts) if summary_parts else "暂无数据"

    # ── 2. 市场整体判定 ──
    bullish_cnt = phases.get("普涨🚀", 0) + phases.get("启动🔥", 0)
    bearish_cnt = phases.get("冰点❄️", 0) + phases.get("普跌📉", 0) + phases.get("退潮🌊", 0)
    brewing_cnt = phases.get("酝酿🌋", 0)
    oscillation_cnt = phases.get("震荡⚖️", 0)

    if bullish_cnt > bearish_cnt + 10:
        bias = "偏多"
        bias_color = "#67c23a"
        assessment = f"市场整体偏强。{bullish_cnt}个板块处于上涨趋势（普涨+启动），" \
                     f"远超衰退方向({bearish_cnt}个)。外加{brewing_cnt}个在酝酿蓄势，上涨动能充裕。"
    elif bearish_cnt > bullish_cnt + 5:
        bias = "偏空"
        bias_color = "#409eff"
        assessment = f"市场整体偏弱。{bearish_cnt}个板块处于衰退方向（退潮+普跌+冰点），" \
                     f"多头仅{bullish_cnt}个。观望为主。"
    else:
        bias = "震荡"
        bias_color = "#909399"
        assessment = f"市场多空均衡。多头{bullish_cnt}个 vs 空头{bearish_cnt}个，" \
                     f"另有{brewing_cnt}个在酝酿、{oscillation_cnt}个在震荡。方向尚不明朗。"
    # 额外判断：震荡+酝酿数量大说明在蓄势
    if oscillation_cnt + brewing_cnt > 50 and bullish_cnt > bearish_cnt:
        assessment += " 大量板块处于震荡/酝酿区间但整体偏多，市场在积蓄力量等待催化。"
    elif oscillation_cnt + brewing_cnt > 50 and bearish_cnt > bullish_cnt:
        assessment += " 震荡/酝酿板块虽多但空头占优，短期可能继续承压。"
    if phases.get("分化⚡", 0) > 5:
        assessment += f" ⚠️ 内部分化板块{phases['分化⚡']}个，局部过热信号。"
    if phases.get("冰点❄️", 0) > 0:
        assessment += f" {phases['冰点❄️']}个板块已至冰点，超跌反弹博弈机会临近。"
    if phases.get("高潮🎯", 0) > 0:
        assessment += f" {phases['高潮🎯']}个板块情绪高潮，谨慎追高。"

    # ── 3. 各相位预判 ──
    phase_predictions = {}
    phase_flow = {
        "高潮🎯": {"next": "分化⚡", "type": "过热", "color": "#f56c6c",
                    "predict": "情绪顶点，分歧已现，建议适当减仓锁定利润，切忌追高。"},
        "普涨🚀": {"next": "高潮🎯", "type": "主升", "color": "#67c23a",
                    "predict": "上升趋势中，趋势良好可持有。若涨幅>4%则接近高潮，需警惕分化。"},
        "启动🔥": {"next": "普涨🚀", "type": "转折", "color": "#e6a23c",
                    "predict": "趋势转折确认，理论上是较好的介入时机。关注能否持续放量。"},
        "冰点反弹🌱": {"next": "筑底🏗️", "type": "反弹", "color": "#67c23a",
                    "predict": "反弹确认中，需观察能否放量突破前低。缩量反弹可能二次探底。"},
        "筑底🏗️": {"next": "酝酿🌋", "type": "筑底", "color": "#67c23a",
                    "predict": "底部确认中，缩量横盘是积极信号。等待放量突破。"},
        "酝酿🌋": {"next": "启动🔥", "type": "蓄势", "color": "#e6a23c",
                    "predict": "蓄势待发阶段，是关注和布局窗口期。关注能否放量突破。"},
        "分化⚡": {"next": "退潮🌊", "type": "分歧", "color": "#f56c6c",
                    "predict": "内部分化严重，龙头可能继续但跟风回调。聚焦前排个股，规避后排。"},
        "退潮🌊": {"next": "普跌📉", "type": "衰退", "color": "#909399",
                    "predict": "资金在撤退，短期回避为主。等待缩量企稳信号。"},
        "防御🛡️": {"next": "震荡⚖️", "type": "观望", "color": "#909399",
                    "predict": "资金避险，板块窄幅震荡。关注高股息/低估值品种。"},
        "冰点❄️": {"next": "冰点反弹🌱", "type": "触底", "color": "#409eff",
                    "predict": "深度回调，短期超卖。未来1-2日反弹概率>70%，可轻仓博弈。"},
        "普跌📉": {"next": "冰点❄️", "type": "衰退", "color": "#909399",
                    "predict": "广泛下跌但尚未到极端，可能继续寻底。等待冰点信号。"},
        "震荡⚖️": {"next": "酝酿🌋", "type": "等待", "color": "#909399",
                    "predict": "方向不明，等待催化因素。减少操作频率，择机布局。"},
    }

    for p_name, flow_info in phase_flow.items():
        items = by_phase.get(p_name, [])
        if not items:
            continue
        predict = flow_info["predict"]

        # 对特定相位做深入分析
        if p_name == "酝酿🌋":
            strong = [s for s in items if s["avg_change"] > 1.2 and s["up_pct"] > 60]
            weak = [s for s in items if s["avg_change"] < 0.7]
            if strong:
                predict += f" 较强（近启动）：{'/'.join(s['sector'] for s in strong[:5])}"
            if len(items) > 10:
                predict += f"。共{len(items)}个板块在蓄势，是最大机会群体。"

        elif p_name == "普涨🚀":
            strong = [s for s in items if s["avg_change"] > 4]
            if strong:
                predict += f" ⚠️ {'/'.join(s['sector'] for s in strong[:3])}已近高潮边界，明日警惕分化。"

        elif p_name == "震荡⚖️":
            positive = [s for s in items if s["avg_change"] > 1.5 and s["up_pct"] > 75 and s["dispersion"] < 4.5]
            hidden_brew = [s for s in items if s["avg_change"] > 2.5 and s["up_pct"] > 80]
            if hidden_brew:
                predict += f" 隐藏机遇：{'/'.join(s['sector'] for s in hidden_brew[:5])}涨幅>2.5%且上涨占比>80%，实际上已近酝酿甚至普涨。"
            if positive:
                predict += f" 偏强板块：{'/'.join(s['sector'] for s in positive[:5])}最可能率先转入酝酿阶段。"
            negative = [s for s in items if s["avg_change"] < -0.5]
            if negative:
                predict += f" 偏弱板块：{'/'.join(s['sector'] for s in negative[:3])}短期回避。"

        elif p_name == "分化⚡":
            strong = [s for s in items if s["avg_change"] > 2]
            weak = [s for s in items if s["avg_change"] < 0]
            if strong:
                predict += f" 强势分化：{'/'.join(s['sector'] for s in strong[:3])}龙头强势但分歧大。"
            if weak:
                predict += f" 弱势分化：{'/'.join(s['sector'] for s in weak[:3])}整体偏弱。"

        phase_predictions[p_name] = {
            "type": flow_info["type"],
            "next": flow_info["next"],
            "color": flow_info["color"],
            "count": len(items),
            "predict": predict,
        }

    # ── 4. 关注板块 ──
    # 酝酿中较强且近启动的
    focus_soft = []
    for s in by_phase.get("酝酿🌋", []):
        if s["avg_change"] > 1.2 and s["up_pct"] > 60:
            focus_soft.append({
                "sector": s["sector"],
                "reason": f"酝酿较强，近启动阈值（+{s['avg_change']:.2f}%，↑{s['up_pct']:.0f}%）",
            })
    # 震荡中被低估的强势板块
    focus_hidden = []
    for s in by_phase.get("震荡⚖️", []):
        if s["avg_change"] > 2.5 and s["up_pct"] > 80:
            focus_hidden.append({
                "sector": s["sector"],
                "reason": f"实际被低估，震荡中涨幅{s['avg_change']:+.2f}%↑{s['up_pct']:.0f}%",
            })
    # 冰点反弹机会
    focus_bounce = []
    for s in by_phase.get("冰点❄️", []) + by_phase.get("普跌📉", []):
        focus_bounce.append({
            "sector": s["sector"],
            "reason": f"超卖反弹机会（跌幅{s['avg_change']:+.2f}%）",
        })
    # 防御品种
    focus_defensive = []
    for s in by_phase.get("防御🛡️", []):
        if s["avg_change"] > -0.3:
            focus_defensive.append({
                "sector": s["sector"],
                "reason": f"资金避险，窄幅震荡中",
            })

    focus_sectors = {}

    if focus_soft:
        focus_sectors["重点蓄势"] = focus_soft[:8]
    if focus_hidden:
        focus_sectors["震荡低估"] = focus_hidden[:8]
    if focus_bounce:
        focus_sectors["超卖反弹"] = focus_bounce[:5]
    if focus_defensive:
        focus_sectors["避险防御"] = focus_defensive[:5]

    # ── 5. 风险警告 ──
    warnings = []
    if phases.get("分化⚡", 0) > 5:
        warnings.append({
            "level": "warning",
            "msg": f"内部分化板块达{phases['分化⚡']}个，市场缺乏强共识主线",
        })
    for s in by_phase.get("普涨🚀", []):
        if s["avg_change"] > 4:
            warnings.append({
                "level": "alert",
                "msg": f"{s['sector']}(+{s['avg_change']:.2f}%)已近高潮，谨慎追高",
            })
            break  # 只提示一次
    for s in by_phase.get("震荡⚖️", []):
        if s["avg_change"] > 3 and s["dispersion"] > 4:
            warnings.append({
                "level": "info",
                "msg": f"{s['sector']}(+{s['avg_change']:.2f}%)高涨幅高分歧(σ{s['dispersion']})，龙头已涨但后排未跟",
            })
            break
    for s in by_phase.get("普跌📉", []):
        if s["avg_change"] < -2 and s["up_pct"] < 5:
            warnings.append({
                "level": "alert",
                "msg": f"{s['sector']}(↓{s['avg_change']:.2f}%)普跌至极端，短线割肉盘涌出",
            })
            break

    if not warnings and phases.get("防御🛡️", 0) > 10:
        warnings.append({
            "level": "info",
            "msg": f"防御板块达{phases['防御🛡️']}个，资金风险偏好下降",
        })
    if not warnings:
        warnings.append({"level": "info", "msg": "市场结构健康，暂无显著风险信号"})

    # ── 6. 主题主线（8条线 + AI动态摘要） ──
    themes = []
    theme_data_for_ai = []

    for td in THEME_DEFINITIONS:
        matched = [s for s in sectors if s["sector"] in td["sectors"]]
        if len(matched) < 2:
            continue  # 至少2个行业有数据才构成主线

        avg_up = sum(s["avg_change"] for s in matched) / len(matched)
        phases_here = [s["phase"] for s in matched]
        fallback_summary = f"{td['name']}板块平均涨幅{avg_up:+.2f}%，涉及{len(matched)}个细分行业，多数处于{'/'.join(sorted(set(phases_here))[:3])}阶段"

        themes.append({
            "name": td["name"],
            "sectors": [s["sector"] for s in matched],
            "summary": fallback_summary,
            "_matched": matched,
        })

        sector_lines = []
        for s in matched:
            sector_lines.append(
                f"  {s['sector']}: 平均涨幅{s['avg_change']:+.2f}%, "
                f"上涨占比{s['up_pct']:.0f}%, 个股{s['stock_count']}只, "
                f"离散度{s['dispersion']:.1f}, 日最大涨{s['max_change']:+.2f}%, "
                f"日最大跌{s['min_change']:+.2f}%, 周期'{s.get('phase','未知')}'"
            )
        theme_data_for_ai.append({
            "name": td["name"],
            "description": td["description"],
            "sectors": "\n".join(sector_lines),
        })

    # AI 生成动态摘要（单次调用，优化速度）
    if theme_data_for_ai:
        try:
            prompt_parts = [
                "你是一位A股板块轮动分析师。以下是今日各主题线的细分行业数据。",
                "请为每条有数据的主题线写一段1-2句的行情判断摘要（50-80字），",
                "分析要点：涨跌强弱、资金共识度、个股内部分化、趋势阶段。",
                "如果是蓄势阶段就提示关注，高潮阶段提示谨慎，冰点阶段提示超跌机会。",
                "",
                '返回 JSON 格式：{"科技线":"摘要内容", "有色资源线":"摘要内容"}',
                "只返回 JSON，不要其他文字。没有数据的线不要出现在JSON里。",
                "",
            ]
            for td in theme_data_for_ai:
                prompt_parts.append(f"--- {td['name']}（{td['description']}） ---")
                prompt_parts.append(td["sectors"])
                prompt_parts.append("")

            prompt = "\n".join(prompt_parts)

            ai_client = _get_deepseek_client()
            resp = ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一位A股板块轮动分析师。返回严格JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                timeout=30,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            ai_summaries = json.loads(raw.strip())

            for theme in themes:
                name = theme["name"]
                if name in ai_summaries:
                    theme["summary"] = ai_summaries[name]
        except Exception:
            pass  # AI失败则使用备用摘要

    # 清理临时字段
    for theme in themes:
        theme.pop("_matched", None)

    return {
        "phase_distribution": phases,
        "summary": summary,
        "desc": " | ".join(summary_parts) if summary_parts else "暂无数据",
        "bias": bias,
        "bias_color": bias_color,
        "assessment": assessment,
        "phase_predictions": phase_predictions,
        "focus_sectors": focus_sectors,
        "warnings": warnings,
        "themes": themes,
    }


# -----------------------------------------------------------
# API: 板块指数（市值加权，逐日链式累加，基准1000）
# -----------------------------------------------------------

@router.post("/sector-indices/refresh")
def refresh_sector_indices_api(
    date_str: str = Query(None, alias="date"),
    full_rebuild: bool = Query(False, alias="full")
):
    """刷新板块指数数据"""
    from backend.services.tradingmgt.sector_index_service import refresh_sector_indices

    if full_rebuild:
        result = refresh_sector_indices(target_date=None)
    else:
        target = date_str or date.today().isoformat()
        result = refresh_sector_indices(target_date=target)
    return result


@router.get("/sector-indices")
def get_sector_indices_api(
    sector: str = Query(None),
    start_date: str = Query(None, alias="start"),
    end_date: str = Query(None, alias="end"),
    limit: int = Query(5000, le=10000),
):
    """查询板块指数历史（用于前端绘制走势图）"""
    from backend.services.tradingmgt.sector_index_service import get_sector_indices, get_base_date

    data = get_sector_indices(
        sector=sector,
        start_date=start_date,
        end_date=end_date,
        limit_dates=limit,
    )
    base_date = get_base_date()

    # 按板块分组
    sectors_map: dict[str, list[dict]] = {}
    for item in data:
        sec = item["sector"]
        if sec not in sectors_map:
            sectors_map[sec] = []
        sectors_map[sec].append({
            "date": item["date"],
            "index_value": item["index_value"],
            "daily_return": item["daily_return"],
        })

    return {
        "sectors": sectors_map,
        "sector_names": sorted(sectors_map.keys()),
        "base_date": base_date,
        "total_records": len(data),
    }


# -----------------------------------------------------------
# API: 自动反思（次日收盘后对比预测与实际行情）
# -----------------------------------------------------------

def _compute_prediction_direction(prediction: str, model_name: str) -> str:
    """从预测文本中提取方向：看涨/看跌/震荡"""
    p = prediction.lower()
    name = model_name.lower()

    if "均值回归" in name:
        if "回调" in p: return "看跌"
        if "反弹" in p: return "看涨"
    if "反馈回路" in name:
        if "延续趋势" in p: return "看涨"
        if "均值回归" in p: return "看跌"
    if "从众效应" in name:
        if "反转" in p: return "看跌"
        if "延续" in p: return "看涨"
    if "反脆弱" in name or "杠铃策略" in name or "黑天鹅" in name:
        return "中性"
    if any(kw in p for kw in ["回调", "回落", "下跌", "承压", "兑现", "警惕"]):
        return "看跌"
    if any(kw in p for kw in ["反弹", "上涨", "延续趋势", "延续", "走强"]):
        return "看涨"
    return "中性"


def _generate_auto_reflection(training: dict, actual_market: dict) -> dict:
    """生成自动反思：对比预测 vs 实际行情"""
    direction = _compute_prediction_direction(training.get("user_prediction", training.get("prediction", "")), training["model_name"])
    avg_chg = actual_market.get("avg_change", 0)
    up_ratio = actual_market.get("up_ratio", 50)

    if avg_chg > 0.5 and up_ratio > 55:
        actual_direction = "看涨"
    elif avg_chg < -0.5 and up_ratio < 45:
        actual_direction = "看跌"
    else:
        actual_direction = "震荡"

    if direction == actual_direction:
        accuracy = "准确"
        match_label = "✅ 方向判断准确"
    elif actual_direction == "震荡" and direction == "中性":
        accuracy = "准确"
        match_label = "✅ 震荡判断准确"
    elif direction == "中性":
        accuracy = "部分准确"
        match_label = "🟡 中性预测，实际有方向"
    else:
        accuracy = "不准确"
        match_label = "❌ 方向判断有误"

    lines = [
        f"📊 **预测回顾：{training['model_name']}**",
        "",
        f"**预测方向：** {direction}",
        f"**实际走势：** {actual_direction}（平均涨跌{avg_chg:+.2f}%，上涨占比{up_ratio}%）",
        "",
        f"**结论：** {match_label}",
        "",
    ]

    if accuracy == "准确":
        if direction == "看涨":
            lines.append("预测看涨，实际上涨确认。市场按预期方向运行，模型逻辑有效。")
            lines.append("💡 **反思提示：** 当预测被验证准确时，问自己——这是模型的洞察力还是运气？")
        elif direction == "看跌":
            lines.append("预测回调，实际下跌确认。风险预判正确。")
            lines.append("💡 **反思提示：** 准确预判风险和准确预判机会同样重要。这次风险信号的触发条件是什么？")
        else:
            lines.append("预测震荡/中性，实际市场波动有限，方向不明。")
            lines.append("💡 **反思提示：** 震荡市场中「不做判断」本身就是正确的判断。")
    elif accuracy == "部分准确":
        lines.append("预测中性但市场走出了方向，或预测有方向但市场震荡。")
        lines.append("💡 **反思提示：** 是否有突发消息、资金异动或政策变化被忽略？")
    else:
        if direction == "看涨":
            lines.append("预测上涨但实际下跌，模型信号失效。")
        elif direction == "看跌":
            lines.append("预测下跌但实际上涨，风险预判失误。")
        else:
            lines.append("预测中性/震荡但市场走出明显方向。")
        lines.append("💡 **反思提示：** ①模型不适用当前环境？②数据不完整？③忽略关键变量？记下教训！")

    lines.extend([
        "",
        f"**今日市场概况：**",
        f"- 全市场平均涨跌：{avg_chg:+.2f}%",
        f"- 上涨/下跌：{actual_market.get('up', '?')}/{actual_market.get('down', '?')}",
        f"- 涨跌比：{up_ratio}%",
        f"- 日内最强：{actual_market.get('max_up', '?'):+.2f}%",
        f"- 日内最弱：{actual_market.get('max_down', '?'):+.2f}%",
    ])

    return {
        "accuracy": accuracy,
        "next_day_result": f"实际走势{direction}（涨跌{avg_chg:+.2f}%，上涨占比{up_ratio}%）",
        "reflection": "\n".join(lines),
    }


@router.post("/daily-training/auto-reflect")
def auto_reflect_all():
    """自动反思：用今日行情对比昨日预测，生成反思报告"""
    today = date.today().isoformat()
    today_dt = date.fromisoformat(today)
    yesterday = (today_dt - timedelta(days=1)).isoformat()

    conn = get_db()
    yesterday_rows = conn.execute(
        "SELECT * FROM model_trainings WHERE training_date = ? AND user_prediction != ''",
        (yesterday,)
    ).fetchall()

    if not yesterday_rows:
        conn.close()
        return {
            "date": today, "yesterday": yesterday, "reflected": 0,
            "message": f"{yesterday} 无待反思的训练记录",
        }

    from backend.routers.market import _load_csv
    df = _load_csv(today, "close")
    if df is None:
        df = _load_csv(today, "noon")
    if df is None:
        conn.close()
        return {"date": today, "yesterday": yesterday, "reflected": 0, "message": f"{today} 无行情数据"}

    valid = df[df["change_pct"].notna()]
    market_summary = {
        "total": len(valid),
        "up": int((valid["change_pct"] > 0).sum()),
        "down": int((valid["change_pct"] < 0).sum()),
        "avg_change": round(float(valid["change_pct"].mean()), 2),
        "max_up": round(float(valid["change_pct"].max()), 2),
        "max_down": round(float(valid["change_pct"].min()), 2),
        "up_ratio": round(int((valid["change_pct"] > 0).sum()) / len(valid) * 100, 1),
    }

    reflected_count = 0
    results = []
    for row in yesterday_rows:
        training = dict(row)
        if training.get("reflection"):
            continue
        ref_data = _generate_auto_reflection(training, market_summary)
        conn.execute(
            "UPDATE model_trainings SET next_day_result = ?, accuracy = ?, reflection = ? WHERE id = ?",
            (ref_data["next_day_result"], ref_data["accuracy"], ref_data["reflection"], training["id"])
        )
        reflected_count += 1
        results.append({"id": training["id"], "model_name": training["model_name"], "accuracy": ref_data["accuracy"]})

    conn.commit()
    conn.close()
    return {
        "date": today, "yesterday": yesterday, "reflected": reflected_count,
        "market_summary": market_summary, "results": results,
        "message": f"已对 {reflected_count} 条昨日训练记录完成自动反思",
    }


@router.get("/stock-sector")
def get_stock_sector(code: str = Query(...), date_str: str = Query(None, alias="date")):
    """查询个股所属行业板块及主题线"""
    from backend.routers.market import _load_csv

    df = _load_csv(date_str, "close")
    if df is None:
        date_str = date_str or date.today().isoformat()
        # 尝试午盘
        df = _load_csv(date_str, "noon")
    if df is None:
        return {"error": "无可用行情数据"}, 404

    if "code" not in df.columns:
        return {"error": "数据格式错误"}, 500

    # 查找股票
    match = df[df["code"].astype(str).str.strip() == str(code).strip()]
    if match.empty:
        match = df[df["code"].astype(str).str.strip().str.zfill(6) == str(code).strip().zfill(6)]
    if match.empty:
        return {"error": f"未找到代码 {code}"}, 404

    row = match.iloc[0]
    sector = str(row.get("sector", "") or "")
    name = str(row.get("name", "") or "")

    # 查主题线
    theme = ""
    for td in THEME_DEFINITIONS:
        if sector in td["sectors"]:
            theme = td["name"]
            break

    return {
        "code": str(code).strip().zfill(6),
        "name": name,
        "sector": sector,
        "theme": theme,
    }
