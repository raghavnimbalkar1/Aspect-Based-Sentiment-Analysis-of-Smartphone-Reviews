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
from smartphone_absa.models.domain_adapter import (
    ADAPTER_SHA256,
    PATTERNS,
    PREDICATE,
    RETAIL,
    DomainABSA,
    valid_cue,
)
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
ELLIPTICAL_OPINION = re.compile(
    r"^(?:(?:it|they)\s+(?:is|are|was|were)\s+)?"
    r"(?:(?:not|very|really|quite|too|so)\s+)*"
    r"(?:good|great|excellent|amazing|bad|awful|terrible|horrible|poor|"
    r"bright|dim|blurry|sharp|slow|fast|smooth|weak|strong|disappointing)\b",
    re.I,
)


def normalise_context(text: str) -> str:
    """Normalise typographic punctuation for inference, never for saved evidence."""
    return text.translate(str.maketrans({"’": "'", "‘": "'", "‑": "-", "–": "-"}))


def opinion_spans(text: str) -> list[tuple[int, int]]:
    """Split independent opinions, preserving shared subjects and exact source offsets."""

    def has_subject(part: str) -> bool:
        return bool(RETAIL.search(part) or any(p.search(part) for p in PATTERNS.values()))

    def trim(start: int, end: int) -> tuple[int, int]:
        while start < end and (text[start].isspace() or text[start] in ",;"):
            start += 1
        while end > start and (text[end - 1].isspace() or text[end - 1] in ",;"):
            end -= 1
        return start, end

    # Contrast and semicolons separate opinions even when an aspect is implicit.
    boundaries = list(
        re.finditer(r"\b(?:but|however|although|yet|whereas)\b|[;\n—]|\s+–\s+", text, re.I)
    )
    spans = []
    start = 0
    for boundary in [*boundaries, None]:
        end = boundary.start() if boundary else len(text)
        current = start
        for join in re.finditer(r",\s*(?:and\s+)?|\band\b", text[start:end], re.I):
            left_end, right_start = start + join.start(), start + join.end()
            left = text[current:left_end]
            # Stop at the next join when checking the right opinion.
            right = re.split(r",|\band\b", text[right_start:end], maxsplit=1, flags=re.I)[0]
            if (
                has_subject(left)
                and has_subject(right)
                and (
                    PREDICATE.search(left)
                    and (join.group().startswith(",") or PREDICATE.search(right))
                )
            ):
                a, b = trim(current, left_end)
                if a < b:
                    spans.append((a, b))
                current = right_start
        a, b = trim(current, end)
        if a < b:
            spans.append((a, b))
        start = boundary.end() if boundary else end
    return spans


def live_candidates(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """Category, classifier context, target, cue and verbatim context span."""
    from smartphone_absa.models.domain_adapter import (
        CONFIG as ORIGINAL_CONFIG,
    )

    pairs = []
    previous = []
    for start, end in opinion_spans(text):
        part = normalise_context(text[start:end])
        before = len(pairs)
        if part:
            for category, pattern in PATTERNS.items():
                matches = [m for m in pattern.finditer(part) if valid_cue(category, m, part)]
                if category == "build":
                    # Workload and game graphics describe use, not the phone's weight.
                    matches = [
                        m
                        for m in matches
                        if not (
                            m.group().lower() == "heavy"
                            and re.match(
                                r"\s+(?:use|usage|workload|gaming|games?|multitasking)\b",
                                part[m.end() :],
                                re.I,
                            )
                        )
                    ]
                if category == "value" and PATTERNS["build"].search(part):
                    # Cheap-looking material is a build opinion; cheap pricing is value.
                    matches = [
                        m
                        for m in matches
                        if not (
                            m.group().lower() == "cheap"
                            and re.search(
                                r"\b(?:feels?|looks?|plastic|materials?|back|frame)\b", part, re.I
                            )
                            and not re.search(
                                r"\b(?:price|cost|money|value|affordable)\b", part, re.I
                            )
                        )
                    ]
                if category == "connectivity" and ENDURANCE.search(part):
                    # Network use can be the condition of a battery complaint.
                    # "drains on 5G" does not evaluate the connection itself.
                    matches = [
                        m
                        for m in matches
                        if not re.search(
                            r"\b(?:on|using|over|with)\s+(?:the\s+)?$", part[: m.start()], re.I
                        )
                    ]
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
                if category == "battery" and cue.lower() in {"battery", "batteries"}:
                    # Do not turn a capacity specification into an endurance claim.
                    target = cue.lower()
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
                pairs.append((category, part, target, cue, start, end))
        if (
            len(pairs) == before
            and previous
            and ELLIPTICAL_OPINION.search(part)
            and not RETAIL.search(part)
        ):
            # Resolve only an adjective-led fragment after one unambiguous feature.
            # Raw evidence remains intact; the trace exposes the supplied target.
            if len({item[0] for item in previous}) == 1:
                category, _, target, cue, _, _ = previous[-1]
                pairs.append(
                    (category, f"{target}: {part}", target, f"{cue} (previous clause)", start, end)
                )
        previous = pairs[before:]
    return pairs


def live_pairs(text: str) -> list[tuple[str, str, str, str]]:
    """Public candidate inspection without span metadata."""
    return [item[:4] for item in live_candidates(text)]


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
            (sentence, category, context, target, cue, start, end)
            for sentence in sentences
            for category, context, target, cue, start, end in live_candidates(sentence.text)
        ]
        # 2. The vocabulary selects candidates. DeBERTa decides their polarity.
        pairs = [(category, context, target) for _, category, context, target, _, _, _ in contexts]
        predictions = self.backbone.classify(pairs)
        steps = []
        grouped = defaultdict(list)
        for (sentence, category, context, target, cue, start, end), (state, score) in zip(
            contexts, predictions, strict=True
        ):
            grouped[category].append(
                Evidence(
                    sentence_id=sentence.id,
                    text=sentence.text[start:end],
                    start=sentence.start + start,
                    end=sentence.start + end,
                    sentiment=state,
                    score=score,
                )
            )
            steps.append(
                InferenceStep(
                    sentence_id=sentence.id,
                    category=category,
                    cue=cue,
                    context=context,
                    target=target,
                    sentiment=state,
                    score=score,
                    start=sentence.start + start,
                    end=sentence.start + end,
                )
            )
        # 3. Aggregate for the review while keeping each local decision separate.
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
