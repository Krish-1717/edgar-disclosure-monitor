"""Data validation for EDGAR Disclosure Monitor pipeline inputs."""
import re
from dataclasses import dataclass, field
from typing import Any

VALID_FORM_TYPES = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
TICKER_RE = re.compile(r"^[A-Z]{1,5}$")

@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def raise_if_invalid(self):
        if not self.is_valid:
            raise ValueError(f"Validation failed: {'; '.join(self.errors)}")

class DataValidator:
    def validate_ticker(self, ticker: Any) -> ValidationResult:
        r = ValidationResult()
        if not isinstance(ticker, str):
            r.add_error(f"ticker must be str, got {type(ticker).__name__}")
            return r
        if not TICKER_RE.match(ticker):
            r.add_error(f"Invalid ticker format '{ticker}': must be 1-5 uppercase letters")
        return r

    def validate_filing(self, filing: dict) -> ValidationResult:
        r = ValidationResult()
        for key in ("accession", "form_type", "filed_date"):
            if key not in filing:
                r.add_error(f"Missing required field: {key}")
        if "accession" in filing and not ACCESSION_RE.match(str(filing["accession"])):
            r.add_error(f"Invalid accession format: {filing['accession']}")
        if "form_type" in filing and filing["form_type"] not in VALID_FORM_TYPES:
            r.add_error(f"Unsupported form_type: {filing['form_type']}")
        if "text" in filing and len(str(filing["text"]).split()) < 100:
            r.add_warning("Filing text is very short -- may be incomplete")
        return r

    def validate_materiality_score(self, score: Any) -> ValidationResult:
        r = ValidationResult()
        try:
            s = float(score)
        except (TypeError, ValueError):
            r.add_error(f"materiality_score must be numeric, got {type(score).__name__}")
            return r
        import math
        if math.isnan(s) or math.isinf(s):
            r.add_error("materiality_score is NaN or Inf")
        elif not (0.0 <= s <= 1.0):
            r.add_error(f"materiality_score out of range [0,1]: {s}")
        return r

    def validate_news_score(self, composite: Any, count: Any) -> ValidationResult:
        r = ValidationResult()
        r2 = self.validate_materiality_score(composite)
        r.errors.extend(r2.errors)
        r.warnings.extend(r2.warnings)
        if not r2.is_valid:
            r.is_valid = False
        if not isinstance(count, int) or count < 0:
            r.add_error(f"article_count must be non-negative int, got {count!r}")
        if isinstance(composite, float) and isinstance(count, int):
            if composite > 0.9 and count < 2:
                r.add_warning("High composite score with very few articles -- verify data")
        return r

    def validate_filing_text(self, text: Any, min_words: int = 100) -> ValidationResult:
        r = ValidationResult()
        if not isinstance(text, str):
            r.add_error(f"Filing text must be str, got {type(text).__name__}")
            return r
        if not text.strip():
            r.add_error("Filing text is empty")
            return r
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            r.add_error("Filing text contains non-UTF-8 characters")
        word_count = len(text.split())
        if word_count < min_words:
            r.add_error(f"Filing text too short: {word_count} words (min {min_words})")
        return r

if __name__ == "__main__":
    v = DataValidator()
    print(v.validate_ticker("NVDA").is_valid)
    print(v.validate_ticker("aapl123").errors)
    print(v.validate_materiality_score(1.5).errors)
    print(v.validate_filing({"form_type": "10-K", "filed_date": "2024-01-01"}).errors)
    print(v.validate_news_score(0.75, 5).is_valid)
