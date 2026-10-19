import pytest

from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.taxonomy import aggregate_sentiments
from smartphone_absa.text import split_sentences


@pytest.fixture(scope="module")
def model():
    return RuleBaseline()


def labels(model, text):
    return {
        aspect.category: aspect.sentiment for aspect in model.analyse(text, language="en").aspects
    }


def test_opposing_aspects_do_not_share_sentence_sentiment(model):
    assert labels(model, "The camera is excellent but the battery is terrible.") == {
        "camera": "positive",
        "battery": "negative",
    }


def test_different_aspects_on_either_side_of_and(model):
    result = labels(model, "The screen is bright and the phone gets hot while gaming.")
    assert result["display"] == "positive"
    assert result["performance"] == "negative"


def test_same_aspect_can_have_mixed_evidence(model):
    assert (
        labels(model, "Daylight photos look good but night shots are awful.")["camera"] == "mixed"
    )


def test_negation_and_absence(model):
    result = labels(model, "The battery is not good.")
    assert result == {"battery": "negative"}
    assert labels(model, "Great phone!") == {}


def test_fast_shipping_does_not_become_phone_performance(model):
    assert labels(model, "Fast delivery, excellent seller.") == {}


def test_charging_fast_does_not_become_performance(model):
    result = labels(model, "It charges very fast.")
    assert result["charging"] == "positive"
    assert "performance" not in result


def test_factual_aspect_is_not_absent(model):
    assert labels(model, "It has a USB-C charging port.")["charging"] == "neutral"


def test_evidence_uses_original_offsets_and_preserves_unicode(model):
    text = "  Nice phone!\nThe camera is excellent.  Battery is bad. 🙂"
    result = model.analyse(text, language="en")
    for aspect in result.aspects:
        for evidence in aspect.evidence:
            assert text[evidence.start : evidence.end] == evidence.text
    for sentence in split_sentences(text):
        assert text[sentence.start : sentence.end] == sentence.text


def test_non_english_does_not_generate_feature_results(model):
    result = model.analyse("La batería es muy mala y la cámara no funciona.", language="es")
    assert not result.supported
    assert not result.aspects


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (["positive", "neutral"], "positive"),
        (["negative", "neutral"], "negative"),
        (["positive", "negative"], "mixed"),
        (["mixed", "neutral"], "mixed"),
        (["absent"], "absent"),
        (["neutral"], "neutral"),
    ],
)
def test_review_aggregation(states, expected):
    assert aggregate_sentiments(states) == expected
