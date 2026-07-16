from dataclasses import dataclass


@dataclass(frozen=True)
class QualityAssessment:
    score: float
    label: str
    reason: str


def assess_answer_quality(answer: str) -> QualityAssessment:
    if not answer or not answer.strip():
        return QualityAssessment(
            score=0.0,
            label="empty",
            reason="Answer is empty.",
        )

    lower_answer = answer.lower()
    refusal_phrases = [
        "i cannot answer",
        "i can't answer",
        "as an ai model",
        "unable to help",
    ]
    needs_input_phrases = [
        "i don't see",
        "i don't know",
        "i am not sure",
        "please provide",
        "provide more",
        "need more context",
    ]

    if any(phrase in lower_answer for phrase in refusal_phrases):
        return QualityAssessment(
            score=0.40,
            label="refusal",
            reason="Answer appears to refuse or avoid the request.",
        )

    if any(phrase in lower_answer for phrase in needs_input_phrases):
        return QualityAssessment(
            score=0.45,
            label="needs_input",
            reason="Answer asks for more information instead of completing the request.",
        )

    if len(answer.split()) < 20:
        return QualityAssessment(
            score=0.65,
            label="short",
            reason="Answer is concise and may be too thin for high-quality targets.",
        )

    return QualityAssessment(
        score=0.92,
        label="complete",
        reason="Answer has enough substance for the current heuristic quality check.",
    )


def heuristic_quality_score(answer: str) -> float:
    return assess_answer_quality(answer).score
