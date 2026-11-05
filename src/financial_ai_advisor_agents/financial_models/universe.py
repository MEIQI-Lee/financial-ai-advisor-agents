import csv
from pathlib import Path

from financial_ai_advisor_agents.financial_models.schemas import Security


class SecurityUniverse:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = Path(csv_path)

    def load(self) -> list[Security]:
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as source:
            securities = [Security.model_validate(row) for row in csv.DictReader(source)]
        if not securities:
            raise ValueError(f"security universe is empty: {self.csv_path}")
        symbols = [security.symbol for security in securities]
        if len(symbols) != len(set(symbols)):
            raise ValueError("security universe contains duplicate symbols")
        return securities

    def get(self, symbol: str) -> Security:
        normalized = symbol.strip().upper()
        for security in self.load():
            if security.symbol == normalized:
                return security
        raise ValueError(f"unknown security symbol: {symbol}")
