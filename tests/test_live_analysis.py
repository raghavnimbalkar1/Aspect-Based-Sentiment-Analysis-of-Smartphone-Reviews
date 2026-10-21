"""Live-review behaviour tests. Synthetic fixtures are not independent accuracy data."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.models.checkpoints import TRANSFER_ID
from smartphone_absa.models.domain_adapter import DOMAIN_ID
from smartphone_absa.models.live import LIVE_ID, LiveABSA, live_pairs, opinion_spans
from smartphone_absa.models.registry import ModelRegistry


@pytest.mark.parametrize(
    ("text", "categories"),
    [
        ("Charging is painfully slow.", {"charging"}),
        ("The phone dies after two hours.", {"battery"}),
        ("It lasts three days.", {"battery"}),
        ("The charger is slow but the processor is fast.", {"charging", "performance"}),
        ("The camera is great, the battery is terrible.", {"camera", "battery"}),
        ("The camera and screen are good.", {"camera", "display"}),
        ("The volume buttons are flimsy.", {"build"}),
        ("Shipping was fast and the seller was excellent.", set()),
        ("The phone is responsive while charging.", {"performance", "charging"}),
        ("The battery charges quickly but drains too fast.", {"battery", "charging"}),
        ("The apps open instantly.", {"performance"}),
        (
            "The battery easily lasts two full days of heavy use, "
            "and the 120Hz display is super smooth and bright",
            {"battery", "display"},
        ),
        ("The plastic back feels cheap.", {"build"}),
        ("This phone is heavy and expensive.", {"build", "value"}),
        ("The battery lasts all day under heavy usage.", {"battery"}),
        ("Battery life is decent, although it drains quickly on 5G.", {"battery"}),
        ("Battery drains quickly but the 5G signal is weak.", {"battery", "connectivity"}),
        ("The camera is excellent but slow to focus.", {"camera"}),
        ("The camera is fast to focus.", {"camera"}),
        ("The phone is fast but the camera is slow to focus.", {"camera", "performance"}),
        ("My main focus is software updates.", {"software"}),
        ("The camera is good but slow phone performance ruins it.", {"camera", "performance"}),
    ],
)
def test_live_candidate_scope(text, categories):
    assert {category for category, _, _, _ in live_pairs(text)} == categories


def test_live_trace_matches_actual_decisions_and_original_offsets():
    seen = []

    def classify(pairs):
        seen.extend(pairs)
        return [
            ("negative" if "terrible" in context or "isn't" in context else "positive", 0.8)
            for _, context, _ in pairs
        ]

    model = LiveABSA(SimpleNamespace(classify=classify))
    text = "  The camera isn’t good. The camera is excellent, the battery is terrible."
    result = model.analyse(text, language="en")
    assert {a.category: a.sentiment for a in result.aspects} == {
        "camera": "mixed",
        "battery": "negative",
    }
    assert len(result.inference_steps) == len(seen) == 3
    assert result.inference_steps[0].context == "The camera isn't good."
    for aspect in result.aspects:
        for evidence in aspect.evidence:
            assert text[evidence.start : evidence.end] == evidence.text
    for step in result.inference_steps:
        assert text[step.start : step.end].replace("’", "'") == step.context
    assert result.general_opinion is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Great camera, awful battery, excellent speakers.",
            ["Great camera", "awful battery", "excellent speakers."],
        ),
        ("The camera, screen and battery are good.", ["The camera, screen and battery are good."]),
        ("The camera and screen are good.", ["The camera and screen are good."]),
        (
            "The battery is great; the camera is poor.",
            ["The battery is great", "the camera is poor."],
        ),
        ("Camera is great, but battery is poor.", ["Camera is great", "battery is poor."]),
        (
            "The battery lasts all day and the screen is bright and smooth.",
            ["The battery lasts all day", "the screen is bright and smooth."],
        ),
    ],
)
def test_independent_opinion_spans_preserve_shared_nouns(text, expected):
    assert [text[start:end] for start, end in opinion_spans(text)] == expected


def test_opposing_clauses_keep_their_own_evidence_and_original_offsets():
    def classify(pairs):
        return [("negative" if "awful" in text else "positive", 0.9) for _, text, _ in pairs]

    text = "  The camera is excellent in daylight, but the camera is awful at night.  "
    model = LiveABSA(SimpleNamespace(classify=classify))
    result = model.analyse(text, language="en")
    assert len(result.sentences) == 1
    assert result.aspects[0].sentiment == "mixed"
    evidence = result.aspects[0].evidence
    assert [item.sentiment for item in evidence] == ["positive", "negative"]
    assert [item.text for item in evidence] == [
        "The camera is excellent in daylight",
        "the camera is awful at night.",
    ]
    assert all(text[e.start : e.end] == e.text for e in evidence)
    assert all(e.sentence_id == result.sentences[0].id for e in evidence)


def test_battery_target_does_not_invent_an_endurance_claim():
    pairs = live_pairs("The phone has a 5000mAh battery.")
    assert pairs == [("battery", "The phone has a 5000mAh battery.", "battery", "battery")]


def test_omitted_single_feature_is_resolved_without_rewriting_evidence():
    seen = []

    def classify(pairs):
        seen.extend(pairs)
        return [("negative" if "awful" in text else "positive", 0.9) for _, text, _ in pairs]

    text = "The camera is excellent in daylight but awful at night."
    result = LiveABSA(SimpleNamespace(classify=classify)).analyse(text, language="en")
    assert result.aspects[0].sentiment == "mixed"
    assert result.aspects[0].evidence[1].text == "awful at night."
    assert seen[1] == ("camera", "camera: awful at night.", "camera")
    assert result.inference_steps[1].cue == "camera (previous clause)"
    assert (
        text[result.inference_steps[1].start : result.inference_steps[1].end] == "awful at night."
    )
    # Do not guess which of two named features an omitted opinion concerns.
    assert len(live_pairs("The camera and display are good but awful outdoors.")) == 2
    assert len(live_pairs("The camera is good but awful shipping.")) == 1


def test_em_dash_opinions_keep_independent_source_spans():
    text = "Wonderful battery — it died halfway through my first call."
    assert [text[a:b] for a, b in opinion_spans(text)] == [
        "Wonderful battery",
        "it died halfway through my first call.",
    ]


def test_elliptical_context_and_conditional_negation_keep_targets_and_evidence():
    pairs = live_pairs("The display is bright but not outdoors.")
    assert pairs[1][:3] == ("display", "screen: not outdoors.", "screen")
    pairs = live_pairs("The camera is great and so is the display.")
    assert pairs[1][:3] == ("display", "The camera is great and so is the display.", "screen")
    assert len(live_pairs("The camera is great but awful phone.")) == 1


def test_general_phone_opinion_survives_alongside_feature_sentences():
    def classify(pairs):
        return [("negative" if "hate" in context else "positive", 0.9) for _, context, _ in pairs]

    text = "I hate this phone. The camera is excellent. It arrived late."
    result = LiveABSA(SimpleNamespace(classify=classify)).analyse(text, language="en")
    assert result.general_opinion.sentiment == "negative"
    assert [item.text for item in result.general_opinion.evidence] == ["I hate this phone."]
    assert result.aspects[0].category == "camera"
    assert result.aspects[0].sentiment == "positive"


def test_general_opinion_never_invents_an_aspect():
    seen = []

    def classify(pairs):
        seen.extend(pairs)
        return [("positive", 0.9) for _ in pairs]

    model = LiveABSA(SimpleNamespace(classify=classify))
    result = model.analyse("I love this phone!", language="en")
    assert result.aspects == [] and result.inference_steps == []
    assert result.general_opinion.sentiment == "positive"
    assert result.general_opinion.evidence[0].text == "I love this phone!"
    assert seen == [("general", "I love this phone!", "phone")]
    result = model.analyse("Shipping was excellent.", language="en")
    assert result.aspects == [] and result.general_opinion is None


def test_unsupported_language_does_not_run_a_classifier():
    def classify(pairs):
        raise AssertionError("Unsupported input must not reach inference")

    model = LiveABSA(SimpleNamespace(classify=classify))
    assert not model.analyse("यह फोन बहुत अच्छा है", language="hi").supported
    assert not model.analyse("This phone is good", language="hi").supported
    assert not model.analyse("बहुत अच्छा").supported


def test_short_english_language_recovery_is_provisional(monkeypatch):
    monkeypatch.setattr("smartphone_absa.models.live.detect_language", lambda text: "ro")
    model = LiveABSA(SimpleNamespace(classify=lambda pairs: [("positive", 0.8)] * len(pairs)))
    result = model.analyse("The battery life is excellent.")
    assert result.supported and result.language == "unknown"
    assert result.aspects[0].category == "battery"
    assert any("uncertain" in warning for warning in result.warnings)


def test_concurrent_analyses_do_not_share_request_state():
    def classify(pairs):
        return [("negative" if "terrible" in text else "positive", 0.8) for _, text, _ in pairs]

    model = LiveABSA(SimpleNamespace(classify=classify))
    inputs = ["The camera is excellent.", "The battery is terrible."] * 10
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda text: model.analyse(text, language="en"), inputs))
    assert [r.aspects[0].category for r in results] == ["camera", "battery"] * 10
    assert [r.inference_steps[0].sentiment for r in results] == ["positive", "negative"] * 10


def test_live_model_is_versioned_and_reuses_the_pinned_backbone(tmp_path, monkeypatch):
    registry = ModelRegistry(tmp_path)
    backbone = SimpleNamespace(classify=lambda pairs: [("positive", 0.8)] * len(pairs))
    registry.loaded[TRANSFER_ID] = backbone
    describe = registry.describe
    monkeypatch.setattr(
        registry,
        "describe",
        lambda mid: {**describe(mid), "available": True} if mid == LIVE_ID else describe(mid),
    )
    adapter = registry.get(LIVE_ID)
    assert adapter.backbone is backbone
    assert registry.get(LIVE_ID) is adapter
    assert DOMAIN_ID == "deberta-domain-v2-10c9dff3-b377506c"
    spec = registry.describe(LIVE_ID)
    assert spec["recommended_for_live"] and spec["adapter_version"] == 3
    assert spec["shared_backbone"] == TRANSFER_ID
    assert spec["smartphone_finetuned"] is False
    assert len([s for s in registry.specs() if s.get("recommended_for_live")]) == 1
    with TestClient(create_app(tmp_path / "workspace.sqlite3", registry=registry)) as client:
        payload = {"text": "The camera is excellent.", "model": LIVE_ID}
        result = client.post("/api/analyse", json=payload)
        assert result.status_code == 200
        assert result.json()["model_id"] == LIVE_ID
        assert result.json()["inference_steps"][0]["sentiment"] == "positive"
        assert all("path" not in row for row in client.get("/api/models").json())
