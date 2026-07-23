from app.core.quality import assess_answer_quality, heuristic_quality_score


def test_empty_answer_scores_zero() -> None:
    assert heuristic_quality_score("") == 0.0


def test_refusal_like_answer_scores_low() -> None:
    assert heuristic_quality_score("I cannot answer that.") == 0.40


def test_short_answer_scores_below_default_threshold() -> None:
    assert heuristic_quality_score("Use a cache.") == 0.65


def test_quality_assessment_explains_short_answer() -> None:
    assessment = assess_answer_quality("Use a cache.")

    assert assessment.score == 0.65
    assert assessment.label == "short"
    assert "concise" in assessment.reason


def test_quality_assessment_detects_needs_input_answer() -> None:
    assessment = assess_answer_quality("I don't see enough context. Please provide the text.")

    assert assessment.score == 0.45
    assert assessment.label == "needs_input"


def test_truncated_answer_is_not_mistaken_for_complete_answer() -> None:
    assessment = assess_answer_quality(
        "This answer contains enough words to look complete to the normal quality "
        "heuristic, but the provider stopped generating it at the configured limit.",
        truncated=True,
    )

    assert assessment.score == 0.30
    assert assessment.label == "truncated"
    assert "output-token limit" in assessment.reason


def test_reasonable_answer_scores_above_default_threshold() -> None:
    answer = (
        "A routing gateway can reduce cost by checking cache first, selecting a "
        "small model for simple prompts, and escalating difficult requests only "
        "when quality checks indicate the first answer is not strong enough."
    )

    assert heuristic_quality_score(answer) == 0.92
