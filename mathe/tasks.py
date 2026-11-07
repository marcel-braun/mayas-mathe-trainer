"""Aufgaben nach Klassenstufe der deutschen Grundschule.

Die Lösung bleibt in der Session. public_view gibt nur die Anzeige heraus.
"""

from __future__ import annotations

import copy
import json
import math
import random
import re
import secrets

MODES = [
    ("rechnen", "Rechnen", "Du tippst die Zahl selbst.", 1),
    ("wahl", "Multiple Choice", "Tippe die richtige Antwort.", 1),
    ("luecken", "Lückenaufgaben", "Welche Zahl fehlt?", 1),
    ("uhr", "Uhr", "Lies die Uhrzeit.", 2),
    ("geld", "Geld", "Zähle Münzen und Scheine.", 2),
    ("groessen", "Größen", "Längen, Gewicht und Zeit.", 1),
    ("formen", "Formen", "Figuren erkennen.", 1),
    ("ordnen", "Zahlen ordnen", "Vergleichen und sortieren.", 1),
]

MIN_GRADE = {row[0]: row[3] for row in MODES}
LIMIT = {1: 20, 2: 100, 3: 1000, 4: 1_000_000}
PLACE = ["Einer", "Zehner", "Hunderter", "Tausender", "Zehntausender", "Hunderttausender"]

SHAPES = [
    ("kreis", "Kreis"),
    ("dreieck", "Dreieck"),
    ("quadrat", "Quadrat"),
    ("rechteck", "Rechteck"),
]
SHAPE_NAMES = dict(SHAPES)
CORNERS = {"dreieck": 3, "quadrat": 4, "rechteck": 4, "kreis": 0}

ALLOWED = {
    1: {"add", "sub", "compare", "order", "neighbor", "shape", "length_compare"},
    2: {
        "add", "sub", "mul", "compare", "order", "neighbor", "shape",
        "length_cm", "clock", "money",
    },
    3: {
        "add", "sub", "mul", "div_exact", "compare", "order", "neighbor", "shape",
        "length_m", "length_cm", "weight", "clock", "money", "perimeter",
    },
    4: {
        "add", "sub", "mul", "div_exact", "div_rest", "compare", "order", "neighbor",
        "shape", "length_m", "length_cm", "length_km", "weight", "clock", "money",
        "perimeter", "area", "fraction", "time_span", "written_add", "written_sub",
    },
}

FRACTION_WORDS = [
    (1, 2, "Die Hälfte", "ist"),
    (1, 4, "Ein Viertel", "ist"),
    (1, 3, "Ein Drittel", "ist"),
    (2, 3, "Zwei Drittel", "sind"),
    (3, 4, "Drei Viertel", "sind"),
    (2, 4, "Zwei Viertel", "sind"),
]
FRACTION_PICTURES = [
    (1, 2, "ein Halb"),
    (1, 3, "ein Drittel"),
    (1, 4, "ein Viertel"),
    (2, 3, "zwei Drittel"),
    (3, 4, "drei Viertel"),
]


def mode_info(mode: str) -> dict | None:
    for mid, title, text, min_grade in MODES:
        if mid == mode:
            return {
                "id": mid,
                "title": title,
                "text": text,
                "min_grade": min_grade,
            }
    return None


def fmt(number: int) -> str:
    value = int(number)
    sign = "-" if value < 0 else ""
    return sign + f"{abs(value):,}".replace(",", ".")


def fmt_euro(cents: int) -> str:
    cents = int(cents)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d} €"


def parse_int_de(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip().replace(" ", "").replace("\u00a0", "")
    if not text or "," in text:
        return None
    if "." in text:
        parts = text.split(".")
        if not parts[0].isdigit() or not all(part.isdigit() and len(part) == 3 for part in parts[1:]):
            return None
        text = "".join(parts)
    if not text.isdigit():
        return None
    return int(text)


def parse_euro_cents(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip().lower().replace("€", "").replace("euro", "")
    text = text.replace(" ", "").replace("\u00a0", "")
    if not text or text.count(",") > 1:
        return None
    if "," in text:
        left, right = text.split(",", 1)
        left = left.replace(".", "")
        if not left.isdigit() or not right.isdigit() or not right or len(right) > 2:
            return None
        return int(left) * 100 + int(right.ljust(2, "0"))
    if text.count(".") > 1:
        return None
    if text.count(".") == 1:
        left, right = text.split(".")
        if not left.isdigit() or not right.isdigit() or not right or len(right) > 2:
            return None
        return int(left) * 100 + int(right.ljust(2, "0"))
    if not text.isdigit():
        return None
    return int(text) * 100


def pick(pairs: list[tuple[str, int]]) -> str:
    names, weights = zip(*pairs)
    return random.choices(list(names), weights=list(weights), k=1)[0]


def apply_calc(calc: tuple) -> int:
    kind = calc[0]
    if kind == "value":
        return int(calc[1])
    if kind == "sum":
        return sum(int(part) for part in calc[1:])
    if kind == "mul":
        value = 1
        for part in calc[1:]:
            value *= int(part)
        return value
    if kind == "sub":
        value = int(calc[1])
        for part in calc[2:]:
            value -= int(part)
        return value
    raise AssertionError(kind)


def clock_angles(hour: int, minute: int) -> tuple[float, float]:
    return (hour % 12) * 30 + minute * 0.5, minute * 6


def clock_phrase(grade: int, hour: int, minute: int) -> str:
    hour = 12 if hour % 12 == 0 else hour % 12
    nxt = 1 if hour == 12 else hour + 1
    if grade >= 4:
        return f"{hour}:{minute:02d} Uhr"
    if minute == 0:
        return f"{hour} Uhr"
    if minute == 15:
        return f"viertel nach {hour}"
    if minute == 30:
        return f"halb {nxt}"
    if minute == 45:
        return f"viertel vor {nxt}"
    raise ValueError(minute)


def shift_clock(hour: int, minute: int, delta: int) -> tuple[int, int]:
    total = ((hour % 12) * 60 + minute + delta) % (12 * 60)
    face, minute = divmod(total, 60)
    return (12 if face == 0 else face), minute


def clock_visual(hour: int, minute: int) -> dict:
    hour_angle, minute_angle = clock_angles(hour, minute)
    marks = []
    for number in range(1, 13):
        rad = math.radians(number * 30)
        marks.append(
            {
                "n": number,
                "x": round(100 + 70 * math.sin(rad), 2),
                "y": round(100 - 70 * math.cos(rad), 2),
            }
        )
    return {
        "type": "clock",
        "hour_angle": round(hour_angle, 2),
        "minute_angle": round(minute_angle, 2),
        "marks": marks,
    }


def column_rows(number: int, width: int) -> list[str]:
    text = str(number)
    return [" "] * (width - len(text)) + list(text)


def column_visual(a: int, b: int, op: str) -> dict:
    width = max(len(str(a)), len(str(b)))
    if op == "-":
        guide = [
            "Beginne rechts bei den Einern.",
            "Wenn oben eine Zahl zu klein ist, leihst du dir 10.",
            "Schreibe nur eine Ziffer auf.",
            "Gehe dann nach links weiter.",
        ]
        symbol = "−"
    else:
        guide = [
            "Beginne rechts bei den Einern.",
            "Schreibe nur eine Ziffer auf.",
            "Den Übertrag nimmst du zur nächsten Stelle mit.",
            "Gehe dann nach links weiter.",
        ]
        symbol = "+"
    return {
        "type": "column",
        "op": symbol,
        "rows": [column_rows(a, width), column_rows(b, width)],
        "guide": guide,
    }


def add_steps(a: int, b: int) -> list[dict]:
    width = max(len(str(a)), len(str(b)), 1)
    top = [int(ch) for ch in f"{a:0{width}d}"]
    bot = [int(ch) for ch in f"{b:0{width}d}"]
    carry = 0
    steps = []
    digits = []
    for index in range(width):
        pos = width - 1 - index
        total = top[pos] + bot[pos] + carry
        write = total % 10
        new_carry = total // 10
        parts = [str(top[pos]), str(bot[pos])]
        if carry:
            parts.append(str(carry))
        steps.append(
            {
                "prompt": f"{PLACE[index]}: {' + '.join(parts)}. Welche Ziffer schreibst du?",
                "help": "Nur eine Ziffer von 0 bis 9. Den Übertrag nimmst du weiter mit.",
                "expect": {"type": "int", "value": write},
            }
        )
        digits.append(write)
        carry = new_carry
    if carry:
        steps.append(
            {
                "prompt": (
                    f"Links kommt noch der Übertrag {carry} dazu. "
                    "Welche Ziffer schreibst du?"
                ),
                "help": "Das ist eine einzelne Ziffer.",
                "expect": {"type": "int", "value": carry},
            }
        )
        digits.append(carry)
    value = int("".join(str(digit) for digit in reversed(digits)))
    if value != a + b:
        raise AssertionError(f"{a}+{b} ergab {value}")
    return steps


def sub_steps(a: int, b: int) -> list[dict]:
    if a < b:
        raise AssertionError("Subtraktion wird negativ")
    width = max(len(str(a)), 1)
    top = [int(ch) for ch in f"{a:0{width}d}"]
    bot = [int(ch) for ch in f"{b:0{width}d}"]
    steps = []
    digits = []
    for index in range(width):
        pos = width - 1 - index
        borrowed = False
        if top[pos] < bot[pos]:
            donor = pos - 1
            while donor >= 0 and top[donor] == 0:
                top[donor] = 9
                donor -= 1
            if donor < 0:
                raise AssertionError("Übertrag fehlgeschlagen")
            top[donor] -= 1
            top[pos] += 10
            borrowed = True
        write = top[pos] - bot[pos]
        if borrowed:
            prompt = (
                f"{PLACE[index]}: Oben ist zu klein. Du leihst dir 10. "
                f"Rechne {top[pos]} − {bot[pos]}. Welche Ziffer schreibst du?"
            )
        else:
            prompt = f"{PLACE[index]}: {top[pos]} − {bot[pos]}. Welche Ziffer schreibst du?"
        steps.append(
            {
                "prompt": prompt,
                "help": "Nur eine Ziffer von 0 bis 9.",
                "expect": {"type": "int", "value": write},
            }
        )
        digits.append(write)
    value = int("".join(str(digit) for digit in reversed(digits)))
    if value != a - b:
        raise AssertionError(f"{a}-{b} ergab {value}")
    return steps


def coin_item(cents: int) -> dict:
    if cents < 100:
        return {
            "kind": "muenze",
            "css": f"c{cents}",
            "text": str(cents),
            "label": f"{cents} Cent",
        }
    euros = cents // 100
    if cents in (100, 200):
        return {
            "kind": "muenze",
            "css": f"e{euros}",
            "text": f"{euros} €",
            "label": f"{euros} Euro",
        }
    return {
        "kind": "schein",
        "css": f"s{euros}",
        "text": f"{euros} €",
        "label": f"{euros} Euro",
    }


def coin_sum(max_cents: int, denoms: list[int], low: int, high: int) -> tuple[list[int], int]:
    want = random.randint(low, high)
    items: list[int] = []
    total = 0
    guard = 0
    while len(items) < want and guard < 40:
        guard += 1
        coin = random.choice(denoms)
        if total + coin <= max_cents:
            items.append(coin)
            total += coin
    if not items:
        coin = min(denoms)
        items = [coin]
        total = coin
    random.shuffle(items)
    return items, total


def number_task(**kwargs) -> dict:
    answer = kwargs.pop("answer")
    task = {
        "input_kind": "number",
        "expect": {"type": "int", "value": int(answer)},
        "placeholder": kwargs.pop("placeholder", "Zahl"),
        "unit": kwargs.pop("unit", ""),
        "title": kwargs.pop("title", ""),
        "prompt": kwargs.pop("prompt"),
        "help": kwargs.pop("help", ""),
        "solution": kwargs.pop("solution"),
        "meta": kwargs.pop("meta"),
        "visual": kwargs.pop("visual", None),
        "choices": [],
    }
    if kwargs:
        raise TypeError(f"unerwartet: {sorted(kwargs)}")
    return task


def euro_task(**kwargs) -> dict:
    cents = int(kwargs.pop("cents"))
    task = number_task(**kwargs, answer=0)
    task["input_kind"] = "euro"
    task["expect"] = {"type": "euro", "cents": cents}
    task["placeholder"] = "0,00"
    task["unit"] = "€"
    return task


def div_task(**kwargs) -> dict:
    quotient = int(kwargs.pop("quotient"))
    remainder = int(kwargs.pop("remainder"))
    task = number_task(**kwargs, answer=quotient)
    task["input_kind"] = "div"
    task["expect"] = {"type": "div", "q": quotient, "r": remainder}
    task["unit"] = ""
    return task


def order_task(**kwargs) -> dict:
    values = [int(value) for value in kwargs.pop("values")]
    task = number_task(**kwargs, answer=values[0])
    task["input_kind"] = "order"
    task["expect"] = {"type": "order", "values": values}
    task["unit"] = ""
    return task


def choice_task(**kwargs) -> dict:
    choices = kwargs.pop("choices")
    correct_id = kwargs.pop("correct_id")
    choice_label = kwargs.pop("choice_label")
    meta = dict(kwargs.pop("meta"))
    meta["choice_label"] = choice_label
    return {
        "input_kind": "choice",
        "expect": {"type": "choice", "id": correct_id},
        "choices": choices,
        "placeholder": "",
        "unit": "",
        "title": kwargs.pop("title", ""),
        "prompt": kwargs.pop("prompt"),
        "help": kwargs.pop("help", ""),
        "solution": kwargs.pop("solution"),
        "meta": meta,
        "visual": kwargs.pop("visual", None),
    }


def int_choices(correct: int, low: int, high: int) -> tuple[list[dict], str]:
    wrongs: list[int] = []
    candidates = []
    for delta in (1, -1, 2, -2, 10, -10, 3, -3, 5, -5, 20, -20, 100, -100, 1000, -1000):
        value = correct + delta
        if value >= 0 and value != correct:
            candidates.append(value)
    random.shuffle(candidates)
    span_low = min(low, max(0, correct - 15))
    span_high = max(high, correct + 15, span_low + 3)
    guard = 0
    pool = candidates[:]
    while len(wrongs) < 3 and guard < 80:
        guard += 1
        if pool:
            value = pool.pop()
        else:
            value = random.randint(span_low, span_high)
        if value != correct and value not in wrongs and value >= 0:
            wrongs.append(value)
    if len(wrongs) < 3:
        raise AssertionError("zu wenige Auswahlmöglichkeiten")
    rows = [(fmt(correct), True)] + [(fmt(value), False) for value in wrongs]
    random.shuffle(rows)
    items = []
    correct_id = None
    seen = set()
    for label, ok in rows:
        if label in seen:
            continue
        seen.add(label)
        cid = secrets.token_hex(4)
        items.append({"id": cid, "label": label})
        if ok:
            correct_id = cid
    if correct_id is None or len(items) < 4:
        raise AssertionError("Auswahl unvollständig")
    return items, correct_id


def label_choices(correct: str, wrongs: list[str], extras: dict | None = None) -> tuple[list[dict], str]:
    extras = extras or {}
    rows = [(correct, True)]
    for label in wrongs:
        if label != correct:
            rows.append((label, False))
    seen = set()
    unique = []
    for label, ok in rows:
        if label in seen:
            continue
        seen.add(label)
        unique.append((label, ok))
    if len(unique) < 2 or sum(1 for _, ok in unique if ok) != 1:
        raise AssertionError("Auswahltexte ungültig")
    random.shuffle(unique)
    items = []
    correct_id = None
    for label, ok in unique:
        cid = secrets.token_hex(4)
        item = {"id": cid, "label": label}
        item.update(extras.get(label) or {})
        items.append(item)
        if ok:
            correct_id = cid
    return items, correct_id


def as_choice(task: dict, low: int, high: int) -> dict:
    correct = int(task["expect"]["value"])
    choices, correct_id = int_choices(correct, low, high)
    label = next(item["label"] for item in choices if item["id"] == correct_id)
    if label != fmt(correct):
        raise AssertionError("Auswahl passt nicht")
    task["input_kind"] = "choice"
    task["choices"] = choices
    task["expect"] = {"type": "choice", "id": correct_id}
    task["unit"] = ""
    task["placeholder"] = ""
    task["meta"]["choice_label"] = label
    return task


def add_pair(limit: int, crossing: bool) -> tuple[int, int, int]:
    if crossing and limit >= 20 and random.random() < 0.65:
        left = random.randint(2, 9)
        low = 11 - left
        high = min(9, limit - left)
        if low <= high:
            right = random.randint(low, high)
            return left, right, left + right
    left = random.randint(0, limit)
    right = random.randint(0, limit - left)
    return left, right, left + right


def sub_pair(limit: int, crossing: bool) -> tuple[int, int, int]:
    if crossing and limit >= 18 and random.random() < 0.65:
        left = random.randint(11, min(18, limit))
        ones = left % 10
        low = ones + 1
        high = min(9, left)
        if low <= high:
            right = random.randint(low, high)
            return left, right, left - right
    left = random.randint(0, limit)
    right = random.randint(0, left)
    return left, right, left - right


def large_pair(op: str) -> tuple[int, int, int]:
    step = random.choice((10, 100, 1000, 10000, 100000))
    if op == "+":
        left = random.randint(0, 1_000_000 // step) * step
        room = (1_000_000 - left) // step
        right = random.randint(0, room) * step
        if left == 0 and right == 0:
            right = step if step <= 1_000_000 else 1
        return left, right, left + right
    left = random.randint(1, 1_000_000 // step) * step
    right = random.randint(0, left // step) * step
    return left, right, left - right


def mul_factors(grade: int) -> tuple[int, int]:
    if grade == 2:
        table = random.choices(
            [2, 5, 10, 3, 4, 6, 7, 8, 9],
            weights=[6, 6, 6, 2, 2, 1, 1, 1, 1],
            k=1,
        )[0]
        other = random.randint(1, 10)
    else:
        table = random.randint(1, 10)
        other = random.randint(1, 10)
    if random.random() < 0.5:
        return table, other
    return other, table


def arith_task(grade: int, kind: str) -> dict:
    if kind == "add":
        if grade >= 4:
            left, right, result = large_pair("+")
        else:
            left, right, result = add_pair(LIMIT[grade], grade == 1)
        prompt = f"{fmt(left)} + {fmt(right)} = ?"
        return number_task(
            prompt=prompt,
            answer=result,
            solution=f"{fmt(left)} + {fmt(right)} = {fmt(result)}",
            meta={
                "skill": "add",
                "a": left,
                "b": right,
                "op": "+",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    if kind == "sub":
        if grade >= 4:
            left, right, result = large_pair("-")
        else:
            left, right, result = sub_pair(LIMIT[grade], grade == 1)
        prompt = f"{fmt(left)} − {fmt(right)} = ?"
        return number_task(
            prompt=prompt,
            answer=result,
            solution=f"{fmt(left)} − {fmt(right)} = {fmt(result)}",
            meta={
                "skill": "sub",
                "a": left,
                "b": right,
                "op": "-",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    if kind == "mul":
        left, right = mul_factors(grade)
        result = left * right
        return number_task(
            prompt=f"{left} · {right} = ?",
            answer=result,
            solution=f"{left} · {right} = {result}",
            meta={
                "skill": "mul",
                "a": left,
                "b": right,
                "op": "·",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    if kind == "div":
        divisor = random.randint(1, 10)
        quotient = random.randint(1, 10)
        dividend = divisor * quotient
        return number_task(
            prompt=f"{dividend} : {divisor} = ?",
            answer=quotient,
            solution=f"{dividend} : {divisor} = {quotient}",
            meta={
                "skill": "div_exact",
                "dividend": dividend,
                "divisor": divisor,
                "quotient": quotient,
                "result": quotient,
                "remainder": 0,
                "numbers": [dividend, divisor, quotient],
            },
        )
    raise AssertionError(kind)


def simple_kind(grade: int) -> str:
    if grade == 1:
        return pick([("add", 55), ("sub", 45)])
    if grade == 2:
        return pick([("add", 30), ("sub", 25), ("mul", 45)])
    if grade == 3:
        return pick([("add", 30), ("sub", 25), ("mul", 25), ("div", 20)])
    return pick([("add", 34), ("sub", 34), ("mul", 32)])


def div_rest_parts() -> dict:
    divisor = random.randint(2, 9)
    quotient = random.randint(1, 12)
    remainder = random.randint(1, divisor - 1)
    dividend = quotient * divisor + remainder
    return {
        "dividend": dividend,
        "divisor": divisor,
        "q": quotient,
        "r": remainder,
    }


def written_numbers(op: str) -> tuple[int, int]:
    digits = random.choice((2, 3))
    low = 10 ** (digits - 1)
    high = 10**digits - 1
    if op == "+":
        return random.randint(low, high), random.randint(low, high)
    left = random.randint(low + 1, high)
    right = random.randint(1, left - 1)
    return left, right


def build_written(op: str, interactive: bool) -> dict:
    left, right = written_numbers(op)
    result = left + right if op == "+" else left - right
    skill = "written_add" if op == "+" else "written_sub"
    title = "Schriftlich addieren" if op == "+" else "Schriftlich subtrahieren"
    symbol = "+" if op == "+" else "−"
    visual = column_visual(left, right, op)
    meta = {
        "skill": skill,
        "a": left,
        "b": right,
        "op": op,
        "result": result,
        "numbers": [left, right, result],
    }
    solution = f"{fmt(left)} {symbol} {fmt(right)} = {fmt(result)}"
    if interactive:
        steps = add_steps(left, right) if op == "+" else sub_steps(left, right)
        return {
            "title": title,
            "prompt": "Rechne Stelle für Stelle.",
            "help": "",
            "input_kind": "number",
            "placeholder": "0",
            "unit": "",
            "steps": steps,
            "step_index": 0,
            "choices": [],
            "visual": visual,
            "solution": solution,
            "meta": meta,
        }
    low = max(0, result - 80)
    high = result + 80
    choices, correct_id = int_choices(result, low, high)
    return choice_task(
        title=title,
        prompt="Was kommt heraus?",
        help="Rechne Stelle für Stelle, von den Einern nach links.",
        choices=choices,
        correct_id=correct_id,
        choice_label=fmt(result),
        solution=solution,
        meta=meta,
        visual=visual,
    )


def build_div_rest(as_mc: bool) -> dict:
    parts = div_rest_parts()
    prompt = f"{parts['dividend']} : {parts['divisor']} = ?"
    solution = (
        f"{parts['dividend']} : {parts['divisor']} = {parts['q']} Rest {parts['r']}"
    )
    meta = {
        "skill": "div_rest",
        "dividend": parts["dividend"],
        "divisor": parts["divisor"],
        "q": parts["q"],
        "r": parts["r"],
        "result": parts["q"],
        "numbers": [parts["dividend"], parts["divisor"], parts["q"], parts["r"]],
    }
    if not as_mc:
        return div_task(
            prompt=prompt,
            help="Schreibe das Ergebnis und den Rest. Der Rest ist kleiner als die Zahl, durch die du teilst.",
            quotient=parts["q"],
            remainder=parts["r"],
            solution=solution,
            meta=meta,
        )
    correct = f"{parts['q']} Rest {parts['r']}"
    wrongs = []
    for label in (
        f"{parts['q']} Rest {parts['r'] + 1}",
        f"{parts['q'] + 1} Rest {parts['r']}",
        f"{parts['q'] + 1} Rest 0",
        f"{max(parts['q'] - 1, 0)} Rest {parts['r']}",
        f"{parts['q']} Rest {max(parts['r'] - 1, 0)}",
        f"{parts['q'] + 2} Rest {parts['r']}",
    ):
        if label != correct and label not in wrongs:
            wrongs.append(label)
        if len(wrongs) == 3:
            break
    choices, correct_id = label_choices(correct, wrongs)
    return choice_task(
        prompt=prompt,
        help="Achte auf den Rest.",
        choices=choices,
        correct_id=correct_id,
        choice_label=correct,
        solution=solution,
        meta=meta,
    )


def gap_from(kind: str, grade: int) -> dict:
    if kind == "add":
        if grade >= 4:
            left, right, result = large_pair("+")
        else:
            left, right, result = add_pair(LIMIT[grade], grade == 1)
        if random.choice((True, False)):
            prompt = f"□ + {fmt(right)} = {fmt(result)}"
            answer = left
        else:
            prompt = f"{fmt(left)} + □ = {fmt(result)}"
            answer = right
        return number_task(
            prompt=prompt,
            help="Welche Zahl fehlt?",
            answer=answer,
            solution=f"{fmt(left)} + {fmt(right)} = {fmt(result)}",
            meta={
                "skill": "add",
                "a": left,
                "b": right,
                "op": "+",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    if kind == "sub":
        if grade >= 4:
            left, right, result = large_pair("-")
        else:
            left, right, result = sub_pair(LIMIT[grade], grade == 1)
        if random.choice((True, False)):
            prompt = f"□ − {fmt(right)} = {fmt(result)}"
            answer = left
        else:
            prompt = f"{fmt(left)} − □ = {fmt(result)}"
            answer = right
        return number_task(
            prompt=prompt,
            help="Welche Zahl fehlt?",
            answer=answer,
            solution=f"{fmt(left)} − {fmt(right)} = {fmt(result)}",
            meta={
                "skill": "sub",
                "a": left,
                "b": right,
                "op": "-",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    if kind == "mul":
        left, right = mul_factors(grade)
        result = left * right
        if random.choice((True, False)):
            prompt = f"□ · {right} = {result}"
            answer = left
        else:
            prompt = f"{left} · □ = {result}"
            answer = right
        return number_task(
            prompt=prompt,
            help="Welche Zahl fehlt?",
            answer=answer,
            solution=f"{left} · {right} = {result}",
            meta={
                "skill": "mul",
                "a": left,
                "b": right,
                "op": "·",
                "result": result,
                "numbers": [left, right, result],
            },
        )
    divisor = random.randint(1, 10)
    quotient = random.randint(1, 10)
    dividend = divisor * quotient
    if random.choice((True, False)):
        prompt = f"□ : {divisor} = {quotient}"
        answer = dividend
    else:
        prompt = f"{dividend} : □ = {quotient}"
        answer = divisor
    return number_task(
        prompt=prompt,
        help="Welche Zahl fehlt?",
        answer=answer,
        solution=f"{dividend} : {divisor} = {quotient}",
        meta={
            "skill": "div_exact",
            "dividend": dividend,
            "divisor": divisor,
            "quotient": quotient,
            "result": quotient,
            "remainder": 0,
            "numbers": [dividend, divisor, quotient, answer],
        },
    )


def build_rechnen(grade: int) -> dict:
    if grade == 4:
        kind = pick(
            [
                ("add", 18),
                ("sub", 18),
                ("wadd", 20),
                ("wsub", 20),
                ("divrest", 16),
                ("mul", 8),
            ]
        )
        if kind == "wadd":
            return build_written("+", True)
        if kind == "wsub":
            return build_written("-", True)
        if kind == "divrest":
            return build_div_rest(False)
        return arith_task(grade, kind)
    return arith_task(grade, simple_kind(grade))


def fraction_of_task() -> dict:
    num, den, words, verb = random.choice(FRACTION_WORDS)
    whole = den * random.randint(1, 8)
    result = num * (whole // den)
    prompt = f"{words} von {whole} {verb} …"
    return number_task(
        prompt=prompt,
        answer=result,
        solution=f"{words} von {whole} {verb} {result}.",
        meta={
            "skill": "fraction",
            "result": result,
            "numbers": [num, den, whole, result],
            "calc": ("mul", num, whole // den),
        },
    )


def fraction_name_task() -> dict:
    num, den, words = random.choice(FRACTION_PICTURES)
    correct = f"{num}/{den} {words}"
    wrongs = [f"{n}/{d} {word}" for n, d, word in FRACTION_PICTURES if (n, d) != (num, den)]
    random.shuffle(wrongs)
    choices, correct_id = label_choices(correct, wrongs[:3])
    return choice_task(
        prompt="Welcher Bruch ist das?",
        choices=choices,
        correct_id=correct_id,
        choice_label=correct,
        solution=f"Das ist {correct}.",
        meta={"skill": "fraction", "fraction_num": num, "fraction_den": den},
        visual={"type": "fraction", "num": num, "den": den},
    )


def fraction_picture_task() -> dict:
    options = FRACTION_PICTURES[:]
    random.shuffle(options)
    chosen = options[:4]
    target = random.choice(chosen)
    letters = ["A", "B", "C", "D"]
    items = []
    correct_id = None
    correct_letter = ""
    for index, (num, den, words) in enumerate(chosen):
        cid = secrets.token_hex(4)
        items.append(
            {
                "id": cid,
                "label": letters[index],
                "fraction": {"num": num, "den": den},
                "aria": f"Bild {letters[index]}",
            }
        )
        if (num, den) == (target[0], target[1]):
            correct_id = cid
            correct_letter = letters[index]
    return choice_task(
        prompt=f"Welches Bild zeigt {target[2]}?",
        choices=items,
        correct_id=correct_id,
        choice_label=correct_letter,
        solution=f"Bild {correct_letter} zeigt {target[2]}.",
        meta={
            "skill": "fraction",
            "fraction_num": target[0],
            "fraction_den": target[1],
            "picture": True,
        },
    )


def build_fraction() -> dict:
    kind = pick([("of", 40), ("name", 30), ("picture", 30)])
    if kind == "of":
        task = fraction_of_task()
        return as_choice(task, 0, max(20, task["expect"]["value"] + 12))
    if kind == "name":
        return fraction_name_task()
    return fraction_picture_task()


def build_wahl(grade: int) -> dict:
    if grade == 4:
        kind = pick(
            [
                ("fraction", 30),
                ("written", 25),
                ("divrest", 20),
                ("arith", 25),
            ]
        )
        if kind == "fraction":
            return build_fraction()
        if kind == "written":
            return build_written(random.choice(("+", "-")), False)
        if kind == "divrest":
            return build_div_rest(True)
    task = arith_task(grade, simple_kind(grade))
    return as_choice(task, 0, max(LIMIT[min(grade, 3)], task["expect"]["value"] + 15))


def build_luecken(grade: int) -> dict:
    if grade == 1:
        kind = pick([("add", 55), ("sub", 45)])
    elif grade == 2:
        kind = pick([("add", 30), ("sub", 25), ("mul", 45)])
    elif grade == 3:
        kind = pick([("add", 25), ("sub", 20), ("mul", 30), ("div", 25)])
    else:
        kind = pick([("add", 25), ("sub", 20), ("mul", 20), ("div", 15), ("divrest", 20)])
        if kind == "divrest":
            return build_div_rest(False)
    return gap_from(kind, grade)


def build_uhr(grade: int) -> dict:
    hour = random.randint(1, 12)
    if grade == 2:
        minute = random.choice((0, 30))
        deltas = (30, -30, 60, -60, 120, 15, -15)
    elif grade == 3:
        minute = random.choice((0, 15, 30, 45))
        deltas = (15, -15, 30, -30, 60, -60, 45, -45)
    else:
        minute = random.choice(tuple(range(0, 60, 5)))
        deltas = (5, -5, 10, -10, 15, -15, 30, -30, 60, -60)
    label = clock_phrase(grade, hour, minute)
    wrongs: list[str] = []
    for delta in deltas:
        other_hour, other_minute = shift_clock(hour, minute, delta)
        if grade == 2 and other_minute not in (0, 30):
            continue
        if grade == 3 and other_minute not in (0, 15, 30, 45):
            continue
        other = clock_phrase(grade, other_hour, other_minute)
        if other != label and other not in wrongs:
            wrongs.append(other)
    guard = 0
    while len(wrongs) < 3 and guard < 40:
        guard += 1
        if grade == 2:
            other_hour, other_minute = random.randint(1, 12), random.choice((0, 30))
        elif grade == 3:
            other_hour, other_minute = random.randint(1, 12), random.choice((0, 15, 30, 45))
        else:
            other_hour, other_minute = random.randint(1, 12), random.choice(tuple(range(0, 60, 5)))
        other = clock_phrase(grade, other_hour, other_minute)
        if other != label and other not in wrongs:
            wrongs.append(other)
    choices, correct_id = label_choices(label, wrongs[:3])
    return choice_task(
        prompt="Wie viel Uhr ist es?",
        choices=choices,
        correct_id=correct_id,
        choice_label=label,
        solution=f"Es ist {label}.",
        meta={"skill": "clock", "hour": hour, "minute": minute},
        visual=clock_visual(hour, minute),
    )


def build_geld(grade: int) -> dict:
    if grade == 2:
        coins, total = coin_sum(100, [1, 2, 5, 10, 20, 50], 2, 5)
        return number_task(
            prompt="Wie viele Cent sind das?",
            help="Zähle alle Münzen zusammen.",
            answer=total,
            unit="Cent",
            placeholder="0",
            solution=f"Das sind {total} Cent.",
            visual={"type": "coins", "items": [coin_item(coin) for coin in coins]},
            meta={
                "skill": "money",
                "kind": "cent",
                "coins": coins,
                "total_cents": total,
                "numbers": coins + [total],
            },
        )
    if grade >= 4 and random.random() < 0.5:
        paid = random.choice((500, 1000, 2000, 5000))
        price = random.randrange(10, paid, 10)
        change = paid - price
        return euro_task(
            prompt="Wie viel Euro bekommst du zurück?",
            help="Mit Komma, zum Beispiel 3,50.",
            cents=change,
            solution=f"Du bekommst {fmt_euro(change)} zurück.",
            visual={
                "type": "wechsel",
                "price": fmt_euro(price),
                "note": coin_item(paid),
            },
            meta={
                "skill": "money",
                "kind": "change",
                "price_cents": price,
                "paid_cents": paid,
                "total_cents": change,
                "numbers": [price, paid, change],
            },
        )
    if grade == 3:
        denoms = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
        cap = 2000
    else:
        denoms = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        cap = 5000
    coins, total = coin_sum(cap, denoms, 2, 4)
    return euro_task(
        prompt="Wie viel Euro sind das?",
        help="Mit Komma, zum Beispiel 3,50.",
        cents=total,
        solution=f"Das sind {fmt_euro(total)}.",
        visual={"type": "coins", "items": [coin_item(coin) for coin in coins]},
        meta={
            "skill": "money",
            "kind": "count",
            "coins": coins,
            "total_cents": total,
            "numbers": coins + [total],
        },
    )


def measure_task(prompt: str, answer: int, unit: str, solution: str, meta: dict, visual=None, help_text: str = "") -> dict:
    meta = dict(meta)
    meta["result"] = answer
    return number_task(
        prompt=prompt,
        help=help_text,
        answer=answer,
        unit=unit,
        solution=solution,
        meta=meta,
        visual=visual,
    )


def build_groessen(grade: int) -> dict:
    if grade == 1:
        if random.random() < 0.28:
            width = random.choice((36, 52, 70, 88))
            left = right = width
            correct = "Beide gleich lang"
        else:
            left = random.randint(28, 96)
            right = random.randint(28, 96)
            while abs(left - right) < 28:
                right = random.randint(28, 96)
            correct = "Band A" if left > right else "Band B"
        wrongs = [label for label in ("Band A", "Band B", "Beide gleich lang") if label != correct]
        choices, correct_id = label_choices(correct, wrongs)
        return choice_task(
            prompt="Welches Band ist länger?",
            choices=choices,
            correct_id=correct_id,
            choice_label=correct,
            solution=f"Richtig ist {correct}.",
            visual={"type": "compare", "a": left, "b": right},
            meta={"skill": "length_compare", "a": left, "b": right, "numbers": [left, right]},
        )
    if grade == 2:
        if random.random() < 0.55:
            length = random.randint(1, 10)
            return measure_task(
                "Wie viele Zentimeter ist der Streifen lang?",
                length,
                "cm",
                f"Der Streifen ist {length} cm lang.",
                {"skill": "length_cm", "calc": ("value", length), "numbers": [length]},
                visual={"type": "ruler", "cm": length, "max_cm": 10},
                help_text="Lies die Zahl am Ende des Streifens ab.",
            )
        left = random.randint(1, 12)
        right = random.randint(1, 18 - left)
        total = left + right
        return measure_task(
            f"{left} cm + {right} cm = ?",
            total,
            "cm",
            f"{left} cm + {right} cm = {total} cm",
            {"skill": "length_cm", "calc": ("sum", left, right), "numbers": [left, right, total]},
        )
    if grade == 3:
        kind = pick([("m", 25), ("mix", 25), ("back", 15), ("kg", 20), ("gmix", 15)])
        if kind == "m":
            meters = random.randint(1, 9)
            answer = meters * 100
            return measure_task(
                f"Wie viele Zentimeter sind {meters} m?",
                answer,
                "cm",
                f"{meters} m sind {answer} cm.",
                {"skill": "length_m", "calc": ("mul", meters, 100), "numbers": [meters, answer]},
            )
        if kind == "mix":
            meters = random.randint(1, 5)
            cm = random.choice((10, 20, 25, 40, 50, 75))
            answer = meters * 100 + cm
            return measure_task(
                f"Wie viele Zentimeter sind {meters} m und {cm} cm?",
                answer,
                "cm",
                f"{meters} m und {cm} cm sind {answer} cm.",
                {"skill": "length_m", "calc": ("sum", meters * 100, cm), "numbers": [meters, cm, answer]},
            )
        if kind == "back":
            meters = random.randint(1, 9)
            cm = meters * 100
            return measure_task(
                f"Wie viele Meter sind {cm} cm?",
                meters,
                "m",
                f"{cm} cm sind {meters} m.",
                {"skill": "length_m", "calc": ("value", meters), "numbers": [cm, meters]},
            )
        if kind == "kg":
            kg = random.randint(1, 9)
            grams = kg * 1000
            return measure_task(
                f"Wie viele Gramm sind {kg} kg?",
                grams,
                "g",
                f"{kg} kg sind {grams} g.",
                {"skill": "weight", "calc": ("mul", kg, 1000), "numbers": [kg, grams]},
            )
        kg = random.randint(1, 4)
        grams = random.choice((100, 200, 250, 500, 750))
        answer = kg * 1000 + grams
        return measure_task(
            f"Wie viele Gramm sind {kg} kg und {grams} g?",
            answer,
            "g",
            f"{kg} kg und {grams} g sind {answer} g.",
            {"skill": "weight", "calc": ("sum", kg * 1000, grams), "numbers": [kg, grams, answer]},
        )
    kind = pick([("km", 18), ("kmm", 18), ("mkm", 12), ("kg", 14), ("time", 20), ("span", 18)])
    if kind == "km":
        km = random.randint(1, 9)
        meters = km * 1000
        return measure_task(
            f"Wie viele Meter sind {km} km?",
            meters,
            "m",
            f"{km} km sind {fmt(meters)} m.",
            {"skill": "length_km", "calc": ("mul", km, 1000), "numbers": [km, meters]},
        )
    if kind == "kmm":
        km = random.randint(1, 5)
        meters = random.choice((100, 200, 250, 500, 750))
        answer = km * 1000 + meters
        return measure_task(
            f"Wie viele Meter sind {km} km und {meters} m?",
            answer,
            "m",
            f"{km} km und {meters} m sind {fmt(answer)} m.",
            {"skill": "length_km", "calc": ("sum", km * 1000, meters), "numbers": [km, meters, answer]},
        )
    if kind == "mkm":
        km = random.randint(2, 9)
        meters = km * 1000
        return measure_task(
            f"Wie viele Kilometer sind {fmt(meters)} m?",
            km,
            "km",
            f"{fmt(meters)} m sind {km} km.",
            {"skill": "length_km", "calc": ("value", km), "numbers": [meters, km]},
        )
    if kind == "kg":
        kg = random.randint(1, 6)
        grams = random.choice((0, 250, 500, 750))
        if grams == 0:
            answer = kg * 1000
            prompt = f"Wie viele Gramm sind {kg} kg?"
            solution = f"{kg} kg sind {fmt(answer)} g."
            calc = ("mul", kg, 1000)
        else:
            answer = kg * 1000 + grams
            prompt = f"Wie viele Gramm sind {kg} kg und {grams} g?"
            solution = f"{kg} kg und {grams} g sind {fmt(answer)} g."
            calc = ("sum", kg * 1000, grams)
        return measure_task(
            prompt,
            answer,
            "g",
            solution,
            {"skill": "weight", "calc": calc, "numbers": [kg, grams, answer]},
        )
    if kind == "time":
        hours = random.randint(1, 5)
        extra = random.choice((0, 15, 30, 45))
        answer = hours * 60 + extra
        if extra == 0:
            prompt = f"Wie viele Minuten sind {hours} Stunden?"
            solution = f"{hours} Stunden sind {answer} Minuten."
            calc = ("mul", hours, 60)
        else:
            prompt = f"Wie viele Minuten sind {hours} Stunden und {extra} Minuten?"
            solution = f"{hours} Stunden und {extra} Minuten sind {answer} Minuten."
            calc = ("sum", hours * 60, extra)
        return measure_task(
            prompt,
            answer,
            "Minuten",
            solution,
            {"skill": "time_span", "calc": calc, "numbers": [hours, extra, answer]},
        )
    start_h = random.randint(8, 15)
    start_m = random.choice((0, 10, 15, 20, 30, 45))
    delta = random.choice((15, 20, 30, 40, 45, 60, 75, 90))
    end_total = start_h * 60 + start_m + delta
    end_h, end_m = divmod(end_total, 60)
    return measure_task(
        f"Von {start_h}:{start_m:02d} Uhr bis {end_h}:{end_m:02d} Uhr. Wie viele Minuten sind das?",
        delta,
        "Minuten",
        f"Das sind {delta} Minuten.",
        {
            "skill": "time_span",
            "calc": ("value", delta),
            "start_min": start_h * 60 + start_m,
            "end_min": end_total,
            "numbers": [start_h, start_m, end_h, end_m, delta],
        },
    )


def shape_choices(correct_name: str) -> tuple[list[dict], str, str]:
    correct = SHAPE_NAMES[correct_name]
    wrongs = [label for name, label in SHAPES if name != correct_name]
    extras = {label: {"shape": name} for name, label in SHAPES}
    choices, correct_id = label_choices(correct, wrongs, extras)
    return choices, correct_id, correct


def build_formen(grade: int) -> dict:
    if grade == 1:
        if random.random() < 0.7:
            name = random.choice(tuple(SHAPE_NAMES))
            choices, correct_id, label = shape_choices(name)
            return choice_task(
                prompt="Wie heißt diese Form?",
                choices=choices,
                correct_id=correct_id,
                choice_label=label,
                solution=f"Das ist ein {label}.",
                visual={"type": "shape", "name": name},
                meta={"skill": "shape", "shape": name, "choice_shape": name},
            )
        if random.choice((True, False)):
            name, prompt = "kreis", "Welche Form ist rund?"
        else:
            name, prompt = "dreieck", "Welche Form hat drei Ecken?"
        choices, correct_id, label = shape_choices(name)
        return choice_task(
            prompt=prompt,
            choices=choices,
            correct_id=correct_id,
            choice_label=label,
            solution=f"Das ist ein {label}.",
            meta={"skill": "shape", "shape": name, "choice_shape": name},
        )
    if grade == 2:
        kind = pick([("ecken", 45), ("rund", 20), ("drei", 20), ("quadrat", 15)])
        if kind == "ecken":
            name = random.choice(("dreieck", "quadrat", "rechteck"))
            corners = CORNERS[name]
            return number_task(
                prompt="Wie viele Ecken hat diese Form?",
                answer=corners,
                solution=f"Die Form hat {corners} Ecken.",
                visual={"type": "shape", "name": name},
                meta={"skill": "shape", "shape": name, "result": corners, "numbers": [corners]},
            )
        if kind == "rund":
            name, prompt = "kreis", "Welche Form ist rund?"
        elif kind == "drei":
            name, prompt = "dreieck", "Welche Form hat drei Ecken?"
        else:
            name, prompt = "quadrat", "Welche Form hat vier gleich lange Seiten?"
        choices, correct_id, label = shape_choices(name)
        return choice_task(
            prompt=prompt,
            choices=choices,
            correct_id=correct_id,
            choice_label=label,
            solution=f"Das ist ein {label}.",
            meta={"skill": "shape", "shape": name, "choice_shape": name},
        )
    if grade == 3:
        length = random.randint(2, 10)
        width = random.randint(2, 10)
        result = 2 * (length + width)
        return measure_task(
            "Wie viele Zentimeter hat der Umfang?",
            result,
            "cm",
            f"Der Umfang ist {result} cm.",
            {
                "skill": "perimeter",
                "l": length,
                "w": width,
                "calc": ("mul", 2, length + width),
                "numbers": [length, width, result],
            },
            visual={"type": "rect", "l": length, "w": width},
            help_text="Der Umfang ist einmal rundherum, alle Seiten zusammen.",
        )
    length = random.randint(2, 12)
    width = random.randint(2, 12)
    result = length * width
    return measure_task(
        "Wie viele Quadratzentimeter hat die Fläche?",
        result,
        "cm²",
        f"Die Fläche ist {result} cm².",
        {
            "skill": "area",
            "l": length,
            "w": width,
            "calc": ("mul", length, width),
            "numbers": [length, width, result],
        },
        visual={"type": "rect", "l": length, "w": width},
        help_text="Fläche = Länge mal Breite.",
    )


def sample_number(grade: int, low: int = 0, high: int | None = None) -> int:
    limit = LIMIT[grade]
    if high is None:
        high = limit
    high = min(limit, high)
    low = max(0, min(low, high))
    if grade <= 3 or random.random() < 0.25:
        return random.randint(low, high)
    step = random.choice((1, 10, 100, 1000))
    start = math.ceil(low / step)
    end = math.floor(high / step)
    if end < start:
        return random.randint(low, high)
    return random.randint(start, end) * step


def order_numbers(grade: int, count: int) -> list[int]:
    if grade < 4:
        return random.sample(range(0, LIMIT[grade] + 1), count)
    for _ in range(25):
        style = random.choice(("place", "near", "wide"))
        if style == "place":
            digit = random.randint(1, 9)
            pool = [digit * 10**power for power in range(0, 6)]
            pool = [number for number in pool if number <= 1_000_000]
            if len(pool) >= count:
                return random.sample(pool, count)
        elif style == "near":
            base = random.randint(1000, 900000)
            pool = {base}
            shifts = (-3000, -400, -40, -3, 3, 40, 400, 3000, 20, -20)
            guard = 0
            while len(pool) < count and guard < 30:
                guard += 1
                pool.add(min(1_000_000, max(0, base + random.choice(shifts))))
            if len(pool) >= count:
                return random.sample(list(pool), count)
        else:
            digits = random.choice((3, 4, 5))
            low = 10 ** (digits - 1)
            high = min(1_000_000, 10**digits - 1)
            return random.sample(range(low, high + 1), count)
    return random.sample(range(0, 10001), count)


def build_ordnen(grade: int) -> dict:
    kind = pick([("compare", 40), ("order", 35), ("neighbor", 25)])
    if kind == "neighbor":
        if random.choice(("nach", "vor")) == "nach":
            number = sample_number(grade, 0, LIMIT[grade] - 1)
            answer = number + 1
            prompt = f"Welche Zahl kommt direkt nach {fmt(number)}?"
            direction = "nach"
        else:
            number = sample_number(grade, 1, LIMIT[grade])
            answer = number - 1
            prompt = f"Welche Zahl kommt direkt vor {fmt(number)}?"
            direction = "vor"
        return number_task(
            prompt=prompt,
            answer=answer,
            solution=f"Die Zahl ist {fmt(answer)}.",
            meta={
                "skill": "neighbor",
                "n": number,
                "direction": direction,
                "result": answer,
                "numbers": [number, answer],
            },
        )
    if kind == "order":
        count = 3 if grade == 1 else 4
        numbers = order_numbers(grade, count)
        ordered = sorted(numbers)
        shuffled = numbers[:]
        random.shuffle(shuffled)
        if shuffled == ordered:
            shuffled = list(reversed(ordered))
            if shuffled == ordered:
                shuffled = ordered[1:] + ordered[:1]
        return order_task(
            prompt="Tippe die Zahlen von klein nach groß.",
            help="Du kannst sie auch mit Komma schreiben.",
            values=ordered,
            placeholder="2, 5, 9",
            solution="Von klein nach groß sind " + ", ".join(fmt(number) for number in ordered) + ".",
            visual={
                "type": "order",
                "numbers": [{"value": number, "label": fmt(number)} for number in shuffled],
            },
            meta={"skill": "order", "numbers": numbers, "result_list": ordered},
        )
    if random.random() < 0.22:
        number = sample_number(grade)
        choices, correct_id = label_choices("Ja, gleich groß", ["Nein"])
        return choice_task(
            prompt="Sind diese Zahlen gleich groß?",
            choices=choices,
            correct_id=correct_id,
            choice_label="Ja, gleich groß",
            solution="Die Zahlen sind gleich groß.",
            visual={"type": "numbers", "numbers": [fmt(number), fmt(number)]},
            meta={"skill": "compare", "numbers": [number, number], "question": "eq"},
        )
    left, right = order_numbers(grade, 2)
    greater = random.choice((True, False))
    prompt = "Welche Zahl ist größer?" if greater else "Welche Zahl ist kleiner?"
    correct_number = max(left, right) if greater else min(left, right)
    other = min(left, right) if greater else max(left, right)
    choices, correct_id = label_choices(fmt(correct_number), [fmt(other), "Gleich groß"])
    word = "größere" if greater else "kleinere"
    return choice_task(
        prompt=prompt,
        choices=choices,
        correct_id=correct_id,
        choice_label=fmt(correct_number),
        solution=f"Die {word} Zahl ist {fmt(correct_number)}.",
        visual={"type": "numbers", "numbers": [fmt(left), fmt(right)]},
        meta={
            "skill": "compare",
            "numbers": [left, right],
            "question": "gt" if greater else "lt",
        },
    )


BUILDERS = {
    "rechnen": build_rechnen,
    "wahl": build_wahl,
    "luecken": build_luecken,
    "uhr": build_uhr,
    "geld": build_geld,
    "groessen": build_groessen,
    "formen": build_formen,
    "ordnen": build_ordnen,
}


def current_expect(task: dict) -> dict:
    if task.get("steps"):
        return task["steps"][task["step_index"]]["expect"]
    return task["expect"]


def public_view(task: dict) -> dict:
    if task.get("steps"):
        current = task["steps"][task["step_index"]]
        prompt = current["prompt"]
        help_text = current.get("help", "")
        step = {"n": task["step_index"] + 1, "total": len(task["steps"])}
        input_kind = current.get("input_kind", "number")
    else:
        prompt = task["prompt"]
        help_text = task.get("help", "")
        step = None
        input_kind = task["input_kind"]
    visual = copy.deepcopy(task["visual"]) if task.get("visual") else None
    from mathe.coach import build_coach

    view = {
        "token": task["token"],
        "title": task.get("title") or "",
        "prompt": prompt,
        "help": help_text,
        "input_kind": input_kind,
        "choices": task.get("choices") or [],
        "visual": visual,
        "step": step,
        "placeholder": task.get("placeholder") or "",
        "unit": task.get("unit") or "",
        "prompt_size": "md" if len(prompt) > 24 else "xl",
    }
    view["coach"] = build_coach(task)
    return view


def _match(expect: dict, form: dict, task: dict) -> tuple[str, str]:
    kind = expect["type"]
    if kind == "int":
        raw = (form.get("answer") or "").strip()
        if raw == "":
            return "empty", "Schreib eine Zahl in das Feld."
        value = parse_int_de(raw)
        if value is None:
            return "invalid", "Ich kann das noch nicht lesen. Nimm Ziffern, zum Beispiel 12."
        if value == expect["value"]:
            return "correct", ""
        return "wrong", ""
    if kind == "euro":
        raw = (form.get("answer") or "").strip()
        if raw == "":
            return "empty", "Schreibe den Betrag, zum Beispiel 3,50."
        cents = parse_euro_cents(raw)
        if cents is None:
            return "invalid", "Schreibe Euro so: 3,50"
        if cents == expect["cents"]:
            return "correct", ""
        return "wrong", ""
    if kind == "div":
        left = (form.get("q") or "").strip()
        right = (form.get("r") or "").strip()
        if left == "" and right == "":
            return "empty", "Schreibe das Ergebnis und den Rest."
        if left == "" or right == "":
            return "empty", "Beide Felder brauchen eine Zahl."
        quotient = parse_int_de(left)
        remainder = parse_int_de(right)
        if quotient is None or remainder is None:
            return "invalid", "Bitte schreibe zwei Zahlen, zum Beispiel Ergebnis 4 und Rest 2."
        if quotient == expect["q"] and remainder == expect["r"]:
            return "correct", ""
        return "wrong", ""
    if kind == "order":
        raw = (form.get("answer") or "").strip()
        if not raw:
            return "empty", "Tippe die Zahlen der Reihe nach an."
        parts = [part for part in re.split(r"[,;]+", raw) if part.strip()]
        numbers = []
        for part in parts:
            value = parse_int_de(part)
            if value is None:
                return "invalid", "Schreibe die Zahlen mit einem Komma, zum Beispiel 2, 5, 9."
            numbers.append(value)
        if numbers == expect["values"]:
            return "correct", ""
        return "wrong", ""
    if kind == "choice":
        raw = (form.get("answer") or "").strip()
        if not raw:
            return "empty", "Tippe eine Antwort an."
        ids = [choice["id"] for choice in task.get("choices") or []]
        if raw not in ids:
            return "invalid", "Tippe eine der Antworten an."
        if raw == expect["id"]:
            return "correct", ""
        return "wrong", ""
    raise AssertionError(kind)


def evaluate(task: dict, form: dict) -> tuple[str, str]:
    status, hint = _match(current_expect(task), form, task)
    if status == "correct" and task.get("steps"):
        if task["step_index"] < len(task["steps"]) - 1:
            task["step_index"] += 1
            return "step", ""
        return "correct", ""
    return status, hint


def correct_choice(task: dict) -> dict:
    expect = task["expect"]
    if task.get("steps"):
        expect = task["steps"][0]["expect"]
    if expect.get("type") != "choice" and not task.get("steps"):
        expect = task["expect"]
    target = task["expect"]["id"] if task["expect"]["type"] == "choice" else None
    if target is None:
        raise AssertionError("keine Auswahl")
    for choice in task["choices"]:
        if choice["id"] == target:
            return choice
    raise AssertionError("richtige Auswahl fehlt")


def correct_form(task: dict) -> dict:
    expect = current_expect(task)
    kind = expect["type"]
    if kind == "int":
        return {"answer": str(expect["value"])}
    if kind == "euro":
        cents = expect["cents"]
        return {"answer": f"{cents // 100},{cents % 100:02d}"}
    if kind == "div":
        return {"q": str(expect["q"]), "r": str(expect["r"])}
    if kind == "order":
        return {"answer": ", ".join(str(value) for value in expect["values"])}
    if kind == "choice":
        return {"answer": expect["id"]}
    raise AssertionError(kind)


def wrong_form(task: dict) -> dict:
    expect = current_expect(task)
    kind = expect["type"]
    if kind == "int":
        return {"answer": str(expect["value"] + 17)}
    if kind == "euro":
        cents = expect["cents"] + 13
        return {"answer": f"{cents // 100},{cents % 100:02d}"}
    if kind == "div":
        return {"q": str(expect["q"] + 1), "r": str(expect["r"])}
    if kind == "order":
        values = list(expect["values"])
        flipped = list(reversed(values))
        if flipped == values:
            flipped = values[1:] + values[:1]
        if flipped == values:
            raise AssertionError("Reihenfolge lässt sich nicht verwechseln")
        return {"answer": ", ".join(str(value) for value in flipped)}
    if kind == "choice":
        others = [choice["id"] for choice in task["choices"] if choice["id"] != expect["id"]]
        if not others:
            raise AssertionError("keine falsche Auswahl")
        return {"answer": others[0]}
    raise AssertionError(kind)


def _walk(node) -> None:
    banned = {"expect", "meta", "steps", "solution", "ok", "password"}
    if isinstance(node, dict):
        for key, value in node.items():
            if key in banned:
                raise AssertionError(f"Schlüssel {key} wäre sichtbar")
            _walk(value)
    elif isinstance(node, list):
        for item in node:
            _walk(item)


def _visual_text(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"type", "css", "kind"}:
                continue
            found.extend(_visual_text(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_visual_text(item))
    elif isinstance(node, str):
        found.append(node)
    return found


def _blob(task: dict, view: dict) -> str:
    parts = [view.get("prompt") or "", view.get("help") or "", view.get("title") or "", task["solution"]]
    coach = view.get("coach") or {}
    parts.append(coach.get("title") or "")
    parts.extend(coach.get("lines") or [])
    parts.extend(_visual_text(coach.get("figure")))
    parts.extend(_visual_text(view.get("visual")))
    for choice in view.get("choices") or []:
        parts.append(choice.get("label") or "")
        parts.append(choice.get("aria") or "")
        parts.extend(_visual_text(choice.get("fraction")))
        parts.extend(_visual_text(choice.get("shape")))
    return " ".join(parts).lower()


def check_skill(task: dict) -> None:
    meta = task["meta"]
    skill = meta["skill"]
    grade = task["grade"]
    limit = LIMIT[grade]
    if skill not in ALLOWED[grade]:
        raise AssertionError(f"{skill} nicht in Klasse {grade}")
    if skill in {"add", "sub", "written_add", "written_sub"}:
        expected = meta["a"] + meta["b"] if "add" in skill else meta["a"] - meta["b"]
        if meta["result"] != expected or meta["a"] < 0 or meta["b"] < 0:
            raise AssertionError("Summe oder Differenz stimmt nicht")
        if "sub" in skill and meta["a"] < meta["b"]:
            raise AssertionError("negative Differenz")
        if meta["a"] > limit or meta["b"] > limit or meta["result"] > limit:
            raise AssertionError("Zahlenraum überschritten")
        if skill.startswith("written"):
            if grade < 4:
                raise AssertionError("schriftlich zu früh")
            if task["mode"] == "rechnen":
                again = add_steps(meta["a"], meta["b"]) if skill == "written_add" else sub_steps(meta["a"], meta["b"])
                got = [step["expect"]["value"] for step in task["steps"]]
                want = [step["expect"]["value"] for step in again]
                if got != want:
                    raise AssertionError("Schritte passen nicht")
            else:
                if task["input_kind"] != "choice":
                    raise AssertionError("schriftlich ohne Auswahl")
    if skill == "mul":
        if grade < 2 or meta["a"] * meta["b"] != meta["result"]:
            raise AssertionError("Malaufgabe")
        if not (1 <= meta["a"] <= 10 and 1 <= meta["b"] <= 10):
            raise AssertionError("Einmaleins")
    if skill == "div_exact":
        if grade < 3 or meta["divisor"] * meta["quotient"] != meta["dividend"]:
            raise AssertionError("Division")
        if meta["result"] != meta["quotient"] or meta.get("remainder") != 0:
            raise AssertionError("Rest bei glatter Division")
    if skill == "div_rest":
        if grade < 4:
            raise AssertionError("Rest zu früh")
        if meta["dividend"] != meta["q"] * meta["divisor"] + meta["r"]:
            raise AssertionError("Division mit Rest")
        if not (0 < meta["r"] < meta["divisor"]):
            raise AssertionError("Rest ungültig")
    if skill == "clock":
        label = clock_phrase(grade, meta["hour"], meta["minute"])
        if meta["choice_label"] != label:
            raise AssertionError("Uhrzeit-Text")
        minute = meta["minute"]
        if grade == 2 and minute not in (0, 30):
            raise AssertionError("volle oder halbe Stunde")
        if grade == 3 and minute not in (0, 15, 30, 45):
            raise AssertionError("Viertelstunde")
        if grade >= 4 and (minute % 5 or minute < 0 or minute >= 60):
            raise AssertionError("Minuten")
        if grade < 4 and ":" in label:
            raise AssertionError("Digitaluhr zu früh")
        if grade < 3 and "viertel" in label:
            raise AssertionError("Viertel zu früh")
    if skill == "money":
        if grade < 2:
            raise AssertionError("Geld zu früh")
        kind = meta["kind"]
        if kind == "cent":
            if grade != 2 or sum(meta["coins"]) != meta["total_cents"] or meta["total_cents"] > 100:
                raise AssertionError("Cent")
            if any(coin not in {1, 2, 5, 10, 20, 50} for coin in meta["coins"]):
                raise AssertionError("Münze")
            if task["expect"]["value"] != meta["total_cents"]:
                raise AssertionError("Cent-Antwort")
        elif kind == "count":
            if sum(meta["coins"]) != meta["total_cents"] or task["expect"]["cents"] != meta["total_cents"]:
                raise AssertionError("Euro zählen")
            if grade == 3 and meta["total_cents"] > 2000:
                raise AssertionError("über 20 Euro")
            if meta["total_cents"] > 10000:
                raise AssertionError("Geldbetrag zu groß")
        elif kind == "change":
            if grade < 4 or meta["paid_cents"] - meta["price_cents"] != meta["total_cents"]:
                raise AssertionError("Rückgeld")
            if not (0 < meta["price_cents"] < meta["paid_cents"]):
                raise AssertionError("Preis")
        else:
            raise AssertionError(kind)
    if skill in {"compare", "order", "neighbor"}:
        for number in meta["numbers"]:
            if number < 0 or number > limit:
                raise AssertionError("Zahl außerhalb")
    if skill == "neighbor":
        if meta["direction"] == "nach" and meta["result"] != meta["n"] + 1:
            raise AssertionError("Nachfolger")
        if meta["direction"] == "vor" and meta["result"] != meta["n"] - 1:
            raise AssertionError("Vorgänger")
        if task["expect"]["value"] != meta["result"]:
            raise AssertionError("Nachbarzahl")
    if skill == "order":
        if meta["result_list"] != sorted(meta["numbers"]):
            raise AssertionError("Sortierung")
        if task["expect"]["values"] != meta["result_list"]:
            raise AssertionError("Reihenfolge")
    if skill == "compare":
        left, right = meta["numbers"]
        question = meta["question"]
        label = meta["choice_label"]
        if question == "eq":
            if left != right or label != "Ja, gleich groß":
                raise AssertionError("Gleichheit")
        elif question == "gt":
            if left == right or label != fmt(max(left, right)):
                raise AssertionError("größer")
        elif question == "lt":
            if left == right or label != fmt(min(left, right)):
                raise AssertionError("kleiner")
        else:
            raise AssertionError(question)
    if skill == "length_compare":
        left, right = meta["a"], meta["b"]
        label = meta["choice_label"]
        if left > right and label != "Band A":
            raise AssertionError("Band A")
        if right > left and label != "Band B":
            raise AssertionError("Band B")
        if left == right and label != "Beide gleich lang":
            raise AssertionError("gleich lang")
    measured = {"length_cm", "length_m", "length_km", "weight", "time_span", "perimeter", "area"}
    if skill in measured:
        if "calc" not in meta or apply_calc(tuple(meta["calc"])) != meta["result"]:
            raise AssertionError("Umrechnung")
        if task.get("steps"):
            raise AssertionError("Größen haben keine Schritte")
        if task["expect"]["type"] == "int" and task["expect"]["value"] != meta["result"]:
            raise AssertionError("Größen-Antwort")
        if skill == "time_span" and "start_min" in meta:
            if meta["end_min"] - meta["start_min"] != meta["result"]:
                raise AssertionError("Zeitspanne")
        if skill == "perimeter" and meta["result"] != 2 * (meta["l"] + meta["w"]):
            raise AssertionError("Umfang")
        if skill == "area" and meta["result"] != meta["l"] * meta["w"]:
            raise AssertionError("Fläche")
        if skill == "length_cm" and meta["result"] > 30:
            raise AssertionError("cm zu lang für die Stufe")
    if skill == "shape":
        if meta.get("shape") not in SHAPE_NAMES:
            raise AssertionError("Form")
        if meta.get("choice_shape") and correct_choice(task).get("shape") != meta["choice_shape"]:
            raise AssertionError("Formenbild")
        if "result" in meta and task["expect"]["type"] == "int" and task["expect"]["value"] != meta["result"]:
            raise AssertionError("Ecken")
    if skill == "fraction":
        if grade < 4 or task["mode"] != "wahl":
            raise AssertionError("Bruch")
        if meta.get("picture"):
            choice = correct_choice(task)
            if choice["fraction"]["num"] != meta["fraction_num"] or choice["fraction"]["den"] != meta["fraction_den"]:
                raise AssertionError("Bruchbild")
        elif "fraction_num" in meta and task.get("visual"):
            if task["visual"]["num"] != meta["fraction_num"] or task["visual"]["den"] != meta["fraction_den"]:
                raise AssertionError("Bruchbild passt nicht")
        if "calc" in meta and apply_calc(tuple(meta["calc"])) != meta["result"]:
            raise AssertionError("Bruchrechnung")
        if task["expect"]["type"] == "int" and task["expect"]["value"] != meta["result"]:
            raise AssertionError("Bruchwert")
    if task["input_kind"] == "choice":
        if correct_choice(task)["label"] != meta["choice_label"]:
            raise AssertionError("Auswahlbeschriftung")
    if grade < 4:
        return


def ban_words(task: dict, view: dict) -> None:
    text = _blob(task, view)
    grade = task["grade"]
    if grade < 4:
        for word in ("kilometer", "flächen", "bruch", "rest"):
            if word in text:
                raise AssertionError(f"Wort {word} in Klasse {grade}")
    if grade < 3:
        for word in ("viertel", "kilogramm", "umfang"):
            if word in text:
                raise AssertionError(f"Wort {word} in Klasse {grade}")
        if re.search(r"\bkg\b", text) or re.search(r"\bkm\b", text):
            raise AssertionError("Einheit zu früh")
    if grade < 2:
        for word in ("zentimeter", "euro", "cent", "uhr"):
            if word in text:
                raise AssertionError(f"Wort {word} in Klasse 1")
        if "·" in text or ":" in text:
            raise AssertionError("Mal oder Geteilt in Klasse 1")


def validate_task(task: dict) -> None:
    if task["grade"] not in LIMIT or task["mode"] not in MIN_GRADE:
        raise AssertionError("Modus oder Klasse")
    if task["grade"] < MIN_GRADE[task["mode"]]:
        raise AssertionError("Modus noch nicht dran")
    if "skill" not in task.get("meta", {}):
        raise AssertionError("ohne Skill")
    if not task.get("solution") or not task.get("token"):
        raise AssertionError("Lösung oder Token fehlt")
    check_skill(task)
    view = public_view(task)
    _walk(view)
    dump = json.dumps(view, ensure_ascii=False)
    if task["solution"] in dump:
        raise AssertionError("Lösung stünde auf der Seite")
    ban_words(task, view)
    trial = copy.deepcopy(task)
    for _ in range(8):
        status, _hint = evaluate(trial, correct_form(trial))
        if status == "correct":
            break
        if status != "step":
            raise AssertionError(status)
    else:
        raise AssertionError("Aufgabe nicht lösbar")
    wrong = copy.deepcopy(task)
    status, _hint = evaluate(wrong, wrong_form(wrong))
    if status != "wrong":
        raise AssertionError(f"Falsche Antwort galt als {status}")


SKILL_LABELS = {
    "add": "Addition",
    "add_zehner": "Addition mit Zehnerübergang",
    "sub": "Subtraktion",
    "sub_zehner": "Subtraktion mit Zehnerübergang",
    "mul": "Malnehmen",
    "div_exact": "Geteilt",
    "div_rest": "Division mit Rest",
    "compare": "Zahlen vergleichen",
    "order": "Zahlen ordnen",
    "neighbor": "Nachbarzahlen",
    "shape": "Formen",
    "length_compare": "Längen vergleichen",
    "length_cm": "Längen in cm",
    "length_m": "Längen in m und cm",
    "length_km": "Längen in km und m",
    "weight": "Gewicht",
    "clock": "Uhr",
    "money": "Geld",
    "perimeter": "Umfang",
    "area": "Fläche",
    "fraction": "Brüche",
    "time_span": "Zeitspannen",
    "written_add": "Schriftlich addieren",
    "written_sub": "Schriftlich subtrahieren",
}


def task_type_key(task: dict) -> str:
    meta = task.get("meta") or {}
    skill = str(meta.get("skill") or "aufgabe")
    if skill in {"add", "sub"}:
        try:
            left = int(meta.get("a"))
            right = int(meta.get("b"))
        except (TypeError, ValueError):
            return skill
        if skill == "add" and (left % 10) + (right % 10) >= 10:
            return "add_zehner"
        if skill == "sub" and (left % 10) < (right % 10):
            return "sub_zehner"
    return skill


def skill_label(key: str) -> str:
    return SKILL_LABELS.get(key, "Aufgabe")


def task_signature(task: dict) -> str:
    meta = task.get("meta") or {}
    numbers = meta.get("numbers")
    if isinstance(numbers, (list, tuple)):
        rendered = ",".join(str(int(number)) for number in numbers)
    else:
        rendered = ""
    prompt = " ".join((task.get("prompt") or "").split())
    return f"{task.get('mode')}|{task.get('grade')}|{task_type_key(task)}|{rendered}|{prompt}"[:300]


def revive_task(snapshot: dict) -> dict:
    task = copy.deepcopy(snapshot)
    task.pop("noted", None)
    task["token"] = secrets.token_urlsafe(12)
    task["step_index"] = 0
    task.setdefault("choices", [])
    return task


def build_task(mode: str, grade: int) -> dict:
    if mode not in BUILDERS or grade not in LIMIT:
        raise ValueError("unbekannt")
    if grade < MIN_GRADE[mode]:
        raise ValueError("zu früh")
    last = "unbekannt"
    for _ in range(12):
        task = BUILDERS[mode](grade)
        task["token"] = secrets.token_urlsafe(12)
        task["mode"] = mode
        task["grade"] = grade
        task.setdefault("step_index", 0)
        task.setdefault("choices", [])
        try:
            validate_task(task)
            return task
        except AssertionError as exc:
            last = str(exc)
    raise RuntimeError(f"{mode} Klasse {grade}: {last}")


def _check_parsers() -> None:
    assert parse_int_de("12") == 12
    assert parse_int_de(" 1.000 ") == 1000
    assert parse_int_de("1.000.000") == 1000000
    assert parse_int_de("1,000") is None
    assert parse_int_de("1.2") is None
    assert parse_int_de("") is None
    assert parse_euro_cents("3,50") == 350
    assert parse_euro_cents("3.50") == 350
    assert parse_euro_cents("3,5") == 350
    assert parse_euro_cents("3") == 300
    assert parse_euro_cents("0,70") == 70
    assert parse_euro_cents("3,50 €") == 350
    assert parse_euro_cents("3,501") is None
    assert parse_euro_cents("1.000") is None
    assert clock_phrase(2, 3, 0) == "3 Uhr"
    assert clock_phrase(2, 3, 30) == "halb 4"
    assert clock_phrase(2, 12, 30) == "halb 1"
    assert clock_phrase(3, 3, 15) == "viertel nach 3"
    assert clock_phrase(3, 3, 45) == "viertel vor 4"
    assert clock_phrase(3, 12, 45) == "viertel vor 1"
    assert clock_phrase(3, 12, 15) == "viertel nach 12"
    assert clock_phrase(4, 2, 5) == "2:05 Uhr"
    assert clock_phrase(4, 12, 0) == "12:00 Uhr"
    hour_angle, minute_angle = clock_angles(3, 0)
    assert hour_angle == 90 and minute_angle == 0
    hour_angle, minute_angle = clock_angles(6, 30)
    assert hour_angle == 195 and minute_angle == 180
    assert clock_angles(12, 0) == (0, 0)
    for _ in range(40):
        left = random.randint(0, 999)
        right = random.randint(0, 999)
        steps = add_steps(left, right)
        digits = [step["expect"]["value"] for step in steps]
        assert int("".join(str(digit) for digit in reversed(digits))) == left + right
        if left >= right:
            steps = sub_steps(left, right)
            digits = [step["expect"]["value"] for step in steps]
            assert int("".join(str(digit) for digit in reversed(digits))) == left - right
    assert int("".join(str(step["expect"]["value"]) for step in reversed(sub_steps(500, 1)))) == 499
    assert int("".join(str(step["expect"]["value"]) for step in reversed(sub_steps(1000, 1)))) == 999
    from mathe.auth import hash_password, verify_password

    stored = hash_password("maya")
    assert verify_password("maya", stored)
    assert not verify_password("Maya", stored)
    assert "maya" not in stored


def self_check(samples: int = 30) -> None:
    _check_parsers()
    from mathe.coach import check_examples

    check_examples()
    for grade in (1, 2, 3, 4):
        for mode, _title, _text, minimum in MODES:
            if grade < minimum:
                try:
                    build_task(mode, grade)
                except ValueError:
                    continue
                raise AssertionError(f"{mode} in Klasse {grade} hätte gesperrt sein müssen")
            for _ in range(samples):
                task = build_task(mode, grade)
                if task["mode"] != mode or task["grade"] != grade:
                    raise AssertionError("Zuordnung")
    print(f"Aufgabenprüfung ok ({samples} je Modus und Klasse).", flush=True)


if __name__ == "__main__":
    self_check()
