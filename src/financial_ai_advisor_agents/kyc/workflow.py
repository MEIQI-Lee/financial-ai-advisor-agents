from typing import Any

from financial_ai_advisor_agents.memory.store import MemoryStore
from financial_ai_advisor_agents.schemas.kyc import KYCOption, KYCQuestion, KYCState, MarketEnvironment


KYC_QUESTIONS = (
    KYCQuestion(
        id="investment_experience",
        title="你的投资经验是？",
        options=[
            KYCOption(value="none", label="没有投资经验", score=1),
            KYCOption(value="under_3_years", label="3年以内", score=2),
            KYCOption(value="3_to_5_years", label="3至5年", score=3),
            KYCOption(value="over_5_years", label="5年以上", score=4),
            KYCOption(value="professional", label="具备专业投资经验", score=5),
        ],
    ),
    KYCQuestion(
        id="loss_reaction",
        title="如果持仓在一个月内下跌10%，你会怎么做？",
        options=[
            KYCOption(value="sell_all", label="全部卖出以避免继续下跌", score=1),
            KYCOption(value="sell_part", label="卖出一部分以降低波动", score=2),
            KYCOption(value="hold", label="保持持仓并继续观察", score=3),
            KYCOption(value="buy_small", label="小幅分批买入", score=4),
            KYCOption(value="buy_more", label="积极买入以摊低成本", score=5),
        ],
    ),
    KYCQuestion(
        id="fixed_expense_destination",
        title="你的主要固定支出流向是？",
        options=[
            KYCOption(value="basic_living", label="基本生活开销", score=2),
            KYCOption(value="housing_loan", label="住房或长期贷款", score=2),
            KYCOption(value="education_eldercare", label="教育或赡养支出", score=1),
            KYCOption(value="insurance_savings", label="保障型保险或长期储蓄", score=4),
        ],
    ),
    KYCQuestion(
        id="fixed_expense_ratio",
        title="固定支出约占你月收入的比例是？",
        options=[
            KYCOption(value="under_20", label="低于20%", score=5),
            KYCOption(value="20_to_40", label="20%至40%", score=4),
            KYCOption(value="40_to_60", label="40%至60%", score=2),
            KYCOption(value="over_60", label="高于60%", score=1),
        ],
    ),
    KYCQuestion(
        id="investment_horizon",
        title="这笔资金计划投资多长时间？",
        options=[
            KYCOption(value="under_1_year", label="1年以内", score=1),
            KYCOption(value="1_to_3_years", label="1至3年", score=2),
            KYCOption(value="3_to_5_years", label="3至5年", score=3),
            KYCOption(value="5_to_10_years", label="5至10年", score=4),
            KYCOption(value="over_10_years", label="10年以上", score=5),
        ],
    ),
)

_HORIZON_ADJUSTMENTS = {
    "under_1_year": -20,
    "1_to_3_years": -10,
    "3_to_5_years": 0,
    "5_to_10_years": 5,
    "over_10_years": 10,
}
_EXPENSE_ADJUSTMENTS = {
    "under_20": 0,
    "20_to_40": -5,
    "40_to_60": -15,
    "over_60": -25,
}
KYC_MARKET_ENVIRONMENT = {
    "economic_cycle": "虚构弱复苏情景，仅用于规则演示",
    "market_interest_rate": "虚构中性利率情景，非实时利率",
    "policies_and_regulations": "未接入政策资讯，不生成实时政策判断",
}


class KYCWorkflow:
    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def start(self, user_id: str) -> KYCState:
        self.memory.update_profile(
            user_id,
            {"kyc": {"step": 0, "answers": {}, "completed": False}},
        )
        return self.status(user_id)

    def answer(self, user_id: str, question_id: str, value: str) -> KYCState:
        profile = self.memory.context(user_id).profile
        if not isinstance(profile.get("kyc"), dict):
            raise ValueError("KYC 尚未开始，请先调用 start")
        state = self._state_from_profile(user_id, profile)
        if state.completed:
            raise ValueError("KYC 已完成；如需修改，请重新开始")
        expected = KYC_QUESTIONS[state.step]
        if question_id != expected.id:
            raise ValueError(f"题目顺序或问题ID错误，当前应回答 {expected.id}")
        option = next((item for item in expected.options if item.value == value), None)
        if option is None:
            raise ValueError(f"选项 {value!r} 不属于问题 {question_id}")

        answers = dict(state.answers)
        answers[question_id] = value
        step = state.step + 1
        completed = step == len(KYC_QUESTIONS)
        payload: dict[str, Any] = {
            "step": step,
            "answers": answers,
            "completed": completed,
        }
        if completed:
            risk_score = self._calculate_risk_score(answers)
            risk_level = self._risk_level(risk_score)
            allocation, explanation = self._calculate_allocation(
                risk_score,
                risk_level,
                answers["investment_horizon"],
                answers["fixed_expense_ratio"],
            )
            payload.update(
                {
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "allocation": allocation,
                    "allocation_explanation": explanation,
                    "market_environment": dict(KYC_MARKET_ENVIRONMENT),
                    "profile": {
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "investment_horizon": answers["investment_horizon"],
                        "fixed_expense_ratio": answers["fixed_expense_ratio"],
                    },
                }
            )
        self.memory.update_profile(user_id, {"kyc": payload})
        return self.status(user_id)

    def status(self, user_id: str) -> KYCState:
        return self._state_from_profile(user_id, self.memory.context(user_id).profile)

    @staticmethod
    def _state_from_profile(user_id: str, profile: dict[str, Any]) -> KYCState:
        raw = profile.get("kyc")
        if not isinstance(raw, dict):
            return KYCState(user_id=user_id, profile=profile, question=KYC_QUESTIONS[0])
        step = int(raw.get("step", 0))
        completed = bool(raw.get("completed", False))
        question = None if completed else KYC_QUESTIONS[step]
        return KYCState(
            user_id=user_id,
            step=step,
            answers=dict(raw.get("answers", {})),
            profile=profile,
            completed=completed,
            risk_level=raw.get("risk_level"),
            risk_score=raw.get("risk_score"),
            allocation=dict(raw.get("allocation", {})),
            allocation_explanation=raw.get("allocation_explanation", ""),
            market_environment=MarketEnvironment.model_validate(raw.get("market_environment", {})),
            question=question,
        )

    @staticmethod
    def _calculate_risk_score(answers: dict[str, str]) -> int:
        total = 0
        for question in KYC_QUESTIONS:
            value = answers[question.id]
            option = next(item for item in question.options if item.value == value)
            total += option.score
        return total

    @staticmethod
    def _risk_level(risk_score: int) -> str:
        if risk_score <= 11:
            return "保守"
        if risk_score <= 18:
            return "稳健"
        return "积极"

    @staticmethod
    def _calculate_allocation(
        risk_score: int,
        risk_level: str,
        horizon: str,
        expense_ratio: str,
    ) -> tuple[dict[str, int], str]:
        base_risky = 20 + 2.5 * (risk_score - 5)
        horizon_adjustment = _HORIZON_ADJUSTMENTS[horizon]
        expense_adjustment = _EXPENSE_ADJUSTMENTS[expense_ratio]
        risky = round(min(90, max(5, base_risky + horizon_adjustment + expense_adjustment)))
        stock_ratio = min(0.7, 0.3 + 0.02 * (risk_score - 5))
        stocks = round(risky * stock_ratio)
        funds = risky - stocks
        cash = 100 - risky
        allocation = {"股票": stocks, "基金": funds, "现金": cash}
        explanation = (
            f"风险分{risk_score}/25，等级为{risk_level}。基础风险资产比例为20 + 2.5×(风险分-5)，"
            f"即{base_risky:.1f}%；投资期限调整{horizon_adjustment:+d}个百分点，"
            f"固定支出占比调整{expense_adjustment:+d}个百分点，风险资产限制在5%至90%。"
            "股票占风险资产的比例随风险分由30%线性提高至70%，其余风险资产配置基金，"
            "风险资产之外配置现金。市场环境字段为明确标注的虚构情景，不代表实时宏观、利率或政策判断，也不用于预测收益。"
        )
        return allocation, explanation
