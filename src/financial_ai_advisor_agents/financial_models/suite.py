from pathlib import Path

import numpy as np

from financial_ai_advisor_agents.financial_models.schemas import FundamentalReport, Security, SecurityScore
from financial_ai_advisor_agents.financial_models.universe import SecurityUniverse


NORMALIZATION_RULES = {
    "cross_section": "min-max to [0, 100]; constant columns score 50; lower PE/PB/debt is better",
    "valuation": "60% inverse-PE score + 40% inverse-PB score; non-positive PE/PB scores 0",
    "quality": "40% gross margin + 35% EPS + 25% inverse debt ratio",
    "technical": "30% RSI + 30% MA trend + 25% MACD + 15% Bollinger position",
    "dividend": "cross-sectional min-max of dividend yield",
    "total": "30% valuation + 30% quality + 25% technical + 15% dividend",
}


def _min_max(values: list[float], inverse: bool = False, non_positive_zero: bool = False) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    low = float(array.min())
    high = float(array.max())
    scores = np.full(array.shape, 50.0) if high == low else (array - low) / (high - low) * 100.0
    if inverse:
        scores = 100.0 - scores
    if non_positive_zero:
        scores = np.where(array <= 0, 0.0, scores)
    return np.clip(scores, 0.0, 100.0)


class FinancialModelSuite:
    def __init__(self, csv_path: Path) -> None:
        self.universe = SecurityUniverse(csv_path)
        self.normalization_rules = dict(NORMALIZATION_RULES)

    def score_securities(self) -> list[SecurityScore]:
        securities = self.universe.load()
        pe_scores = _min_max([s.pe_ratio for s in securities], inverse=True, non_positive_zero=True)
        pb_scores = _min_max([s.pb_ratio for s in securities], inverse=True, non_positive_zero=True)
        margin_scores = _min_max([s.gross_margin for s in securities])
        eps_scores = _min_max([s.eps for s in securities])
        debt_scores = _min_max([s.debt_ratio for s in securities], inverse=True)
        dividend_scores = _min_max([s.dividend_yield for s in securities])

        scores: list[SecurityScore] = []
        for index, security in enumerate(securities):
            rsi_score = float(np.clip(100.0 - abs(security.rsi_14 - 50.0) * 2.5, 0.0, 100.0))
            trend_score = {"BULLISH": 100.0, "NEUTRAL": 50.0, "BEARISH": 0.0}.get(security.ma_trend, 50.0)
            macd_score = {"GOLDEN_CROSS": 100.0, "NEUTRAL": 50.0, "DEAD_CROSS": 0.0}.get(security.macd_signal, 50.0)
            boll_width = security.boll_upper - security.boll_lower
            boll_score = 50.0 if boll_width <= 0 else float(
                np.clip((security.close - security.boll_lower) / boll_width * 100.0, 0.0, 100.0)
            )
            valuation = 0.60 * pe_scores[index] + 0.40 * pb_scores[index]
            quality = 0.40 * margin_scores[index] + 0.35 * eps_scores[index] + 0.25 * debt_scores[index]
            technical = 0.30 * rsi_score + 0.30 * trend_score + 0.25 * macd_score + 0.15 * boll_score
            dividend = dividend_scores[index]
            total = 0.30 * valuation + 0.30 * quality + 0.25 * technical + 0.15 * dividend
            scores.append(
                SecurityScore(
                    symbol=security.symbol,
                    name=security.name,
                    sector=security.sector,
                    total_score=round(float(total), 6),
                    valuation_score=round(float(valuation), 6),
                    quality_score=round(float(quality), 6),
                    technical_score=round(float(technical), 6),
                    dividend_score=round(float(dividend), 6),
                    components={
                        "pe": round(float(pe_scores[index]), 6),
                        "pb": round(float(pb_scores[index]), 6),
                        "gross_margin": round(float(margin_scores[index]), 6),
                        "eps": round(float(eps_scores[index]), 6),
                        "debt": round(float(debt_scores[index]), 6),
                        "rsi": round(rsi_score, 6),
                        "ma_trend": trend_score,
                        "macd": macd_score,
                        "bollinger": round(boll_score, 6),
                    },
                )
            )
        return sorted(scores, key=lambda score: (-score.total_score, score.symbol))

    def fundamental(self, symbol: str) -> FundamentalReport:
        security = self.universe.get(symbol)
        score = next(item for item in self.score_securities() if item.symbol == security.symbol)
        flags = self._risk_flags(security)
        valuation = "估值指标高于 30 倍 PE 阈值" if security.pe_ratio > 30 else "估值指标未触发 30 倍 PE 阈值"
        summary = (
            f"{security.name}（{security.symbol}）综合分 {score.total_score:.2f}/100；"
            f"毛利率 {security.gross_margin:.2f}%，负债率 {security.debt_ratio:.2f}%，{valuation}。"
        )
        return FundamentalReport(
            **security.model_dump(exclude={"boll_upper", "boll_middle", "boll_lower"}),
            score=score,
            risk_flags=flags,
            summary=summary,
            assumptions=[
                "报告完全由本地虚构 CSV 字段和横截面归一化规则计算。",
                "分数用于相对比较，不是评级、投资建议或未来收益预测。",
            ],
        )

    @staticmethod
    def _risk_flags(security: Security) -> list[str]:
        flags: list[str] = []
        if security.debt_ratio > 70:
            flags.append(f"负债率 {security.debt_ratio:.1f}% 高于 70%")
        if security.gross_margin < 20:
            flags.append(f"毛利率 {security.gross_margin:.1f}% 低于 20%")
        if security.eps < 0:
            flags.append("EPS 为负")
        if security.pe_ratio < 0:
            flags.append("PE 为负，估值分数按 0 处理")
        elif security.pe_ratio > 30:
            flags.append(f"PE {security.pe_ratio:.1f} 高于 30 倍")
        if security.pb_ratio > 5:
            flags.append(f"PB {security.pb_ratio:.1f} 高于 5 倍")
        if security.rsi_14 > 70:
            flags.append(f"RSI {security.rsi_14:.1f} 高于 70，存在超买风险")
        elif security.rsi_14 < 30:
            flags.append(f"RSI {security.rsi_14:.1f} 低于 30，存在弱势或超卖风险")
        if security.ma_trend == "BEARISH":
            flags.append("均线趋势为 BEARISH")
        if security.macd_signal == "DEAD_CROSS":
            flags.append("MACD 为 DEAD_CROSS")
        if security.close > security.boll_upper or security.close < security.boll_lower:
            flags.append("收盘价超出布林带上下轨")
        return flags
