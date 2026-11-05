import pytest

from financial_ai_advisor_agents.kyc.workflow import KYC_QUESTIONS, KYCWorkflow
from financial_ai_advisor_agents.memory.store import MemoryStore


ANSWERS = {
    "investment_experience": "professional",
    "loss_reaction": "buy_more",
    "fixed_expense_destination": "insurance_savings",
    "fixed_expense_ratio": "under_20",
    "investment_horizon": "over_10_years",
}


def complete(workflow, user_id="user", **overrides):
    values = {**ANSWERS, **overrides}
    state = workflow.start(user_id)
    for question in KYC_QUESTIONS:
        assert state.question is not None
        assert state.question.id == question.id
        state = workflow.answer(user_id, question.id, values[question.id])
    return state


def test_status_initial_and_full_five_question_flow(tmp_path):
    workflow = KYCWorkflow(MemoryStore(tmp_path / "memory.db"))
    initial = workflow.status("user")
    assert initial.step == 0
    assert not initial.completed
    assert initial.question.id == KYC_QUESTIONS[0].id

    state = complete(workflow)
    assert state.completed
    assert state.step == 5
    assert state.question is None
    assert state.answers == ANSWERS
    assert state.risk_level == "积极"
    assert state.risk_score == 24
    assert sum(state.allocation.values()) == 100
    assert set(state.allocation) == {"股票", "基金", "现金"}
    assert "风险分24/25" in state.allocation_explanation
    assert state.market_environment.economic_cycle.startswith("虚构")
    assert state.market_environment.market_interest_rate.startswith("虚构")
    assert "未接入政策资讯" in state.market_environment.policies_and_regulations


def test_every_answer_is_persistent_and_new_store_recovers(tmp_path):
    path = tmp_path / "memory.db"
    workflow = KYCWorkflow(MemoryStore(path))
    workflow.start("user")
    first = KYC_QUESTIONS[0]
    workflow.answer("user", first.id, ANSWERS[first.id])

    resumed = KYCWorkflow(MemoryStore(path)).status("user")
    assert resumed.step == 1
    assert resumed.answers == {first.id: ANSWERS[first.id]}
    assert resumed.question.id == KYC_QUESTIONS[1].id
    resumed_workflow = KYCWorkflow(MemoryStore(path))
    for question in KYC_QUESTIONS[1:]:
        resumed_workflow.answer("user", question.id, ANSWERS[question.id])

    restored = KYCWorkflow(MemoryStore(path)).status("user")
    assert restored.completed
    assert restored.profile["kyc"]["allocation"] == restored.allocation
    assert restored.profile["kyc"]["profile"]["risk_level"] == restored.risk_level


def test_start_restarts_completed_assessment(tmp_path):
    workflow = KYCWorkflow(MemoryStore(tmp_path / "memory.db"))
    complete(workflow)
    restarted = workflow.start("user")
    assert restarted.step == 0
    assert restarted.answers == {}
    assert not restarted.completed
    assert restarted.risk_score is None
    assert restarted.allocation == {}
    assert restarted.question.id == KYC_QUESTIONS[0].id


def test_answer_validates_order_id_and_option_without_state_change(tmp_path):
    workflow = KYCWorkflow(MemoryStore(tmp_path / "memory.db"))
    workflow.start("user")
    with pytest.raises(ValueError, match="顺序或问题ID"):
        workflow.answer("user", KYC_QUESTIONS[1].id, "hold")
    with pytest.raises(ValueError, match="不属于"):
        workflow.answer("user", KYC_QUESTIONS[0].id, "unknown")
    with pytest.raises(ValueError, match="尚未开始"):
        workflow.answer("missing", KYC_QUESTIONS[0].id, "none")
    assert workflow.status("user").step == 0

    complete(workflow)
    with pytest.raises(ValueError, match="已完成"):
        workflow.answer("user", KYC_QUESTIONS[-1].id, ANSWERS[KYC_QUESTIONS[-1].id])


def test_allocation_rules_reduce_risky_assets_for_high_fixed_expenses(tmp_path):
    workflow = KYCWorkflow(MemoryStore(tmp_path / "memory.db"))
    low_expense = complete(workflow, "low", fixed_expense_ratio="under_20")
    high_expense = complete(workflow, "high", fixed_expense_ratio="over_60")

    for state in (low_expense, high_expense):
        assert sum(state.allocation.values()) == 100
        assert all(isinstance(value, int) and value >= 0 for value in state.allocation.values())
        assert "固定支出占比调整" in state.allocation_explanation
    low_risky = low_expense.allocation["股票"] + low_expense.allocation["基金"]
    high_risky = high_expense.allocation["股票"] + high_expense.allocation["基金"]
    assert high_risky < low_risky
    assert high_expense.allocation["现金"] > low_expense.allocation["现金"]


def test_short_horizon_reduces_risky_assets(tmp_path):
    workflow = KYCWorkflow(MemoryStore(tmp_path / "memory.db"))
    long_term = complete(workflow, "long", investment_horizon="over_10_years")
    short_term = complete(workflow, "short", investment_horizon="under_1_year")
    long_risky = long_term.allocation["股票"] + long_term.allocation["基金"]
    short_risky = short_term.allocation["股票"] + short_term.allocation["基金"]
    assert short_risky < long_risky
