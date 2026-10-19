"""The single label mapping shared by annotation, models, and the application."""

from dataclasses import dataclass
from enum import StrEnum

TAXONOMY_VERSION = "smartphone-v1"


class Sentiment(StrEnum):
    ABSENT = "absent"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


LABELS = tuple(state.value for state in Sentiment)
PRESENT_LABELS = LABELS[1:]


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    description: str
    cues: tuple[str, ...]


CATEGORIES = (
    Category(
        "battery",
        "Battery",
        "battery endurance, drain and standby time",
        (r"batter(?:y|ies)", r"standby", r"(?:lasts?|lasting) (?:all|a full|the whole) day"),
    ),
    Category(
        "charging",
        "Charging",
        "charging speed, charging ports and wireless charging",
        (r"charg(?:e|es|ing|er)", r"usb[ -]?c", r"charging port"),
    ),
    Category(
        "camera",
        "Camera",
        "photo, video and camera quality",
        (
            r"cameras?",
            r"photos?",
            r"pictures?",
            r"selfies?",
            r"night shots?",
            r"video(?:s| recording)?",
        ),
    ),
    Category(
        "display",
        "Display",
        "screen brightness, colours and touch response",
        (r"screens?", r"displays?", r"touchscreen", r"amoled"),
    ),
    Category(
        "performance",
        "Performance & thermals",
        "speed, lag, gaming and heat",
        (
            r"performance",
            r"lag(?:s|gy|ging)?",
            r"slow",
            r"fast",
            r"gaming",
            r"games?",
            r"overheat(?:s|ing)?",
            r"(?:gets?|runs?|running) hot",
            r"processors?",
            r"multitask\w*",
        ),
    ),
    Category(
        "software",
        "Software",
        "operating system, updates, interface and software bugs",
        (
            r"software",
            r"android",
            r"ios",
            r"updates?",
            r"bloatware",
            r"interface",
            r"operating system",
            r"apps?",
            r"bugs?",
        ),
    ),
    Category(
        "build",
        "Build & design",
        "materials, durability, weight, size and ergonomics",
        (
            r"design",
            r"build",
            r"durab\w*",
            r"lightweight",
            r"heavy",
            r"weight",
            r"ergonomic\w*",
            r"plastic",
            r"metal",
            r"comfortable",
        ),
    ),
    Category(
        "audio",
        "Audio",
        "speakers, microphone and call sound quality",
        (r"speakers?", r"microphones?", r"sound", r"audio", r"headphones?", r"volume"),
    ),
    Category(
        "connectivity",
        "Connectivity",
        "cellular signal, Wi-Fi, Bluetooth and GPS",
        (
            r"wi[ -]?fi",
            r"bluetooth",
            r"gps",
            r"signal",
            r"reception",
            r"network",
            r"dropped calls?",
            r"connectivity",
            r"5g",
            r"4g",
            r"lte",
        ),
    ),
    Category(
        "value",
        "Value",
        "price satisfaction, affordability and value for money",
        (r"price", r"value", r"money", r"expensive", r"cheap", r"affordable", r"worth"),
    ),
)
CATEGORY_IDS = tuple(category.id for category in CATEGORIES)
CATEGORY_BY_ID = {category.id: category for category in CATEGORIES}


def aggregate_sentiments(states: list[str]) -> str:
    """Combine evidence once per review/category, without counting absent as neutral."""
    present = set(states) - {Sentiment.ABSENT}
    if Sentiment.MIXED in present or {Sentiment.POSITIVE, Sentiment.NEGATIVE} <= present:
        return Sentiment.MIXED
    if Sentiment.POSITIVE in present:
        return Sentiment.POSITIVE
    if Sentiment.NEGATIVE in present:
        return Sentiment.NEGATIVE
    return Sentiment.NEUTRAL if present else Sentiment.ABSENT
