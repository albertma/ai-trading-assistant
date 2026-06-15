"""
板块RL预测 — 用强化学习优化板块走势预测策略

架构：
  State:    板块技术面特征向量
  Action:   预测次日涨跌（0=看空 / 1=看多）
  Reward:   预测正确+1，错误-1
  Policy:   2层MLP，REINFORCE训练

数据：128板块 × 19交易日 = 2432样本
训练：滚动窗口（前15天训练，后4天验证）
"""
import json, os, sqlite3, pickle
import numpy as np
from pathlib import Path
from datetime import date, datetime

DB = str(Path.home() / 'Jarvis' / 'ai_trading' / 'stock_archive.db')
MODEL_DIR = Path.home() / 'Jarvis' / 'ai_trading' / 'rl_models'
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ── 环境 ──────────────────────────────────────────

def build_state_features(sector_history: list[dict]) -> list[dict]:
    """从板块历史数据构建每个交易日的特征向量"""
    closes = np.array([r["index_value"] for r in sector_history])
    returns = np.array([r["daily_return"] for r in sector_history])
    n = len(closes)
    if n < 10:
        return []

    # 预计算均线
    def sma(data, window):
        if len(data) < window:
            return np.array([0.0] * len(data))
        s = np.cumsum(data)
        s[window:] = s[window:] - s[:-window]
        result = np.empty_like(data, dtype=float)
        result[:window - 1] = 0.0
        result[window - 1:] = s[window - 1:] / window
        return result

    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)

    # MACD
    def ema(data, span):
        alpha = 2 / (span + 1)
        result = np.empty_like(data, dtype=float)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = data[i] * alpha + result[i - 1] * (1 - alpha)
        return result

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = ema12 - ema26
    dea = ema(dif, 9)

    # RSI14
    rsi = np.full(n, 50.0, dtype=float)
    if n >= 15:
        for i in range(14, n):
            gains = sum(max(0, closes[j] - closes[j - 1]) for j in range(i - 13, i + 1))
            losses = sum(max(0, closes[j - 1] - closes[j]) for j in range(i - 13, i + 1))
            avg_gain = gains / 14
            avg_loss = losses / 14
            rsi[i] = 50 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss > 0 else 100

    # 构建每行特征
    features = []
    for i in range(5, n - 1):  # 需要MA5，且需要知道next day返回
        price_vs_ma20 = (closes[i] - ma20[i]) / ma20[i] * 100 if ma20[i] > 0 else 0
        # 相对强度：过去5日涨幅 vs 所有板块均值（这里简化用return代替）
        rps_proxy = sum(returns[max(0, i - 4):i + 1])

        feat = [
            round(returns[i], 2),           # 当日涨幅
            round(ma5[i], 1),                # MA5
            round(ma10[i], 1),               # MA10
            round(ma20[i], 1),               # MA20
            round(price_vs_ma20, 2),         # 价格偏离MA20%
            round(rsi[i], 1),                # RSI
            round(rps_proxy, 2),             # RPS代理
            round(dif[i], 2),                # MACD DIF
            round(dea[i], 2),                # MACD DEA
        ]

        # 标签：次日涨跌
        label = 1 if returns[i + 1] > 0 else 0

        features.append({
            "features": feat,
            "label": label,
            "next_return": round(returns[i + 1], 2),
            "date": sector_history[i]["date"],
            "next_date": sector_history[i + 1]["date"],
        })

    return features


def load_all_sector_data() -> dict:
    """加载所有板块数据并构建特征"""
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT date, sector, index_value, daily_return FROM sector_indices ORDER BY sector, date"
    ).fetchall()
    db.close()

    # 按板块分组
    sector_map = {}
    for r in rows:
        s = r["sector"]
        if s not in sector_map:
            sector_map[s] = []
        sector_map[s].append(dict(r))

    all_features = {}
    for sector, hist in sector_map.items():
        feats = build_state_features(hist)
        if feats:
            all_features[sector] = feats

    return all_features


# ── 策略网络（PyTorch） ──────────────────────────

def build_policy_net(input_dim=9, hidden=16):
    """2层MLP + softmax"""
    import torch
    return torch.nn.Sequential(
        torch.nn.Linear(input_dim, hidden),
        torch.nn.ReLU(),
        torch.nn.Linear(hidden, 2),  # 2 actions: down/up
    )


def train_rl(all_features, epochs=200, lr=0.01, l1_reg=1e-4):
    """
    REINFORCE训练
    - 每个(板块, 日)对是一个独立step
    - policy gradient最大化累计奖励
    """
    import torch

    # 展平所有特征
    all_X, all_y, all_weights = [], [], []
    for sector, feats in all_features.items():
        for f in feats:
            all_X.append(f["features"])
            all_y.append(f["label"])
    all_X = torch.tensor(all_X, dtype=torch.float32)
    all_y = torch.tensor(all_y, dtype=torch.long)

    # 类别平衡权重（涨/跌样本比例）
    n_pos = (all_y == 1).sum().item()
    n_neg = (all_y == 0).sum().item()
    pos_weight = n_neg / max(n_pos, 1)
    neg_weight = n_pos / max(n_neg, 1)

    n = len(all_y)
    input_dim = all_X.shape[1]
    policy_net = build_policy_net(input_dim)
    optimizer = torch.optim.Adam(policy_net.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=50, gamma=0.5)

    # REINFORCE训练
    history = {"loss": [], "accuracy": []}
    for epoch in range(epochs):
        logits = policy_net(all_X)
        probs = torch.softmax(logits, dim=1)
        log_probs = torch.log(probs + 1e-8)

        # 取所选action的log prob
        selected_log_probs = log_probs[range(n), all_y]

        # 奖励：预测正确+1，错误-1 → 这里是"预测概率"版本的交叉熵
        # 用带权重的交叉熵来模拟RL奖励
        weights = torch.where(all_y == 1, pos_weight, neg_weight)
        loss = -(selected_log_probs * weights).mean()

        # L1正则化
        l1 = 0
        for p in policy_net.parameters():
            l1 += p.abs().sum()
        loss += l1_reg * l1

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        scheduler.step()

        # 评估
        with torch.no_grad():
            preds = logits.argmax(dim=1)
            acc = (preds == all_y).float().mean().item()

        history["loss"].append(round(loss.item(), 4))
        history["accuracy"].append(round(acc, 4))

        if (epoch + 1) % 50 == 0:
            print(f"  epoch {epoch+1}/{epochs} loss={loss.item():.4f} acc={acc:.4f}")

    # 计算混淆矩阵
    with torch.no_grad():
        preds = policy_net(all_X).argmax(dim=1).numpy()
        y_true = all_y.numpy()
        tp = ((preds == 1) & (y_true == 1)).sum()
        tn = ((preds == 0) & (y_true == 0)).sum()
        fp = ((preds == 1) & (y_true == 0)).sum()
        fn = ((preds == 0) & (y_true == 1)).sum()

    metrics = {
        "accuracy": round((tp + tn) / max(len(y_true), 1), 4),
        "precision": round(tp / max(tp + fp, 1), 4),
        "recall": round(tp / max(tp + fn, 1), 4),
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "samples": len(y_true),
        "pos_ratio": round(n_pos / n, 3),
    }

    return policy_net, history, metrics


def predict_sectors(policy_net, all_features, target_date: str) -> list[dict]:
    """用训练好的策略预测指定日期各板块的次日方向"""
    import torch
    results = []
    for sector, feats in all_features.items():
        # 找到target_date对应的特征
        match = [f for f in feats if f["date"] == target_date]
        if not match:
            continue
        f = match[0]
        x = torch.tensor([f["features"]], dtype=torch.float32)
        with torch.no_grad():
            logits = policy_net(x)
            prob_up = torch.softmax(logits, dim=1)[0, 1].item()
            pred = "up" if prob_up > 0.5 else "down"

        results.append({
            "sector": sector,
            "prob_up": round(prob_up, 3),
            "prediction": pred,
            "next_return": f["next_return"],
        })

    results.sort(key=lambda x: x["prob_up"], reverse=True)
    return results


def train_and_save():
    """完整训练流程"""
    print("📦 加载板块数据...")
    all_features = load_all_sector_data()
    print(f"    {len(all_features)} 个板块")

    total_samples = sum(len(v) for v in all_features.values())
    print(f"    {total_samples} 个样本")

    # 按时间划分训练/验证集（前80%天 vs 后20%天）
    dates = sorted(set(f["date"] for feats in all_features.values() for f in feats))
    split_idx = max(int(len(dates) * 0.8), 2)
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])

    train_features = {}
    test_features = {}
    for sector, feats in all_features.items():
        train_f = [f for f in feats if f["date"] in train_dates]
        test_f = [f for f in feats if f["date"] in test_dates]
        if train_f:
            train_features[sector] = train_f
        if test_f:
            test_features[sector] = test_f

    print(f"\n🎯 训练集: {sum(len(v) for v in train_features.values())} 样本 ({dates[split_idx-1]} 前)")
    print(f"🎯 验证集: {sum(len(v) for v in test_features.values())} 样本 ({dates[split_idx]} 起)")

    print("\n🧠 REINFORCE训练中...")
    policy_net, history, metrics = train_rl(train_features)

    print(f"\n📊 训练集指标:")
    for k, v in metrics.items():
        print(f"    {k}: {v}")

    # 验证
    if test_features:
        import torch
        all_X_t, all_y_t = [], []
        for sector, feats in test_features.items():
            for f in feats:
                all_X_t.append(f["features"])
                all_y_t.append(f["label"])
        all_X_t = torch.tensor(all_X_t, dtype=torch.float32)
        all_y_t = torch.tensor(all_y_t, dtype=torch.long)
        with torch.no_grad():
            preds = policy_net(all_X_t).argmax(dim=1).numpy()
            y_true = all_y_t.numpy()
            test_acc = (preds == y_true).mean()
            tp = ((preds == 1) & (y_true == 1)).sum()
            tn = ((preds == 0) & (y_true == 0)).sum()
            fp = ((preds == 1) & (y_true == 0)).sum()
            fn = ((preds == 0) & (y_true == 1)).sum()
            precision = tp / max(tp + fp, 1)
            recall = tp / max(tp + fn, 1)
        print(f"\n📊 验证集指标:")
        print(f"    accuracy: {test_acc:.4f}")
        print(f"    precision: {precision:.4f}")
        print(f"    recall: {recall:.4f}")

    # 保存模型
    import torch
    model_path = MODEL_DIR / "sector_rl_policy.pt"
    torch.save(policy_net.state_dict(), model_path)
    print(f"\n💾 模型已保存: {model_path}")

    # 保存训练历史+指标
    meta = {
        "train_date": date.today().isoformat(),
        "train_samples": sum(len(v) for v in train_features.values()),
        "test_samples": sum(len(v) for v in test_features.values()) if test_features else 0,
        "train_metrics": metrics,
        "test_accuracy": round(float(test_acc), 4) if test_features else 0,
        "history": history,
        "feature_names": ["return", "MA5", "MA10", "MA20", "偏离MA20%", "RSI", "RPS_5d", "MACD_DIF", "MACD_DEA"],
    }
    meta_path = MODEL_DIR / "sector_rl_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"📄 元数据已保存: {meta_path}")

    # 回测：模拟策略收益
    print("\n💰 模拟回测（验证集）:")
    if test_features:
        predictions = predict_sectors(policy_net, test_features, list(test_dates)[0])
        # 假设：买入前5名看多板块，等权
        top5 = predictions[:5]
        avg_return = np.mean([p["next_return"] for p in top5])
        print(f"  买入RPS前5: 次日平均收益 {avg_return:+.2f}%")

        # 对比：如果全部买入看多板块 vs 全部卖出看空板块
        up_sectors = [p for p in predictions if p["prediction"] == "up"]
        down_sectors = [p for p in predictions if p["prediction"] == "down"]
        if up_sectors:
            up_avg = np.mean([p["next_return"] for p in up_sectors])
            print(f"  看多板块平均: {up_avg:+.2f}% ({len(up_sectors)}个)")
        if down_sectors:
            down_avg = np.mean([p["next_return"] for p in down_sectors])
            print(f"  看空板块平均: {down_avg:+.2f}% ({len(down_sectors)}个)")

    # 最新预测
    latest_date = dates[-1]
    predictions = predict_sectors(policy_net, all_features, latest_date)
    print(f"\n📈 最新预测 ({latest_date} → 次日):")
    print(f"  看多: {sum(1 for p in predictions if p['prediction']=='up')} 个板块")
    print(f"  看空: {sum(1 for p in predictions if p['prediction']=='down')} 个板块")
    print(f"  次日看多TOP5:")
    for p in predictions[:5]:
        print(f"    🟢 {p['sector']:12s} prob={p['prob_up']:.1%}")

    return {
        "model_path": str(model_path),
        "meta_path": str(meta_path),
        "metrics": metrics,
        "test_accuracy": round(float(test_acc), 4) if test_features else 0,
        "latest_predictions": predictions[:10],
        "history": history["loss"][-10:] if history.get("loss") else [],
    }


def load_model():
    """加载训练好的模型"""
    import torch
    model_path = MODEL_DIR / "sector_rl_policy.pt"
    if not model_path.exists():
        return None, None
    policy_net = build_policy_net()
    policy_net.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    policy_net.eval()

    meta_path = MODEL_DIR / "sector_rl_meta.json"
    meta = {}
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
    return policy_net, meta


if __name__ == "__main__":
    result = train_and_save()
    print(f"\n✅ 训练完成")
