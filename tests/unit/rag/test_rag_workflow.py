import re
from pathlib import Path

from financial_ai_advisor_agents.rag.index import LocalBM25Index
from financial_ai_advisor_agents.rag.workflow import RAGWorkflow


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_workflow(tmp_path):
    index = LocalBM25Index(PROJECT_ROOT / "data" / "mock" / "knowledge.json", tmp_path / "index.json")
    index.build()
    return RAGWorkflow(index)


def test_answer_is_grounded_with_consistent_citations_and_tags(tmp_path):
    response = build_workflow(tmp_path).run("资产配置为什么要考虑投资期限", top_k=3)
    assert response.status == "ok"
    assert response.sources
    citations = re.findall(r"\[(\d+)\]", response.answer)
    assert citations == [str(number) for number in range(1, len(response.sources) + 1)]

    parts = response.answer.splitlines()
    assert len(parts) == len(response.sources)
    for number, (part, source) in enumerate(zip(parts, response.sources), start=1):
        assert part.endswith(f"[{number}]")
        retrieved_sentences = part[: -len(f"[{number}]")]
        sentences = re.findall(r"[^。！？!?]+[。！？!?]?", retrieved_sentences)
        assert sentences
        assert all(sentence in source.text for sentence in sentences)
        assert source.source
        assert source.page > 0
    assert response.tags == list(dict.fromkeys(tag for source in response.sources for tag in source.tags))


def test_no_evidence_does_not_invent_an_answer(tmp_path):
    response = build_workflow(tmp_path).run("如何制作巧克力蛋糕")
    assert response.status == "insufficient_evidence"
    assert response.sources == []
    assert response.tags == []
    assert "无法" in response.answer
    assert "[1]" not in response.answer


def test_empty_query_and_zero_top_k_have_no_evidence(tmp_path):
    workflow = build_workflow(tmp_path)
    assert workflow.run("").status == "insufficient_evidence"
    assert workflow.run("资产配置", top_k=0).status == "insufficient_evidence"
