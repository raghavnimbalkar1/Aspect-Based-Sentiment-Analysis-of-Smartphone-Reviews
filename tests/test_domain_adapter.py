"""Scope fixtures exercise policy behaviour, not corpus accuracy."""

from types import SimpleNamespace

import pytest

from smartphone_absa.models.checkpoints import TRANSFER_ID
from smartphone_absa.models.domain_adapter import DOMAIN_ID, DomainABSA, domain_pairs
from smartphone_absa.models.registry import ModelRegistry


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Camera and screen look excellent.", {"camera", "display"}),
        ("Battery, screen and camera are good.", {"battery", "display", "camera"}),
        ("The phone has responsive software and good speed.", {"software", "performance"}),
        ("Shipping was fast.", set()),
        ("A fast charger with slow charging speed.", {"charging"}),
        ("The volume rocker is awkward.", {"build"}),
        ("The camera resolution is poor.", {"camera"}),
        ("The display resolution is sharp.", {"display"}),
        ("My SIM card cannot connect to Verizon.", {"connectivity"}),
        ("Bixby is annoying.", {"software"}),
        ("The portrait shows water.", set()),
        ("Water damage ruined it.", {"build"}),
    ],
)
def test_candidates_follow_domain_and_context(text, expected):
    assert {category for category, _, _ in domain_pairs(text)} == expected


def test_shared_predicate_and_independent_opinions_keep_their_scope():
    shared = domain_pairs("The camera and screen are not good.")
    assert all(clause == "The camera and screen are not good." for _, clause, _ in shared)
    pairs = domain_pairs("The display is good and the camera is awful.")
    assert {category: clause for category, clause, _ in pairs} == {
        "display": "The display is good",
        "camera": "the camera is awful.",
    }
    coordinated = domain_pairs("The battery and camera are good and the screen is poor.")
    assert next(clause for category, clause, _ in coordinated if category == "battery") == (
        "The battery and camera are good"
    )


def test_domain_analyzer_uses_shared_classifier_and_original_evidence():
    seen = []

    def classify(pairs):
        seen.extend(pairs)
        return [("negative" if "awful" in clause else "positive", 0.8) for _, clause, _ in pairs]

    backbone = SimpleNamespace(classify=classify)
    model = DomainABSA(backbone)
    text = "  The screen and camera are good. The screen is awful."
    result = model.analyse(text, language="en")
    assert {item.category: item.sentiment for item in result.aspects} == {
        "display": "mixed",
        "camera": "positive",
    }
    assert model.backbone is backbone and seen
    for aspect in result.aspects:
        for evidence in aspect.evidence:
            assert text[evidence.start : evidence.end] == evidence.text
    assert not model.analyse("यह अच्छा है", language="hi").supported


def test_registry_reuses_one_backbone_for_both_adapters(tmp_path, monkeypatch):
    registry = ModelRegistry(tmp_path)
    backbone = SimpleNamespace(classify=lambda pairs: [])
    registry.loaded[TRANSFER_ID] = backbone
    describe = registry.describe
    monkeypatch.setattr(
        registry,
        "describe",
        lambda mid: {**describe(mid), "available": True} if mid == DOMAIN_ID else describe(mid),
    )
    adapter = registry.get(DOMAIN_ID)
    assert adapter.backbone is registry.get(TRANSFER_ID) is backbone
    assert registry.get(DOMAIN_ID) is adapter
    assert registry.describe(DOMAIN_ID)["shared_backbone"] == TRANSFER_ID
