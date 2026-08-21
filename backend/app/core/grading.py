"""Keyword-based grading used when AI grading is unavailable. Deliberately
simple and transparent rather than a black box, since it's a fallback."""


def keyword_grade(student_answer: str, rubric_keywords: str) -> tuple[int, str]:
    keywords = [k.strip().lower() for k in rubric_keywords.split(",") if k.strip()]
    if not keywords:
        return 0, "No rubric available for this question."

    answer_lower = student_answer.lower()
    hits = [k for k in keywords if k in answer_lower]
    score = round(100 * len(hits) / len(keywords))

    if not hits:
        feedback = "Your answer didn't clearly cover the key points expected here. Compare it with the model answer."
    elif len(hits) == len(keywords):
        feedback = "Strong answer — it touches on all the key points expected for this question."
    else:
        missing = [k for k in keywords if k not in hits]
        feedback = f"Good start. Consider also addressing: {', '.join(missing[:3])}."

    return score, feedback
