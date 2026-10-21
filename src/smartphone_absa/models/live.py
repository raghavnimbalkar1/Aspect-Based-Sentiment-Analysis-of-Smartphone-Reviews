"""Live-review adapter. Candidate policy and transformer decisions remain separate.

Edit aspects_live.json for vocabulary. Sentiment comes from the pinned DeBERTa
checkpoint, not from the keyword list or any expected demonstration answer.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from smartphone_absa.domain import Analysis, AspectResult, Evidence, GeneralOpinion, InferenceStep
from smartphone_absa.models.checkpoints import REVISION
from smartphone_absa.models.domain_adapter import ADAPTER_SHA256, DomainABSA
from smartphone_absa.models.inference import TransferredABSA
from smartphone_absa.taxonomy import CATEGORIES, TAXONOMY_VERSION, aggregate_sentiments
from smartphone_absa.text import detect_language, split_sentences

CONFIG_PATH = Path(__file__).with_name("aspects_live.json")
CONFIG = json.loads(CONFIG_PATH.read_text())
POLICY_SHA256 = hashlib.sha256(
    CONFIG_PATH.read_bytes() + Path(__file__).read_bytes() + ADAPTER_SHA256.encode()
).hexdigest()
LIVE_ID = f"deberta-live-v3-{REVISION[:8]}-{POLICY_SHA256[:8]}"
IMPLICIT = {
    category: re.compile("|".join(patterns), re.I)
    for category, patterns in CONFIG["additional_cues"].items()
}
CHARGING_ONLY = re.compile(
    r"\bcharg\w*\b.{0,45}\b(?:slow|fast|speed)\b|"
    r"\b(?:slow|fast)\s+(?:wireless\s+)?charg\w*\b",
    re.I,
)
PERFORMANCE_CUES = re.compile(
    r"\b(?:performance|processor|gaming|games?|lag\w*|overheat\w*|snappy|responsive|"
    r"multitask\w*|stutter\w*|freez\w*)\b",
    re.I,
)
BATTERY_CHARGING = re.compile(r"\bbatter(?:y|ies)\s+(?:is\s+)?charg\w*\b", re.I)
ENDURANCE = re.compile(r"\b(?:last\w*|drain\w*|standby|dies?|dead|endurance|capacity)\b", re.I)
APP_SPEED = re.compile(
    r"\bapps?\s+(?:open|launch|load)\w*\b.{0,20}\b(?:instantly|quickly|slowly|fast|slow)\b",
    re.I,
)
SOFTWARE_SPECIFIC = re.compile(
    r"\b(?:software|android|ios|updates?|bloatware|interface|operating system|bugs?|crash\w*)\b",
    re.I,
)
PHONE_REFERENCE = re.compile(r"\b(?:phone|smartphone|device|iphone|handset|it)\b", re.I)
ENGLISH_PHRASE = re.compile(
    r"\b(?:the|this|my|its|is|are|was|very|not|good|bad|great|excellent|terrible|life)\b", re.I
)


def normalise_context(text: str) -> str:
    """Normalise typographic punctuation for inference, never for saved evidence."""
    return text.translate(str.maketrans({"’": "'", "‘": "'", "‑": "-", "–": "-"}))


def live_pairs(text: str) -> list[tuple[str, str, str, str]]:
    """Category, local context, sentiment target and actual matched cue."""
    from smartphone_absa.models.domain_adapter import (
        CONFIG as ORIGINAL_CONFIG,
    )
    from smartphone_absa.models.domain_adapter import (
        PATTERNS,
        clauses,
        valid_cue,
    )

    pairs = []
    for clause in clauses(normalise_context(text)):
        # A comma between two full feature opinions also creates separate contexts.
        parts = re.split(r",\s*(?=(?:the|my|its|this)\b)", clause, flags=re.I)
        for part in parts:
            for category, pattern in PATTERNS.items():
                matches = [m for m in pattern.finditer(part) if valid_cue(category, m, part)]
                additional = IMPLICIT.get(category)
                extra = additional.search(part) if additional else None
                if not matches and not extra:
                    continue
                if (
                    category == "performance"
                    and (CHARGING_ONLY.search(part) or re.search(r"\bdrain\w*\b", part, re.I))
                    and not PERFORMANCE_CUES.search(part)
                ):
                    continue
                if (
                    category == "battery"
                    and BATTERY_CHARGING.search(part)
                    and not ENDURANCE.search(part)
                ):
                    continue
                if (
                    category == "software"
                    and APP_SPEED.search(part)
                    and not SOFTWARE_SPECIFIC.search(part)
                ):
                    continue
                cue = matches[0].group() if matches else extra.group()
                target = CONFIG.get("target_overrides", {}).get(
                    category, ORIGINAL_CONFIG["categories"][category]["target"]
                )
                if category == "connectivity" and cue.lower() in {
                    "signal",
                    "reception",
                    "wi-fi",
                    "wifi",
                    "bluetooth",
                    "gps",
                    "mobile data",
                    "hotspot",
                }:
                    target = cue.lower()
                pairs.append((category, part.strip(), target, cue))
    return pairs


class LiveABSA(DomainABSA):
    def __init__(self, backbone: TransferredABSA):
        self.id = LIVE_ID
        self.backbone = backbone

    def candidate_pairs(self, text: str) -> list[tuple[str, str, str]]:
        return [(category, context, target) for category, context, target, _ in live_pairs(text)]

    def limitations(self) -> list[str]:
        return [
            "DeBERTa sentiment with smartphone candidate rules. "
            "No smartphone transformer fine-tuning.",
            "Implicit references, sarcasm and comparisons can still be misread.",
            "Model scores are uncalibrated and are not accuracy percentages.",
        ]

    def analyse(self, text: str, review_id: str = "input", language: str | None = None) -> Analysis:
        detected = language or detect_language(text)
        if language is None and detected == "unknown":
            letters = [char for char in text if char.isalpha()]
            foreign = sum("LATIN" not in unicodedata.name(char, "") for char in letters)
            if letters and foreign > len(letters) / 2:
                detected = "unsupported"
        if language is None and detected not in {"en", "unknown"}:
            # Statistical language detection is unreliable for brief feature phrases.
            # Explicit caller-provided language always takes precedence.
            latin = not re.search(r"[^\x00-\x7f\u2000-\u206f]", text)
            if latin and len(ENGLISH_PHRASE.findall(text)) >= 2 and live_pairs(text):
                detected = "unknown"
        if detected not in {"en", "unknown"}:
            return Analysis(
                model_id=self.id,
                taxonomy_version=TAXONOMY_VERSION,
                language=detected,
                sentences=[],
                aspects=[],
                supported=False,
                warnings=["Use an English review for this version."],
            )

        # 1. Preserve the original sentences and their evidence offsets.
        sentences = split_sentences(text, review_id)
        contexts = [
            (sentence, category, context, target, cue)
            for sentence in sentences
            for category, context, target, cue in live_pairs(sentence.text)
        ]
        # 2. The vocabulary selects candidates. DeBERTa decides their polarity.
        pairs = [(category, context, target) for _, category, context, target, _ in contexts]
        predictions = self.backbone.classify(pairs)
        steps = []
        local = defaultdict(list)
        for (sentence, category, context, target, cue), (state, score) in zip(
            contexts, predictions, strict=True
        ):
            local[(sentence.id, category)].append((state, score))
            steps.append(
                InferenceStep(
                    sentence_id=sentence.id,
                    category=category,
                    cue=cue,
                    context=context,
                    target=target,
                    sentiment=state,
                    score=score,
                )
            )
        # 3. Opposing contexts make a mixed aspect. Evidence stays verbatim.
        grouped = defaultdict(list)
        for sentence in sentences:
            for category in CATEGORIES:
                values = local.get((sentence.id, category.id), [])
                if values:
                    grouped[category.id].append(
                        Evidence(
                            sentence_id=sentence.id,
                            text=sentence.text,
                            start=sentence.start,
                            end=sentence.end,
                            sentiment=aggregate_sentiments([s for s, _ in values]),
                            score=sum(p for _, p in values) / len(values),
                        )
                    )
        warnings = self.limitations()
        if detected == "unknown":
            warnings.append(
                "Language identification is uncertain; processed provisionally as English."
            )
        result = Analysis(
            model_id=self.id,
            taxonomy_version=TAXONOMY_VERSION,
            language=detected,
            sentences=sentences,
            inference_steps=steps,
            warnings=warnings,
            aspects=[
                AspectResult(
                    category=category.id,
                    evidence=grouped[category.id],
                    sentiment=aggregate_sentiments([e.sentiment for e in grouped[category.id]]),
                )
                for category in CATEGORIES
                if category.id in grouped
            ],
        )
        # 4. General praise receives its own phone-level result, never a fake aspect.
        if result.supported and not result.aspects and PHONE_REFERENCE.search(text):
            evidence = []
            for sentence in result.sentences:
                state, score = self.backbone.classify(
                    [("general", normalise_context(sentence.text), "phone")]
                )[0]
                evidence.append(
                    Evidence(
                        sentence_id=sentence.id,
                        text=sentence.text,
                        start=sentence.start,
                        end=sentence.end,
                        sentiment=state,
                        score=score,
                    )
                )
            if evidence:
                result.general_opinion = GeneralOpinion(
                    sentiment=aggregate_sentiments([e.sentiment for e in evidence]),
                    evidence=evidence,
                )
        return result
