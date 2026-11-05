import json
from pathlib import Path

import pytest

from financial_ai_advisor_agents.rag.index import LocalBM25Index, _tokenize


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS_PATH = PROJECT_ROOT / "data" / "mock" / "knowledge.json"


def test_build_writes_real_offline_bm25_statistics(tmp_path):
    index_path = tmp_path / "nested" / "knowledge-index.json"
    index = LocalBM25Index(DOCUMENTS_PATH, index_path)
    count = index.build()
    assert count >= 8

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["document_count"] == count
    assert len(payload["documents"]) == count
    assert payload["average_document_length"] > 0
    assert payload["document_frequency"]["资产"] >= 2
    assert payload["document_frequency"]["rsi"] == 1
    assert all(document["term_frequencies"] for document in payload["documents"])


def test_tokenizer_supports_chinese_bigram_english_and_numbers():
    tokens = _tokenize("RSI达到70，资产配置ABC123")
    assert tokens[:3] == ["rsi", "达到", "70"]
    assert "资产" in tokens
    assert "产配" in tokens
    assert "配置" in tokens
    assert "abc123" in tokens


def test_search_is_relevant_for_chinese_and_english_queries(tmp_path):
    index = LocalBM25Index(DOCUMENTS_PATH, tmp_path / "index.json")
    index.build()
    chinese = index.search("如何理解最大回撤", top_k=3)
    english = index.search("RSI 70 超买是什么意思", top_k=3)
    assert chinese[0].chunk_id == "maximum-drawdown"
    assert "最大回撤" in chinese[0].text
    assert english[0].chunk_id == "rsi-indicator"
    assert english[0].score > 0


def test_tag_filter_and_matching_bonus(tmp_path):
    index = LocalBM25Index(DOCUMENTS_PATH, tmp_path / "index.json")
    index.build()
    unfiltered = index.search("资金 风险", top_k=20)
    filtered = index.search("资金 风险", tags=("备用金",), top_k=5)
    assert filtered
    assert all("备用金" in result.tags for result in filtered)
    original = next(result for result in unfiltered if result.chunk_id == "emergency-fund")
    boosted = next(result for result in filtered if result.chunk_id == "emergency-fund")
    assert boosted.score == pytest.approx(original.score + 0.5)


def test_missing_index_fails_explicitly(tmp_path):
    index = LocalBM25Index(DOCUMENTS_PATH, tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError, match="请先调用 build"):
        index.search("资产配置")
