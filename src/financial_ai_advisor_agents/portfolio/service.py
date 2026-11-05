import json
from pathlib import Path
from typing import Any

import numpy as np

from financial_ai_advisor_agents.schemas.portfolio import (
    AttributionItem,
    HoldingAnalysis,
    Portfolio,
    PortfolioAnalysis,
    SectorAllocation,
)
from financial_ai_advisor_agents.portfolio.ocr import PaddleOCREngine, extract_ocr_lines, parse_ocr_lines
from financial_ai_advisor_agents.portfolio.optimization import optimize_portfolio
from financial_ai_advisor_agents.portfolio.risk import calculate_risk


class PortfolioService:
    def __init__(
        self,
        sample_path: Path,
        ocr_engine: Any | None = None,
        max_weight: float = 0.35,
        cash_min: float = 0.05,
    ) -> None:
        self.sample_path = Path(sample_path)
        self.ocr_engine = ocr_engine
        self.max_weight = max_weight
        self.cash_min = cash_min

    def load_sample(self) -> Portfolio:
        with self.sample_path.open("r", encoding="utf-8") as source:
            return Portfolio.model_validate(json.load(source))

    def analyze_sample(self) -> PortfolioAnalysis:
        analysis = self.analyze(self.load_sample())
        assumptions = ["内置 JSON 为虚构样例，未经过 OCR，也不代表真实账户或行情。"]
        return analysis.model_copy(update={"assumptions": assumptions + analysis.assumptions})

    def analyze_image(self, content: bytes, filename: str) -> PortfolioAnalysis:
        if not content:
            raise ValueError("image content must not be empty")
        engine = self.ocr_engine
        if engine is None:
            engine = PaddleOCREngine()
        lines = extract_ocr_lines(engine, content, filename)
        holdings = parse_ocr_lines(lines)
        portfolio = Portfolio(
            holdings=holdings,
            benchmark_return=0.0,
            benchmark_history=[0.0] * len(holdings[0].return_history),
        )
        analysis = self.analyze(portfolio)
        assumptions = [
            "图片结果来自所配置的 OCR 引擎，证券名称和数值需人工核对。",
            "OCR 未提供历史序列，12 期零收益仅用于占位；基准设为 0，不代表真实历史表现。",
        ]
        return analysis.model_copy(update={"assumptions": assumptions + analysis.assumptions})

    def analyze(self, portfolio: Portfolio) -> PortfolioAnalysis:
        market_values = np.array([h.quantity * h.current_price for h in portfolio.holdings], dtype=float)
        total_value = float(market_values.sum())
        if total_value <= 0:
            raise ValueError("portfolio market value must be positive")
        weights = market_values / total_value
        returns = np.array([h.period_return for h in portfolio.holdings], dtype=float)
        contributions = weights * returns
        total_return = float(contributions.sum())
        active_contributions = weights * (returns - portfolio.benchmark_return)

        holding_rows = [
            HoldingAnalysis(
                symbol=holding.symbol,
                name=holding.name,
                sector=holding.sector,
                weight=float(weight),
                period_return=holding.period_return,
                contribution=float(contribution),
                market_value=float(market_value),
                unrealized_pnl=float((holding.current_price - holding.cost_price) * holding.quantity),
                signal="强势" if holding.period_return > 0.05 else "弱势" if holding.period_return < -0.05 else "中性",
            )
            for holding, weight, contribution, market_value in zip(
                portfolio.holdings, weights, contributions, market_values
            )
        ]
        sector_totals: dict[str, float] = {}
        for holding, weight in zip(portfolio.holdings, weights):
            sector_totals[holding.sector] = sector_totals.get(holding.sector, 0.0) + float(weight)
        sectors = [
            SectorAllocation(sector=sector, weight=weight)
            for sector, weight in sorted(sector_totals.items(), key=lambda item: (-item[1], item[0]))
        ]
        history = np.array([holding.return_history for holding in portfolio.holdings], dtype=float)
        portfolio_returns = weights.dot(history)
        risk = calculate_risk(
            portfolio_returns,
            weights,
            [sector.weight for sector in sectors],
        )
        attribution = [
            AttributionItem(
                symbol=holding.symbol,
                contribution=float(contribution),
                active_contribution=float(active_contribution),
            )
            for holding, contribution, active_contribution in zip(
                portfolio.holdings, contributions, active_contributions
            )
        ]
        optimization = optimize_portfolio(
            portfolio,
            max_weight=max(self.max_weight, 1.0 / len(portfolio.holdings)),
            cash_min=self.cash_min,
        )
        diagnoses = self._diagnose(portfolio, risk.score, risk, total_return)
        return PortfolioAnalysis(
            portfolio=portfolio,
            holdings=holding_rows,
            sectors=sectors,
            risk=risk,
            attribution=attribution,
            total_return=total_return,
            benchmark_return=portfolio.benchmark_return,
            active_return=total_return - portfolio.benchmark_return,
            total_value=total_value,
            total_pnl=float(sum(row.unrealized_pnl for row in holding_rows)),
            diagnoses=diagnoses,
            optimization=optimization,
            assumptions=[
                "所有数据仅用于虚构演示，不构成真实行情、投资建议或收益承诺。",
                "贡献 = 当前市值权重 × 持有期收益率；主动贡献 = 权重 ×（个券持有期收益率 - 基准收益率），不是多期 Brinson 归因。",
                "收益率序列按月度观测并以 12 期年化；历史 VaR95 是组合序列 5% 分位对应的非负损失。",
                "优化以持有期收益率为期望收益、月度历史协方差的 12 期年化为风险，采用有界单纯形投影梯度法。",
            ],
        )

    @staticmethod
    def _diagnose(portfolio: Portfolio, score: float, risk: Any, total_return: float) -> list[str]:
        diagnoses: list[str] = []
        if risk.max_weight > 0.30:
            diagnoses.append(f"最大标的权重 {risk.max_weight:.1%} 超过 30%，存在单券集中风险。")
        if risk.max_sector_weight > 0.40:
            diagnoses.append(f"最大行业权重 {risk.max_sector_weight:.1%} 超过 40%，存在行业集中风险。")
        if risk.hhi > 0.25:
            diagnoses.append(f"HHI 为 {risk.hhi:.3f}，超过 0.25 的集中度阈值。")
        if risk.annualized_volatility > 0.25:
            diagnoses.append(f"年化波动率 {risk.annualized_volatility:.1%} 超过 25%。")
        if risk.max_drawdown > 0.20:
            diagnoses.append(f"累计序列最大回撤 {risk.max_drawdown:.1%} 超过 20%。")
        if risk.var_95 > 0.05:
            diagnoses.append(f"历史 VaR95 为 {risk.var_95:.1%}，超过 5%。")
        if total_return < portfolio.benchmark_return:
            diagnoses.append("组合持有期收益低于基准；该算术归因不代表多期 Brinson 结果。")
        if score >= 75:
            diagnoses.append("综合风险分达到极高区间，应优先复核集中度和历史损失指标。")
        return diagnoses
