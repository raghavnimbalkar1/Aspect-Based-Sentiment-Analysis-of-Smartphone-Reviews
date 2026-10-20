"""Versioned domain candidates; sentiment still comes from the unchanged checkpoint."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from smartphone_absa.models.checkpoints import REVISION
from smartphone_absa.models.inference import TransferredABSA

CONFIG_PATH = Path(__file__).with_name("aspects_v2.json")
CONFIG = json.loads(CONFIG_PATH.read_text())
CONFIG_SHA256 = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
# Include the policy code as well as its vocabulary in the model identity.
ADAPTER_SHA256 = hashlib.sha256(
    CONFIG_PATH.read_bytes() + b"\n" + Path(__file__).read_bytes()
).hexdigest()
DOMAIN_ID = f"deberta-domain-v2-{REVISION[:8]}-{ADAPTER_SHA256[:8]}"
PATTERNS = {
    category: re.compile(r"\b(?:" + "|".join(item["cues"]) + r")\b", re.I)
    for category, item in CONFIG["categories"].items()
}
PREDICATE = re.compile(CONFIG["scope"]["predicate"], re.I)
RETAIL = re.compile(r"\b(?:delivery|shipping|arriv\w*|seller|packag\w*)\b", re.I)


def clauses(text: str) -> list[str]:
    """Keep coordinated nouns with their shared predicate; split complete opinions."""
    result = []
    for clause in re.split(CONFIG["scope"]["contrast"], text, flags=re.I):
        current = ""
        for part in re.split(r"\band\b", clause, flags=re.I):
            part = part.strip()
            subject = RETAIL.search(part) or any(p.search(part) for p in PATTERNS.values())
            if current and PREDICATE.search(current) and subject and PREDICATE.search(part):
                result.append(current.strip())
                current = part
            else:
                current = f"{current} and {part}" if current else part
        if current.strip():
            result.append(current.strip())
    return result


def valid_cue(category: str, match: re.Match, clause: str) -> bool:
    cue = match.group().lower()
    before, after = clause[: match.start()], clause[match.end() :]
    if category == "audio" and cue == "volume":
        return not re.match(r"\s+(?:button|key|switch|rocker)", after, re.I)
    if category == "display" and cue == "resolution":
        explicit_display = re.search(
            r"\b(?:screen|display|touchscreen|amoled|oled)\b", clause, re.I
        )
        return bool(explicit_display) or not PATTERNS["camera"].search(clause)
    if category == "performance" and cue in {"fast", "slow", "speed"}:
        if RETAIL.search(clause) and not re.search(
            r"\b(?:phone|device|processor|performance|gaming)\b", clause, re.I
        ):
            return False
        if re.search(
            r"(?:charg\w*|internet|download|network)\s+(?:speed\s+)?(?:is\s+)?$", before, re.I
        ):
            return False
        if re.match(r"\s+(?:charg\w*|delivery|shipping|internet|download)", after, re.I):
            return False
    return True


def domain_pairs(text: str) -> list[tuple[str, str, str]]:
    pairs = []
    for clause in clauses(text):
        for category, pattern in PATTERNS.items():
            if any(valid_cue(category, match, clause) for match in pattern.finditer(clause)):
                pairs.append((category, clause, CONFIG["categories"][category]["target"]))
    return pairs


class DomainABSA(TransferredABSA):
    def __init__(self, backbone: TransferredABSA):
        self.id = DOMAIN_ID
        self.backbone = backbone

    def candidate_pairs(self, text: str) -> list[tuple[str, str, str]]:
        return domain_pairs(text)

    def classify(self, pairs: list[tuple[str, str, str]]) -> list[tuple[str, float]]:
        return self.backbone.classify(pairs)

    def limitations(self) -> list[str]:
        return [
            "Domain adapter v2 over the transferred checkpoint; no smartphone fine-tuning.",
            "Domain vocabulary and clause heuristics can miss or misassign implicit aspects.",
            "Adapter designed after diagnostic error inspection; "
            "diagnostic scores are development results.",
            "Mixed combines opposing clause predictions; scores are uncalibrated.",
        ]
