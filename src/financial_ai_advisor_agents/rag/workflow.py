import re

from financial_ai_advisor_agents.rag.index import LocalBM25Index, _tokenize
from financial_ai_advisor_agents.schemas.rag import RAGResponse, SearchResult


_MIN_RELEVANCE_SCORE = 0.2
_SENTENCE_PATTERN = re.compile(r"[^。！？!?]+[。！？!?]?")


class RAGWorkflow:
    def __init__(self, index: LocalBM25Index):
        self.index = index

    def run(self, query: str, top_k: int = 3, tags=()) -> RAGResponse:
        results = self.index.search(query, tags=tags, top_k=top_k)
        if not results or results[0].score < _MIN_RELEVANCE_SCORE:
            return RAGResponse(
                query=query,
                answer="现有知识库没有足够的相关内容，无法基于可靠资料回答。",
                sources=[],
                tags=[],
                status="insufficient_evidence",
            )

        answer_parts = [
            f"{self._extract_sentences(query, result)}[{number}]"
            for number, result in enumerate(results, start=1)
        ]
        tags = list(dict.fromkeys(tag for result in results for tag in result.tags))
        return RAGResponse(
            query=query,
            answer="\n".join(answer_parts),
            sources=results,
            tags=tags,
            status="ok",
        )

    @staticmethod
    def _extract_sentences(query: str, result: SearchResult) -> str:
        sentences = [item.strip() for item in _SENTENCE_PATTERN.findall(result.text) if item.strip()]
        if not sentences:
            return result.text.strip()
        query_terms = set(_tokenize(query))
        scored = [
            (index, len(query_terms & set(_tokenize(sentence))))
            for index, sentence in enumerate(sentences)
        ]
        selected = [index for index, score in sorted(scored, key=lambda item: (-item[1], item[0])) if score > 0][:2]
        if not selected:
            selected = [0]
        return "".join(sentences[index] for index in sorted(selected))
