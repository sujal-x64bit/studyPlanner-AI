from datetime import date


def calculate_exam_urgency(exam_date):
    """
    Returns an urgency score from 0 to 100
    based on how close the exam is.
    """

    if exam_date is None:
        return 10

    if isinstance(exam_date, str):
        exam_date = date.fromisoformat(exam_date)

    today = date.today()
    days_remaining = (exam_date - today).days

    if days_remaining <= 3:
        return 100
    elif days_remaining <= 7:
        return 85
    elif days_remaining <= 14:
        return 70
    elif days_remaining <= 30:
        return 50
    else:
        return 25


def calculate_difficulty_score(difficulty):
    """
    Converts difficulty from 1-5 into 0-100.
    """

    if difficulty is None:
        difficulty = 3

    difficulty = max(1, min(difficulty, 5))

    return (difficulty / 5) * 100


def calculate_knowledge_gap(mastery_level):
    """
    Calculates how much of the topic
    still needs to be learned.
    """

    if mastery_level is None:
        mastery_level = 0

    mastery_level = max(0, min(mastery_level, 100))

    return 100 - mastery_level


def calculate_priority(
    exam_date=None,
    difficulty=3,
    mastery_level=0
):
    """
    Final priority calculation.
    Returns a score from 0-100.
    """

    exam_urgency = calculate_exam_urgency(exam_date)

    difficulty_score = calculate_difficulty_score(difficulty)

    knowledge_gap = calculate_knowledge_gap(mastery_level)

    priority_score = (
        exam_urgency * 0.40
        + difficulty_score * 0.25
        + knowledge_gap * 0.35
    )

    return round(priority_score, 2)


def get_priority_category(score):
    """
    Converts numerical priority into a category.
    """

    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"