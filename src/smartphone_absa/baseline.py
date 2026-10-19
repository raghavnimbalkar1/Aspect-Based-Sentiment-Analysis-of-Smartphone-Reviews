"""B1: explicit aspect cues and clause-local VADER, with documented domain rules."""

from __future__ import annotations

import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from smartphone_absa.domain import Analysis, AspectResult, Evidence
from smartphone_absa.taxonomy import CATEGORIES, TAXONOMY_VERSION, aggregate_sentiments
from smartphone_absa.text import detect_language, split_sentences

MODEL_ID = "rules-v1"
_CLAUSE_BREAK = re.compile(r"\b(?:but|however|although|yet|whereas)\b|[;\n]|,\s*(?=the\b)", re.I)
_RETAIL = re.compile(r"\b(?:shipping|delivery|seller|packaging|shipment)\b", re.I)


class RuleBaseline:
    id = MODEL_ID

    def __init__(self) -> None:
        self.vader = SentimentIntensityAnalyzer()
        self.patterns = {
            category.id: re.compile(r"\b(?:" + "|".join(category.cues) + r")\b", re.I)
            for category in CATEGORIES
        }

    def _state(self, text: str, category: str) -> tuple[str, float]:
        score = self.vader.polarity_scores(text)["compound"]
        # These are baseline heuristics, not human labels or learned weights.
        domain_positive = {
            "battery": r"\b(?:lasts? (?:all|a full|the whole) day|long battery|great battery)\b",
            "charging": r"\b(?:fast charg\w*|charg\w* (?:very )?(?:fast|quickly))\b",
            "camera": r"\b(?:sharp|crisp|clear) (?:photos?|pictures?|images?)\b",
            "display": r"\b(?:bright|vibrant|crisp|sharp)\b",
            "performance": r"\b(?:smooth|snappy|responsive|very fast)\b",
            "value": r"\b(?:worth (?:the|every)|affordable|value for money)\b",
        }
        domain_negative = {
            "battery": (
                r"\b(?:barely lasts?|drains? (?:fast|quickly)|dead by|battery dies|poor battery)\b"
            ),
            "charging": r"\b(?:won.t charge|stopped charging|slow charg\w*|charg\w* slowly)\b",
            "camera": r"\b(?:blurry|grainy|out of focus)\b",
            "display": r"\b(?:dim|unresponsive|dead pixels?|flicker\w*)\b",
            "performance": r"\b(?:lag\w*|overheat\w*|(?:gets?|runs?) hot|slow)\b",
            "software": r"\b(?:crash\w*|freez\w*|bloatware|buggy)\b",
            "audio": r"\b(?:muffled|distorted|tinny)\b",
            "connectivity": r"\b(?:drops?|disconnect\w*|no signal|poor reception)\b",
            "value": r"\b(?:overpriced|too expensive|waste of money|not worth)\b",
        }
        positive = bool(re.search(domain_positive.get(category, r"(?!)"), text, re.I))
        negative = bool(re.search(domain_negative.get(category, r"(?!)"), text, re.I))
        # Explicit negation around a domain cue defeats the positive heuristic.
        if positive and re.search(r"\b(?:not|never|isn.t|aren.t)\b", text, re.I):
            positive = False
        if positive and negative:
            return "mixed", score
        if negative:
            return "negative", score
        if positive:
            return "positive", score
        if score >= 0.05:
            return "positive", score
        if score <= -0.05:
            return "negative", score
        return "neutral", score

    def analyse(self, text: str, review_id: str = "input", language: str | None = None) -> Analysis:
        language = language or detect_language(text)
        warnings = []
        if language not in ("en", "unknown"):
            return Analysis(
                model_id=self.id,
                taxonomy_version=TAXONOMY_VERSION,
                aspects=[],
                sentences=[],
                language=language,
                supported=False,
                warnings=["English is supported. This text was detected as another language."],
            )
        if language == "unknown":
            warnings.append("Language is uncertain; short English text is processed provisionally.")
        sentences = split_sentences(text, review_id)
        grouped: dict[str, list[Evidence]] = {}
        if any(len(sentence.text) > 3000 for sentence in sentences):
            warnings.append(
                "A long sentence may give poor aspect/opinion attachment in this baseline."
            )
        for sentence in sentences:
            states: dict[str, list[tuple[str, float]]] = {}
            clauses = [
                part.strip(" ,") for part in _CLAUSE_BREAK.split(sentence.text) if part.strip()
            ]
            # Split 'and' only when both halves have their own aspect cues.
            expanded = []
            for clause in clauses:
                parts = re.split(r"\band\b", clause, flags=re.I)
                if len(parts) > 1 and all(
                    any(p.search(part) for p in self.patterns.values()) for part in parts
                ):
                    expanded.extend(parts)
                else:
                    expanded.append(clause)
            for clause in expanded:
                matched = {
                    category
                    for category, pattern in self.patterns.items()
                    if pattern.search(clause)
                }
                # Bare 'fast' often describes charging; avoid that performance false positive.
                if "performance" in matched and "charging" in matched:
                    without_charging = re.sub(r"\bfast\b", "", clause, flags=re.I)
                    if not self.patterns["performance"].search(without_charging):
                        matched.discard("performance")
                if _RETAIL.search(clause):
                    warnings.append(
                        "Retail-related text is excluded where no phone feature is explicit."
                    )
                    if matched <= {"performance"} and not re.search(
                        r"\b(?:phone|device|gaming|processor|lag\w*)\b", clause, re.I
                    ):
                        continue
                for category in matched:
                    states.setdefault(category, []).append(self._state(clause, category))
            for category, values in states.items():
                state = aggregate_sentiments([label for label, _ in values])
                # Compound is a lexicon score, not a calibrated confidence.
                grouped.setdefault(category, []).append(
                    Evidence(
                        sentence_id=sentence.id,
                        text=sentence.text,
                        start=sentence.start,
                        end=sentence.end,
                        sentiment=state,
                        score=sum(score for _, score in values) / len(values),
                    )
                )
        aspects = [
            AspectResult(
                category=category.id,
                sentiment=aggregate_sentiments([e.sentiment for e in grouped[category.id]]),
                evidence=grouped[category.id],
            )
            for category in CATEGORIES
            if category.id in grouped
        ]
        warnings.append("Rule baseline: implicit aspects and opinion attachment can be missed.")
        return Analysis(
            model_id=self.id,
            taxonomy_version=TAXONOMY_VERSION,
            aspects=aspects,
            sentences=sentences,
            warnings=list(dict.fromkeys(warnings)),
            language=language,
        )
