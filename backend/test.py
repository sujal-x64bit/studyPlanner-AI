from priority_engine import (
    calculate_priority,
    get_priority_category
)


score = calculate_priority(
    exam_date="2026-09-05",
    difficulty=4,
    mastery_level=20
)

category = get_priority_category(score)

print("Priority Score:", score)
print("Priority Category:", category)