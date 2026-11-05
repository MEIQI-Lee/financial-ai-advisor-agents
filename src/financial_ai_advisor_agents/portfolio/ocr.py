import re
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from financial_ai_advisor_agents.schemas.portfolio import Holding


_NUMBER = r"[-+]?\d+(?:\.\d+)?"


class PaddleOCREngine:
    def __init__(self, lang: str = "ch", **kwargs: Any) -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed; install the optional 'paddleocr' dependency to analyze images"
            ) from exc
        self._engine = PaddleOCR(lang=lang, **kwargs)

    def extract_text(self, content: bytes, filename: str = "") -> list[str]:
        suffix = Path(filename).suffix if Path(filename).suffix else ".png"
        temporary_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(content)
                temporary_path = temporary.name
            result = self._engine.ocr(temporary_path)
            return _extract_texts(result)
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)


def _extract_texts(result: Any) -> list[str]:
    if result is None:
        return []
    if isinstance(result, str):
        return [result]
    if isinstance(result, dict):
        if isinstance(result.get("rec_texts"), list):
            return [str(text) for text in result["rec_texts"]]
        texts: list[str] = []
        for value in result.values():
            texts.extend(_extract_texts(value))
        return texts
    if isinstance(result, (tuple, list)):
        if len(result) == 2 and isinstance(result[0], str) and isinstance(result[1], (int, float)):
            return [result[0]]
        texts = []
        for item in result:
            texts.extend(_extract_texts(item))
        return texts
    return []


def extract_ocr_lines(engine: Any, content: bytes, filename: str) -> list[str]:
    if hasattr(engine, "extract_text"):
        result = engine.extract_text(content, filename)
    elif hasattr(engine, "recognize"):
        result = engine.recognize(content, filename)
    elif callable(engine):
        result = engine(content, filename)
    else:
        raise TypeError("OCR engine must be callable or provide extract_text(content, filename)")
    if isinstance(result, str):
        return [line.strip() for line in result.splitlines() if line.strip()]
    return [str(line).strip() for line in result if str(line).strip()]


def _keyed_value(line: str, labels: str) -> str | None:
    match = re.search(rf"(?:{labels})\s*[:：]?\s*({_NUMBER}%?)", line, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _keyed_text(line: str, labels: str) -> str | None:
    match = re.search(rf"(?:{labels})\s*[:：]\s*([^\s,，|]+)", line, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _to_float(value: str) -> float:
    number = float(value.rstrip("%"))
    return number / 100.0 if value.endswith("%") else number


def parse_ocr_line(line: str) -> Holding:
    cleaned = re.sub(r"(?<=\d),(?=\d{3}\b)", "", line.strip())
    if not cleaned:
        raise ValueError("empty OCR line")

    symbol = _keyed_text(cleaned, r"证券代码|代码|symbol")
    if symbol is None:
        match = re.match(r"^([A-Za-z][A-Za-z0-9.-]{1,15}|\d{6}|现金)(?:\s+|$)", cleaned)
        symbol = match.group(1) if match else None
    if not symbol:
        raise ValueError(f"OCR line has no recognizable symbol: {line}")

    quantity_text = _keyed_value(cleaned, r"持仓数量|数量|持仓|quantity|qty")
    price_text = _keyed_value(cleaned, r"当前价格|当前价|现价|市价|current_price|price")
    cost_text = _keyed_value(cleaned, r"成本价格|成本价|成本|cost_price|cost")
    return_text = _keyed_value(cleaned, r"持有期收益率|期间收益率|收益率|period_return|return")
    name = _keyed_text(cleaned, r"证券名称|名称|name")
    sector = _keyed_text(cleaned, r"行业|板块|sector")

    if quantity_text is None or price_text is None or cost_text is None:
        tokens = [token for token in re.split(r"[\s,，|]+", cleaned) if token]
        try:
            symbol_index = tokens.index(symbol)
        except ValueError as exc:
            raise ValueError(f"OCR line has incomplete numeric fields: {line}") from exc
        if len(tokens) <= symbol_index + 1:
            raise ValueError(f"OCR line has no security name: {line}")
        name = name or tokens[symbol_index + 1]
        numeric_start = symbol_index + 2
        if sector is None and len(tokens) > numeric_start and not re.fullmatch(rf"{_NUMBER}%?", tokens[numeric_start]):
            sector = tokens[numeric_start]
            numeric_start += 1
        numeric_tokens = [
            token for token in tokens[numeric_start:] if re.fullmatch(rf"{_NUMBER}%?", token)
        ]
        if len(numeric_tokens) < 3:
            raise ValueError(f"OCR line requires quantity, current price and cost price: {line}")
        quantity_text = quantity_text or numeric_tokens[0]
        price_text = price_text or numeric_tokens[1]
        cost_text = cost_text or numeric_tokens[2]
        if return_text is None and len(numeric_tokens) >= 4:
            return_text = numeric_tokens[3]

    quantity = _to_float(quantity_text)
    current_price = _to_float(price_text)
    cost_price = _to_float(cost_text)
    if return_text is not None:
        period_return = _to_float(return_text)
    elif cost_price > 0:
        period_return = current_price / cost_price - 1.0
    else:
        raise ValueError(f"OCR line needs a return when cost price is zero: {line}")
    return Holding(
        symbol=symbol,
        name=name or "待确认",
        sector=sector or "待确认",
        quantity=quantity,
        current_price=current_price,
        cost_price=cost_price,
        period_return=period_return,
        return_history=[0.0] * 12,
    )


def parse_ocr_lines(lines: Sequence[str]) -> list[Holding]:
    holdings: list[Holding] = []
    for line in lines:
        if re.match(r"^\s*(证券代码|代码\s+名称|symbol\s+name)", line, flags=re.IGNORECASE):
            continue
        holdings.append(parse_ocr_line(line))
    if not holdings:
        raise ValueError("OCR did not produce any holding rows")
    return holdings
