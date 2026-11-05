from financial_ai_advisor_agents.schemas.pipeline import TaskResult, TaskStatus


def test_validator_rejects_failed_required_task(app):
    plan = app.planner.run("RSI 超卖", app.pipeline.memory.context("u"))
    failed = TaskResult(task_id="database_1", status=TaskStatus.FAILED, error="SQL failed")
    result = app.validator.run("RSI 超卖", plan, [failed])
    assert result.passed is False
    assert result.failed_task_ids == ["database_1"]
    assert "SQL failed" in result.feedback


def test_synthesizer_states_capability_boundary(app):
    result = app.synthesizer.run("预测明天涨停股", [])
    assert result.status == "unsupported"
    assert "待实现" in result.answer
