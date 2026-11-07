"""Welche Aufgabe als Nächstes kommt.

Schwache und frisch falsche Typen kommen öfter, sichere seltener.
Eine gerade falsche Aufgabe kommt wieder, aber nicht als unmittelbare nächste.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from mathe.tasks import build_task, revive_task, task_signature, task_type_key


def skill_weight(correct: int, wrong: int, fresh: bool) -> float:
    weight = 1.0 + ((wrong + 1) / (correct + 1)) * 2.0
    if fresh:
        weight *= 2.4
    if correct >= 4 and wrong == 0:
        weight *= 0.3
    elif correct >= 3 and correct >= wrong * 3:
        weight *= 0.5
    return weight


def replay_choice(opened: list[dict], recent: list[str], last_was_replay: bool) -> str | None:
    if last_was_replay or not opened:
        return None
    previous = recent[0] if recent else None
    for item in opened:
        if item["signature"] != previous:
            return item["signature"]
    return None


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def choose_focus(rows: list[dict]) -> str | None:
    if not rows or random.random() < 0.3:
        return None
    now = datetime.now(timezone.utc)
    weighted = []
    for row in rows:
        last = row.get("last_wrong_at")
        fresh = False
        if last is not None and int(row.get("wrong") or 0) > 0:
            fresh = now - _aware(last) < timedelta(minutes=45)
        weight = skill_weight(int(row["correct"]), int(row["wrong"]), fresh)
        if weight >= 1.2:
            weighted.append((row["skill"], weight))
    if not weighted:
        return None
    skills = [skill for skill, _weight in weighted]
    weights = [weight for _skill, weight in weighted]
    return random.choices(skills, weights=weights, k=1)[0]


def next_task(user_id: int, mode: str, grade: int, recent: list[str], last_was_replay: bool):
    from mathe.db import open_mistakes, skill_stats_for

    opened = open_mistakes(user_id, grade, mode)
    wanted = replay_choice(opened, recent, last_was_replay)
    if wanted:
        for item in opened:
            if item["signature"] == wanted:
                return revive_task(item["snapshot"]), True
    avoid = set(recent[:1])
    focus = choose_focus(skill_stats_for(user_id, grade, mode))
    for _ in range(24):
        candidate = build_task(mode, grade)
        if task_signature(candidate) in avoid:
            continue
        if focus and task_type_key(candidate) != focus:
            continue
        return candidate, False
    for _ in range(12):
        candidate = build_task(mode, grade)
        if task_signature(candidate) not in avoid:
            return candidate, False
    return build_task(mode, grade), False
