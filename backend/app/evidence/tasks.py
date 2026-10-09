"""Task-based work: being paid to like videos, rate hotels, or review products.

No genuine employer pays for likes, ratings, or "prepaid tasks"; it is the opening
move of the task scam, which asks for money a few tasks later. The model labels a
claim as a task scheme; this check confirms the excerpt really describes one.
"""

import re

TASK_WORK = re.compile(
    r"\b(like|likes|liking|subscribe|subscribing|follow|following|rate|rating|ratings|review|reviews|"
    r"5[- ]star|five[- ]star|prepaid|merchant|task|tasks|thumbs[- ]up|youtube|google maps|hotel|"
    r"product boost|order grabbing|recharge task)\b",
    re.I,
)


def is_task_scheme(text: str) -> bool:
    return bool(TASK_WORK.search(text))
