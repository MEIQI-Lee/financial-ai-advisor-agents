import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from financial_ai_advisor_agents.schemas.rag import KnowledgeDocument, SearchResult


_TOKEN_PATTERN = re.compile(r"[a-zA-Z]+[a-zA-Z0-9]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]+")


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for part in _TOKEN_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            if len(part) == 1:
                tokens.append(part)
            else:
                tokens.extend(part[index : index + 2] for index in range(len(part) - 1))
        else:
            tokens.append(part)
    return tokens


class LocalBM25Index:
    def __init__(self, documents_path: Path, index_path: Path):
        self.documents_path = Path(documents_path)
        self.index_path = Path(index_path)

    def build(self) -> int:
        payload = json.loads(self.documents_path.read_text(encoding="utf-8"))
        raw_documents = payload.get("documents") if isinstance(payload, dict) else payload
        if not isinstance(raw_documents, list):
            raise ValueError("知识库必须是文档数组或包含 documents 数组的对象")
        documents = [KnowledgeDocument.model_validate(item) for item in raw_documents]
        chunk_ids = [document.id for document in documents]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("知识库文档 id 必须唯一")

        indexed_documents = []
        document_frequency: Counter[str] = Counter()
        total_length = 0
        for document in documents:
            tokens = _tokenize(f"{document.title}\n{document.content}")
            frequencies = Counter(tokens)
            document_frequency.update(frequencies.keys())
            total_length += len(tokens)
            indexed_documents.append(
                {
                    "chunk_id": document.id,
                    "title": document.title,
                    "text": document.content,
                    "source": document.source,
                    "page": document.page,
                    "tags": document.tags,
                    "length": len(tokens),
                    "term_frequencies": dict(sorted(frequencies.items())),
                }
            )
        index = {
            "version": 1,
            "tokenizer": "chinese-bigram+english-number",
            "k1": 1.5,
            "b": 0.75,
            "document_count": len(indexed_documents),
            "average_document_length": total_length / len(indexed_documents) if indexed_documents else 0,
            "document_frequency": dict(sorted(document_frequency.items())),
            "documents": indexed_documents,
        }
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(indexed_documents)

    def search(
        self,
        query: str,
        tags: Iterable[str] = (),
        top_k: int = 3,
    ) -> list[SearchResult]:
        if not self.index_path.exists():
            raise FileNotFoundError(f"BM25 索引不存在：{self.index_path}；请先调用 build()")
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        if top_k <= 0:
            return []
        if isinstance(tags, str):
            tags = (tags,)
        requested_tags = {tag.strip() for tag in tags if tag.strip()}
        query_terms = set(_tokenize(query))
        documents = index["documents"]
        if not query_terms or not documents:
            return []

        document_count = len(documents)
        average_length = index["average_document_length"] or 1.0
        document_frequency = index["document_frequency"]
        k1 = float(index["k1"])
        b = float(index["b"])
        ranked: list[tuple[float, SearchResult]] = []
        for document in documents:
            document_tags = set(document["tags"])
            matched_tags = requested_tags & document_tags
            if requested_tags and not matched_tags:
                continue
            frequencies = document["term_frequencies"]
            length = document["length"]
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                df = document_frequency[term]
                inverse_frequency = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
                denominator = frequency + k1 * (1 - b + b * length / average_length)
                score += inverse_frequency * frequency * (k1 + 1) / denominator
            if score <= 0:
                continue
            score += 0.5 * len(matched_tags)
            result = SearchResult(
                chunk_id=document["chunk_id"],
                title=document["title"],
                text=document["text"],
                source=document["source"],
                page=document["page"],
                tags=document["tags"],
                score=round(score, 6),
            )
            ranked.append((score, result))
        ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return [result for _, result in ranked[:top_k]]
