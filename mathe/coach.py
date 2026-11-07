"""Rechenhilfe zur konkreten Aufgabe.

Die Hilfe bleibt in der Anzeige, das Antwortfeld füllt sie nicht.
Bei Rechnen und Lücken ab Klasse 2 steht das Ergebnis erst im letzten Satz.
Klasse 1 und die anderen Modi nehmen das Ergebnis nicht vorweg.
"""

from __future__ import annotations

import re

PLACES = [
    "Einer",
    "Zehner",
    "Hunderter",
    "Tausender",
    "Zehntausender",
    "Hunderttausender",
    "Millionen",
]

QUIET_MODES = {"wahl", "uhr", "geld", "groessen", "formen", "ordnen"}
ORDINALS = [
    "",
    "ersten",
    "zweiten",
    "dritten",
    "vierten",
    "fünften",
    "sechsten",
    "siebten",
    "achten",
    "neunten",
    "zehnten",
]


def _fmt(number: int) -> str:
    from mathe.tasks import fmt

    return fmt(int(number))


def _place(index: int) -> str:
    if 0 <= index < len(PLACES):
        return PLACES[index]
    return "nächste Stelle"


def _contains_number(text: str, number: int) -> bool:
    token = _fmt(number)
    return re.search(rf"(?<![\d.]){re.escape(token)}(?!\d)", text) is not None


def _hide_token(line: str, number: int) -> str:
    token = _fmt(number)
    return re.sub(rf"(?<![\d.]){re.escape(token)}(?!\d)", "diese Zahl", line)


def _shield(lines: list[str], banned: set[int], allowed: set[int], solution: str, reveal_last: bool) -> list[str]:
    hidden = [number for number in banned if number not in allowed and len(_fmt(number)) >= 2]
    if reveal_last and lines:
        body = lines[:-1]
        last = lines[-1]
    else:
        body = lines
        last = None
    cleaned = []
    for line in body:
        for number in hidden:
            line = _hide_token(line, number)
        cleaned.append(line)
    if last is not None:
        cleaned.append(last)
    blob = "\n".join(cleaned)
    if solution and solution in blob:
        raise AssertionError("Hilfe wiederholt die Lösung")
    if reveal_last and hidden:
        for number in hidden:
            if not _contains_number(cleaned[-1], number):
                raise AssertionError("Ergebnis fehlt im letzten Schritt")
            earlier = "\n".join(cleaned[:-1])
            if _contains_number(earlier, number):
                raise AssertionError("Ergebnis steht zu früh in der Hilfe")
    return cleaned


def _column(a: int, b: int, op: str) -> dict:
    width = max(len(str(int(a))), len(str(int(b))), 1)

    def row(number: int) -> list[str]:
        text = str(int(number))
        return [" "] * (width - len(text)) + list(text)

    return {
        "type": "column",
        "op": "+" if op == "+" else "−",
        "rows": [row(a), row(b)],
    }


def _line(start: int) -> dict:
    start = int(start)
    if start < 0:
        start = 0
    if start > 20:
        start = 20
    return {"type": "line", "max": 20, "start": start}


def _add_facts(a: int, b: int) -> list[dict]:
    width = max(len(str(a)), len(str(b)), 1)
    top = [int(ch) for ch in f"{a:0{width}d}"]
    bot = [int(ch) for ch in f"{b:0{width}d}"]
    carry = 0
    facts = []
    for index in range(width):
        pos = width - 1 - index
        parts = [top[pos], bot[pos]]
        if carry:
            parts.append(carry)
        total = top[pos] + bot[pos] + carry
        write = total % 10
        new_carry = total // 10
        facts.append(
            {
                "place": _place(index),
                "parts": parts,
                "total": total,
                "write": write,
                "carry_out": new_carry,
                "only_carry": False,
            }
        )
        carry = new_carry
    if carry:
        facts.append(
            {
                "place": _place(width),
                "parts": [carry],
                "total": carry,
                "write": carry,
                "carry_out": 0,
                "only_carry": True,
            }
        )
    return facts


def _add_sentence(fact: dict, result: int) -> str:
    if fact["only_carry"]:
        if fact["write"] == result:
            return "Ganz vorn bleibt noch ein Übertrag stehen."
        return f"Ganz vorn schreibst du den Übertrag {fact['write']}."
    spoken = " plus ".join(str(part) for part in fact["parts"])
    total = fact["total"]
    write = fact["write"]
    carry = fact["carry_out"]
    if total == result:
        text = f"{fact['place']}: {spoken}."
        if carry and write != result:
            text += f" Schreibe {write} und nimm {carry} als Übertrag mit."
        elif write != result:
            text += f" Schreibe {write}."
        elif carry:
            text += " Es gibt einen Übertrag."
        return text
    text = f"{fact['place']}: {spoken} ergibt {total}."
    if write != result:
        text += f" Schreibe {write}."
    if carry and carry != result:
        text += f" Nimm {carry} als Übertrag mit."
    elif carry:
        text += " Es bleibt ein Übertrag."
    return text


def written_add_lines(a: int, b: int, reveal: bool, closing: str) -> list[str]:
    a, b = int(a), int(b)
    result = a + b
    lines = [
        f"Schreibe {_fmt(a)} und {_fmt(b)} untereinander, Einer unter Einer.",
        "Beginne rechts. Wird eine Stelle 10 oder mehr, schreibst du nur die Einerziffer und nimmst den Zehner als Übertrag mit.",
    ]
    if not reveal:
        lines.append("Gehe so Stelle für Stelle nach links.")
        lines.append("Die Zahl liest du selbst. Hier steht sie noch nicht, und keine Antwort ist markiert.")
        return lines
    for fact in _add_facts(a, b):
        lines.append(_add_sentence(fact, result))
    lines.append("Lies die Ziffern von links nach rechts.")
    lines.append(f"{closing} {_fmt(result)}.")
    return lines


def _sub_facts(a: int, b: int) -> list[dict]:
    width = max(len(str(a)), len(str(b)), 1)
    top = [int(ch) for ch in f"{a:0{width}d}"]
    bot = [int(ch) for ch in f"{b:0{width}d}"]
    facts = []
    for index in range(width):
        pos = width - 1 - index
        borrowed = False
        bridges = False
        if top[pos] < bot[pos]:
            donor = pos - 1
            while donor >= 0 and top[donor] == 0:
                top[donor] = 9
                donor -= 1
            if donor < 0:
                raise AssertionError("borgen")
            top[donor] -= 1
            bridges = donor < pos - 1
            top[pos] += 10
            borrowed = True
        facts.append(
            {
                "place": _place(index),
                "next_place": _place(index + 1),
                "upper": top[pos],
                "lower": bot[pos],
                "write": top[pos] - bot[pos],
                "borrowed": borrowed,
                "bridges": bridges,
            }
        )
    return facts


def _sub_sentence(fact: dict, result: int) -> str:
    upper = fact["upper"]
    lower = fact["lower"]
    write = fact["write"]
    if fact["borrowed"]:
        if fact["bridges"]:
            text = (
                f"{fact['place']}: Oben ist zu klein. "
                "Du leihst dir weiter links, leere Stellen dazwischen werden zu neun."
            )
        else:
            text = (
                f"{fact['place']}: Oben ist zu klein. "
                f"Du leihst dir einen Zehner von den {fact['next_place']}."
            )
        if upper != result and lower != result:
            text += f" Jetzt {upper} minus {lower}."
        else:
            text += " Jetzt reicht die obere Stelle."
    elif upper != result and lower != result:
        text = f"{fact['place']}: {upper} minus {lower}."
    else:
        text = f"{fact['place']}: Diese Stelle rechnest du für sich."
    if write != result:
        text += f" Schreibe {write}."
    else:
        text += " Die Ziffer gehört zum Ergebnis."
    return text


def written_sub_lines(a: int, b: int, reveal: bool, closing: str) -> list[str]:
    a, b = int(a), int(b)
    result = a - b
    lines = [
        f"Schreibe {_fmt(a)} und {_fmt(b)} untereinander, Einer unter Einer.",
        "Beginne rechts. Ist oben eine Ziffer zu klein, leihst du dir einen Zehner von links.",
    ]
    if not reveal:
        lines.append("Schreibe jede Stelle und gehe nach links weiter.")
        lines.append("Die Zahl liest du selbst. Hier steht sie noch nicht, und keine Antwort ist markiert.")
        return lines
    for fact in _sub_facts(a, b):
        lines.append(_sub_sentence(fact, result))
    lines.append("Lies die Ziffern von links nach rechts.")
    lines.append(f"{closing} {_fmt(result)}.")
    return lines


def grade1_add_lines(a: int, b: int) -> list[str]:
    start, add = (a, b) if a >= b else (b, a)
    result = a + b
    lines = [f"Starte bei {start} auf dem Zahlenstrahl."]
    if add == 0:
        lines.append("Es kommt nichts dazu.")
        lines.append("Die Zahl an deinem Start schreibst du selbst ins Feld.")
        return lines
    if start % 10 == 0:
        if add == result:
            lines.append("Gehe so viele Schritte nach rechts, wie die zweite Zahl sagt.")
        else:
            lines.append(f"Gehe {add} Schritte nach rechts.")
        lines.append("Die Zahl, auf der du landest, schreibst du selbst ins Feld.")
        return lines
    need = 10 - (start % 10)
    if add < need:
        if add == result:
            lines.append("Gehe so viele Schritte nach rechts, wie die zweite Zahl sagt.")
        else:
            lines.append(f"Gehe {add} Schritte nach rechts. Du bleibst in diesem Zehner.")
        lines.append("Die Zahl, auf der du landest, schreibst du selbst ins Feld.")
        return lines
    if add == need:
        if need == result:
            lines.append("Gehe bis zum nächsten Zehner. Genau so groß ist der Schritt.")
        else:
            lines.append(f"Bis zum nächsten Zehner fehlen {need}. Genau so viele Schritte gehst du.")
        lines.append("Du landest auf dem Zehner. Diese Zahl schreibst du selbst ins Feld.")
        return lines
    rest = add - need
    step = f"Bis zum nächsten Zehner fehlen {need}."
    if need != result:
        lines.append(f"{step} Die nimmst du von der {add}." if add != result else f"{step}")
    else:
        lines.append("Gehe zuerst bis zum nächsten Zehner.")
    if rest == result:
        lines.append("Was von der zweiten Zahl noch übrig ist, gehst du vom Zehner aus weiter.")
    else:
        lines.append(f"Danach bleiben {rest} Schritte. Die gehst du vom Zehner aus weiter.")
    lines.append("Die Zahl, auf der du landest, schreibst du selbst ins Feld.")
    return lines


def grade1_sub_lines(a: int, b: int) -> list[str]:
    result = a - b
    lines = [f"Starte bei {a} auf dem Zahlenstrahl."]
    if b == 0:
        lines.append("Du gehst keinen Schritt zurück.")
        lines.append("Die Zahl an deinem Start schreibst du selbst ins Feld.")
        return lines
    ones = a % 10
    if b <= ones or ones == 0:
        if b == result:
            lines.append("Gehe so viele Schritte nach links, wie die zweite Zahl sagt.")
        else:
            lines.append(f"Gehe {b} Schritte nach links.")
        lines.append("Die Zahl, auf der du landest, schreibst du selbst ins Feld.")
        return lines
    if ones == result:
        lines.append("Gehe zuerst bis zum Zehner zurück.")
    else:
        lines.append(f"Gehe zuerst {ones} Schritte zurück bis zum Zehner.")
    rest = b - ones
    if rest == result:
        lines.append("Was von der zweiten Zahl noch übrig ist, gehst du weiter zurück.")
    else:
        lines.append(f"Dann noch {rest} Schritte zurück.")
    lines.append("Die Zahl, auf der du ankommst, schreibst du selbst ins Feld.")
    return lines


def halb_add_lines(a: int, b: int, reveal: bool, closing: str) -> list[str]:
    result = a + b
    t1, o1 = divmod(a, 10)
    t2, o2 = divmod(b, 10)
    ones = o1 + o2
    extra = ones // 10
    ones_digit = ones % 10
    tens = t1 + t2 + extra
    lines = [
        f"{_fmt(a)} sind {t1} Zehner und {o1} Einer.",
        f"{_fmt(b)} sind {t2} Zehner und {o2} Einer.",
    ]
    if not reveal:
        lines.append("Zähle zuerst die Einer, danach die Zehner.")
        lines.append("Sind die Einer 10 oder mehr, wird daraus ein Zehner.")
        lines.append("Die zusammengebaute Zahl schreibst du selbst. Hier steht sie noch nicht.")
        return lines
    if ones == result:
        lines.append(f"Einer: {o1} plus {o2}.")
    else:
        lines.append(f"Einer: {o1} plus {o2} ergibt {ones}.")
    if extra:
        if ones_digit == result:
            lines.append(f"Daraus wird {extra} Zehner zum Mitnehmen. Die Einer gehören zum Ergebnis.")
        else:
            lines.append(f"Daraus werden {extra} Zehner zum Mitnehmen und {ones_digit} Einer.")
    tens_text = f"Zehner: {t1} plus {t2}"
    if extra:
        tens_text += f" plus {extra}"
    if tens != result and tens * 10 != result:
        tens_text += f" ergibt {tens} Zehner."
    else:
        tens_text += "."
    lines.append(tens_text)
    lines.append(f"{closing} {_fmt(result)}.")
    return lines


def halb_sub_lines(a: int, b: int, reveal: bool, closing: str) -> list[str]:
    result = a - b
    t1, o1 = divmod(a, 10)
    t2, o2 = divmod(b, 10)
    lines = [
        f"{_fmt(a)} sind {t1} Zehner und {o1} Einer.",
        f"{_fmt(b)} sind {t2} Zehner und {o2} Einer.",
    ]
    if not reveal:
        lines.append("Ziehe zuerst die Einer ab, danach die Zehner.")
        lines.append("Sind oben zu wenig Einer, tauschst du einen Zehner in zehn Einer.")
        lines.append("Die Zahl schreibst du selbst. Hier steht sie noch nicht.")
        return lines
    if o1 < o2:
        ones_digit = (o1 + 10) - o2
        tens_digit = (t1 - 1) - t2
        lines.append(f"Einer: {o1} minus {o2} geht nicht. Tausche einen Zehner in zehn Einer.")
        if ones_digit == result:
            lines.append("Die Einer gehören zum Ergebnis.")
        else:
            lines.append(f"Dann sind es {o1 + 10} minus {o2}, das sind {ones_digit} Einer.")
        if tens_digit == result or tens_digit * 10 == result:
            lines.append(f"Zehner: {t1 - 1} minus {t2}.")
        else:
            lines.append(f"Zehner: {t1 - 1} minus {t2} ergibt {tens_digit} Zehner.")
    else:
        ones_digit = o1 - o2
        tens_digit = t1 - t2
        if ones_digit == result:
            lines.append(f"Einer: {o1} minus {o2}.")
        else:
            lines.append(f"Einer: {o1} minus {o2} ergibt {ones_digit}.")
        if tens_digit == result or tens_digit * 10 == result:
            lines.append(f"Zehner: {t1} minus {t2}.")
        else:
            lines.append(f"Zehner: {t1} minus {t2} ergibt {tens_digit} Zehner.")
    lines.append(f"{closing} {_fmt(result)}.")
    return lines


def mul_lines(a: int, b: int, reveal: bool, closing: str) -> list[str]:
    a, b = int(a), int(b)
    result = a * b
    if not reveal:
        return [
            f"{a} mal {b} heißt: die {a} genau {b}-mal nehmen.",
            "Du kannst die Gruppen nacheinander dazuzählen.",
            "Wie viele es zusammen sind, rechnest du selbst. Keine Antwort ist markiert.",
        ]
    if a == 0 or b == 0:
        return [
            f"{a} mal {b} heißt: es kommt nichts dazu.",
            f"{closing} {_fmt(result)}.",
        ]
    if b == 1:
        return [
            f"{a} mal 1 heißt: genau einmal die {a}.",
            f"{closing} {_fmt(result)}.",
        ]
    lines = [f"{a} mal {b} heißt: die {a} genau {b}-mal hintereinander."]
    running = 0
    for index in range(1, b):
        running += a
        name = ORDINALS[index] if index < len(ORDINALS) else f"{index}."
        if running == result:
            lines.append(f"Beim {name} Mal nimmst du {a} dazu.")
        else:
            lines.append(f"Beim {name} Mal nimmst du {a} dazu, zusammen {running}.")
    lines.append(f"Beim letzten Mal noch {a} dazu. {closing} {_fmt(result)}.")
    return lines


def div_exact_lines(dividend: int, divisor: int, quotient: int, reveal: bool, closing: str) -> list[str]:
    dividend, divisor, quotient = int(dividend), int(divisor), int(quotient)
    if not reveal:
        return [
            f"Teile {_fmt(dividend)} durch {divisor}.",
            f"Suche im Einmaleins der {divisor}, welche Reihe bei {_fmt(dividend)} landet.",
            "Wie oft das ist, rechnest du selbst. Keine Antwort ist markiert.",
        ]
    lines = [
        f"Teile {_fmt(dividend)} durch {divisor}.",
        f"Gehe das Einmaleins der {divisor} durch.",
    ]
    for step in range(1, quotient):
        product = divisor * step
        if product in {quotient, dividend}:
            lines.append(f"{divisor} mal {step} ist noch kleiner als {_fmt(dividend)}.")
        else:
            lines.append(f"{divisor} mal {step} ergibt {product}.")
    lines.append(
        f"{divisor} mal {quotient} trifft {_fmt(dividend)}. {closing} {_fmt(quotient)}."
    )
    return lines


def div_rest_lines(dividend: int, divisor: int, quotient: int, remainder: int, reveal: bool) -> list[str]:
    dividend, divisor = int(dividend), int(divisor)
    quotient, remainder = int(quotient), int(remainder)
    if not reveal:
        return [
            f"Teile {_fmt(dividend)} durch {divisor}.",
            "Suche, wie oft der Teiler ganz hineinpasst, ohne darüber zu gehen.",
            "Was übrig bleibt, ist kleiner als der Teiler.",
            "Ergebnis und Rest schreibst du selbst. Hier stehen sie noch nicht.",
        ]
    lines = [
        f"Teile {_fmt(dividend)} durch {divisor}.",
        f"Suche im Einmaleins der {divisor} die größte Reihe, die nicht über {_fmt(dividend)} hinausgeht.",
    ]
    if quotient > 1:
        previous = divisor * (quotient - 1)
        if previous not in {quotient, remainder} and (quotient - 1) not in {quotient, remainder}:
            lines.append(f"{divisor} mal {quotient - 1} ergibt {previous}. Das reicht noch nicht.")
        else:
            lines.append("Die nächstkleinere Reihe reicht noch nicht.")
    product = divisor * quotient
    lines.append(
        f"{divisor} mal {quotient} ergibt {product}. "
        f"Von {_fmt(dividend)} bleibt danach noch etwas übrig, kleiner als {divisor}. "
        f"Das Ergebnis ist {quotient}, der Rest ist {remainder}."
    )
    return lines


def _add_pack(grade: int, a: int, b: int, reveal: bool, closing: str) -> tuple[list[str], dict | None]:
    if grade <= 1:
        start = a if a >= b else b
        return grade1_add_lines(a, b), _line(start)
    if grade == 2:
        return halb_add_lines(a, b, reveal, closing), None
    return written_add_lines(a, b, reveal, closing), _column(a, b, "+")


def _sub_pack(grade: int, a: int, b: int, reveal: bool, closing: str) -> tuple[list[str], dict | None]:
    if grade <= 1:
        return grade1_sub_lines(a, b), _line(a)
    if grade == 2:
        return halb_sub_lines(a, b, reveal, closing), None
    return written_sub_lines(a, b, reveal, closing), _column(a, b, "-")


def _grade1_gap(skill: str, left: int, right: int, total: int, unknown: str | None) -> list[str]:
    if skill == "add":
        known = right if unknown == "left" else left
        return [
            f"Es soll {_fmt(total)} herauskommen.",
            f"Starte bei {known} auf dem Zahlenstrahl.",
            f"Zähle die Schritte bis {_fmt(total)}.",
            "So viele Schritte sind die fehlende Zahl. Schreibe sie selbst ins Feld.",
        ]
    if unknown == "left":
        return [
            f"Du gehst {right} zurück und landest bei {_fmt(total)}.",
            "Lege diese beiden Zahlen auf dem Zahlenstrahl hintereinander.",
            "Wie weit du vom Anfang bis zum Ende kommst, ist die fehlende Zahl.",
            "Schreibe sie selbst ins Feld.",
        ]
    return [
        f"Starte bei {_fmt(left)}.",
        f"Du willst bei {_fmt(total)} ankommen.",
        "Zähle die Schritte zurück. So groß ist die fehlende Zahl.",
        "Schreibe sie selbst ins Feld.",
    ]


def _unknown(prompt: str) -> str | None:
    if "□" not in prompt:
        return None
    if prompt.strip().startswith("□"):
        return "left"
    return "right"


def _arith(task: dict, reveal: bool) -> tuple[list[str], dict | None]:
    grade = int(task["grade"])
    meta = task["meta"]
    skill = meta["skill"]
    prompt = task.get("prompt") or ""
    unknown = _unknown(prompt)
    gap = unknown is not None
    closing = "Die fehlende Zahl ist" if gap else "Das Ergebnis ist"
    if skill in {"add", "written_add"}:
        left, right = int(meta["a"]), int(meta["b"])
        total = int(meta["result"])
        if gap and grade <= 1:
            return _grade1_gap("add", left, right, total, unknown), _line(right if unknown == "left" else left)
        if gap:
            known = right if unknown == "left" else left
            lines, figure = _sub_pack(grade, total, known, True, closing)
            intro = f"Die Lücke findest du mit Minus: {_fmt(total)} minus {_fmt(known)}."
            return [intro] + lines, figure
        return _add_pack(grade, left, right, reveal, closing)
    if skill in {"sub", "written_sub"}:
        left, right = int(meta["a"]), int(meta["b"])
        total = int(meta["result"])
        if gap and grade <= 1:
            start = total if unknown == "left" else left
            return _grade1_gap("sub", left, right, total, unknown), _line(start)
        if gap:
            if unknown == "left":
                lines, figure = _add_pack(grade, total, right, True, closing)
                intro = f"Die Lücke findest du mit Plus: {_fmt(total)} plus {_fmt(right)}."
                return [intro] + lines, figure
            lines, figure = _sub_pack(grade, left, total, True, closing)
            intro = f"Die Lücke findest du mit Minus: {_fmt(left)} minus {_fmt(total)}."
            return [intro] + lines, figure
        return _sub_pack(grade, left, right, reveal, closing)
    if skill == "mul":
        left, right = int(meta["a"]), int(meta["b"])
        if gap and reveal:
            if unknown == "left":
                lines = div_exact_lines(left * right, right, left, True, closing)
                intro = f"Die Lücke findest du mit Geteilt: {_fmt(left * right)} durch {right}."
            else:
                lines = div_exact_lines(left * right, left, right, True, closing)
                intro = f"Die Lücke findest du mit Geteilt: {_fmt(left * right)} durch {left}."
            return [intro] + lines, None
        return mul_lines(left, right, reveal, closing), None
    if skill == "div_exact":
        dividend = int(meta["dividend"])
        divisor = int(meta["divisor"])
        quotient = int(meta["quotient"])
        if gap and reveal:
            if unknown == "left":
                lines = mul_lines(divisor, quotient, True, closing)
                intro = f"Die Lücke findest du mit Mal: {divisor} mal {quotient}."
                return [intro] + lines, None
            lines = div_exact_lines(dividend, quotient, divisor, True, closing)
            intro = f"Die Lücke findest du mit Geteilt: {_fmt(dividend)} durch {quotient}."
            return [intro] + lines, None
        return div_exact_lines(dividend, divisor, quotient, reveal, closing), None
    if skill == "div_rest":
        return (
            div_rest_lines(
                meta["dividend"],
                meta["divisor"],
                meta["q"],
                meta["r"],
                reveal,
            ),
            None,
        )
    raise AssertionError(skill)


def _step_help(task: dict) -> tuple[list[str], dict | None]:
    meta = task["meta"]
    index = int(task.get("step_index") or 0)
    left, right = int(meta["a"]), int(meta["b"])
    if meta["skill"] == "written_add":
        facts = _add_facts(left, right)
        fact = facts[index]
        if fact["only_carry"]:
            lines = [
                "Links ist noch ein Übertrag übrig.",
                f"Du schreibst die Ziffer {fact['write']}.",
            ]
        else:
            spoken = " plus ".join(str(part) for part in fact["parts"])
            lines = [f"Du bist bei den {fact['place']}.", f"Rechne {spoken}."]
            if fact["total"] != fact["write"]:
                lines.append(f"Das ergibt {fact['total']}.")
                if fact["carry_out"]:
                    lines.append(f"Die {fact['carry_out']} ist der Übertrag für die nächste Stelle.")
            lines.append(f"Du schreibst die Ziffer {fact['write']}.")
        return lines, None
    facts = _sub_facts(left, right)
    fact = facts[index]
    lines = [f"Du bist bei den {fact['place']}."]
    if fact["borrowed"]:
        lines.append("Oben ist die Ziffer zu klein. Du leihst dir einen Zehner von links.")
    lines.append(f"Rechne {fact['upper']} minus {fact['lower']}.")
    lines.append(f"Du schreibst die Ziffer {fact['write']}.")
    return lines, None


def _clock_lines(grade: int) -> list[str]:
    lines = [
        "Der kurze Zeiger zeigt die Stunde.",
        "Der lange Zeiger zeigt die Minuten.",
    ]
    if grade <= 2:
        lines.append("Steht der lange Zeiger oben, ist es genau die Stunde.")
        lines.append("Steht er unten, sagt man halb und meint die nächste Stunde.")
    elif grade == 3:
        lines.append("Oben ist die volle Stunde, unten ist halb.")
        lines.append("Bei der 3 ist es viertel nach, bei der 9 ist es viertel vor.")
    else:
        lines.append("Jede Zahl am Rand steht für fünf Minuten.")
        lines.append("Lies erst die Stunde am kurzen Zeiger, dann die Minuten am langen.")
    lines.append("Die passende Uhrzeit tippst du selbst an. Nichts ist markiert.")
    return lines


def _money_lines(task: dict) -> list[str]:
    kind = task["meta"].get("kind")
    if kind == "cent":
        return [
            "Jede Münze zeigt ihren Wert in Cent.",
            "Fang bei der größten Zahl an und zähle die anderen dazu.",
            "Die Summe schreibst du selbst in das Feld.",
        ]
    if kind == "change":
        return [
            "Sieh auf den Preis und auf den Schein, mit dem bezahlt wird.",
            "Ziehe den Preis vom Schein ab.",
            "Was übrig bleibt, ist das Rückgeld. Schreibe es mit einem Komma.",
        ]
    return [
        "Zähle zuerst die Euro, danach die Cent.",
        "Hundert Cent sind ein Euro.",
        "Schreibe die Euro vor dem Komma und die Cent danach.",
    ]


def _measure_lines(task: dict) -> list[str]:
    meta = task["meta"]
    skill = meta["skill"]
    prompt = task.get("prompt") or ""
    visual = task.get("visual") or {}
    if skill == "length_compare":
        return [
            "Lege die beiden Bänder gedanklich übereinander.",
            "Das Band, das weiter reicht, ist länger.",
            "Reichen beide gleich weit, sind sie gleich lang. Nichts ist markiert.",
        ]
    if skill == "length_cm" and visual.get("type") == "ruler":
        return [
            "Der Streifen beginnt bei 0 auf dem Lineal.",
            "Lies die Zahl, an der der Streifen aufhört.",
            "Diese Zahl schreibst du selbst in das Feld.",
        ]
    if skill == "length_cm":
        return [
            "Zentimeter rechnest du wie andere Zahlen.",
            "Plus bleibt Plus.",
            "Die Summe schreibst du selbst dazu.",
        ]
    if skill == "length_m":
        return [
            "Ein Meter hat hundert Zentimeter.",
            "Bei mehreren Metern nimmst du hundert mehrmals.",
            "Kommen einzelne Zentimeter dazu, zählst du sie am Ende dazu.",
        ]
    if skill == "length_km":
        if "Kilometer sind" in prompt and "Meter" in prompt and prompt.strip().startswith("Wie viele Kilometer"):
            return [
                "Tausend Meter sind ein Kilometer.",
                "Schau, wie oft tausend Meter in die Meterzahl passen.",
                "Die Zahl schreibst du selbst ins Feld.",
            ]
        return [
            "Ein Kilometer hat tausend Meter.",
            "Bei mehreren Kilometern nimmst du tausend mehrmals.",
            "Kommen einzelne Meter dazu, zählst du sie am Ende dazu.",
        ]
    if skill == "weight":
        return [
            "Ein Kilogramm hat tausend Gramm.",
            "Bei mehreren Kilogramm nimmst du tausend mehrmals.",
            "Kommen einzelne Gramm dazu, zählst du sie am Ende dazu.",
        ]
    if skill == "time_span" and "Von " in prompt:
        return [
            "Lies die Startzeit und die Endzeit.",
            "Zähle die Minuten dazwischen. Eine Stunde zählt als sechzig Minuten.",
            "Die Minuten schreibst du selbst ins Feld.",
        ]
    if skill == "time_span":
        return [
            "Eine Stunde hat sechzig Minuten.",
            "Bei mehreren Stunden nimmst du sechzig mehrmals.",
            "Kommen einzelne Minuten dazu, zählst du sie am Ende dazu.",
        ]
    if skill == "perimeter":
        return [
            f"Das Viereck ist {meta['l']} cm lang und {meta['w']} cm breit.",
            "Der Umfang geht einmal herum: zwei Längen und zwei Breiten.",
            "Zähle alle vier Seiten zusammen. Die Zahl schreibst du selbst.",
        ]
    if skill == "area":
        return [
            f"Das Viereck ist {meta['l']} cm lang und {meta['w']} cm breit.",
            "Die Fläche zählst du in Kästchen: Länge mal Breite.",
            "Die Zahl der Kästchen schreibst du selbst ins Feld.",
        ]
    raise AssertionError(skill)


def _shape_lines(task: dict) -> list[str]:
    prompt = task.get("prompt") or ""
    if "Ecken hat diese" in prompt:
        return [
            "Zähle jede Spitze der Form einmal.",
            "Jede Ecke zählt mit.",
            "Die Zahl schreibst du selbst in das Feld.",
        ]
    if "rund" in prompt:
        return [
            "Suche die Form ohne Ecken.",
            "Sie ist überall rund.",
            "Diese Form tippst du selbst an. Nichts ist markiert.",
        ]
    if "drei Ecken" in prompt:
        return [
            "Zähle bei jeder Form die Ecken.",
            "Du suchst die Form mit genau drei Ecken.",
            "Tippe sie selbst an. Nichts ist markiert.",
        ]
    if "gleich lange Seiten" in prompt:
        return [
            "Schau, wo alle Seiten gleich lang sind.",
            "Die Form hat vier Ecken.",
            "Tippe sie selbst an. Nichts ist markiert.",
        ]
    return [
        "Schau auf die Linien der Form.",
        "Rund und ohne Ecke, drei Ecken oder vier Ecken.",
        "Bei vier Ecken prüfst du, ob alle Seiten gleich lang sind.",
        "Den Namen tippst du selbst an. Nichts ist markiert.",
    ]


def _order_lines(task: dict) -> list[str]:
    skill = task["meta"]["skill"]
    grade = int(task["grade"])
    if skill == "neighbor":
        return [
            "Direkt danach ist um eins größer.",
            "Direkt davor ist um eins kleiner.",
            "Diese eine Stelle rechnest du selbst und schreibst die Zahl ins Feld.",
        ]
    if skill == "order":
        return [
            "Suche die kleinste Zahl und tippe sie zuerst an.",
            "Dann immer die nächstgrößere, bis alle Zahlen in der Reihe stehen.",
            "Die Reihenfolge setzt du selbst. Hier ist sie nicht vorgemacht.",
        ]
    if grade <= 1:
        return [
            "Stell dir die Zahlen auf dem Zahlenstrahl vor.",
            "Weiter rechts liegt die größere Zahl.",
            "Die passende Antwort tippst du selbst an. Nichts ist markiert.",
        ]
    return [
        "Vergleiche die Zahlen von links, bei der größten Stelle zuerst.",
        "Die erste Stelle, die sich unterscheidet, entscheidet.",
        "Die größere Ziffer dort gehört zur größeren Zahl. Nichts ist markiert.",
    ]


def _fraction_pack(task: dict) -> tuple[list[str], dict | None]:
    meta = task["meta"]
    if meta.get("picture"):
        return [
            "Jedes Bild ist in gleich große Stücke geteilt.",
            "Zähle die gefärbten Stücke und alle Stücke.",
            "Suche das Bild, das zur Aufgabe passt. Es ist hier nicht markiert.",
        ], None
    if "fraction_num" in meta:
        figure = {
            "type": "fraction",
            "num": int(meta["fraction_num"]),
            "den": int(meta["fraction_den"]),
        }
        return [
            "Schau auf den Balken mit den gleich großen Stücken.",
            "Zähle alle Stücke. So viele hat das Ganze.",
            "Zähle die farbigen Stücke.",
            "Daraus liest du den Bruch. Den Namen suchst du selbst, nichts ist markiert.",
        ], figure
    numbers = meta.get("numbers") or []
    if len(numbers) >= 3:
        _num, den, whole = int(numbers[0]), int(numbers[1]), int(numbers[2])
        figure = {"type": "fraction", "num": int(numbers[0]), "den": den}
        return [
            "Der Balken zeigt gleich große Stücke. Die farbigen gehören dazu.",
            f"Teile {_fmt(whole)} in so viele Gruppen, wie der Balken Stücke hat.",
            "Nimm so viele Gruppen, wie Stücke farbig sind.",
            "Wie viele das sind, suchst du selbst. Keine Antwort ist markiert.",
        ], figure
    return [
        "Ein Bruch teilt ein Ganzes in gleich große Stücke.",
        "Schau, wie viele Stücke farbig sind und wie viele es insgesamt sind.",
        "Die passende Antwort suchst du selbst. Nichts ist markiert.",
    ], None


def _quiet(task: dict) -> tuple[list[str], dict | None, str]:
    mode = task["mode"]
    if mode == "uhr":
        return _clock_lines(int(task["grade"])), None, "So liest du die Uhr"
    if mode == "geld":
        return _money_lines(task), None, "So zählst du das Geld"
    if mode == "groessen":
        return _measure_lines(task), None, "So findest du es heraus"
    if mode == "formen":
        skill = task["meta"]["skill"]
        if skill in {"perimeter", "area"}:
            return _measure_lines(task), None, "So findest du es heraus"
        return _shape_lines(task), None, "So erkennst du die Form"
    if mode == "ordnen":
        return _order_lines(task), None, "So ordnest du die Zahlen"
    if mode == "wahl":
        skill = task["meta"]["skill"]
        if skill == "fraction":
            lines, figure = _fraction_pack(task)
            return lines, figure, "So siehst du den Bruch"
        lines, figure = _arith(task, False)
        return lines, figure, "So kannst du rechnen"
    raise AssertionError(mode)


def _titles_and_lines(task: dict) -> tuple[str, list[str], dict | None, bool, set[int], set[int]]:
    mode = task["mode"]
    grade = int(task["grade"])
    meta = task.get("meta") or {}
    skill = meta.get("skill")
    if mode in QUIET_MODES:
        lines, figure, title = _quiet(task)
        banned, allowed = _quiet_numbers(task)
        return title, lines, figure, False, banned, allowed
    if task.get("steps") and skill in {"written_add", "written_sub"}:
        lines, figure = _step_help(task)
        found = re.search(r"Ziffer (\d+)", lines[-1])
        write = int(found.group(1)) if found else 0
        allowed = {int(meta["a"]), int(meta["b"])}
        return "So machst du diese Stelle", lines, figure, True, {write}, allowed
    if grade <= 1 and skill in {"add", "sub"}:
        lines, figure = _arith(task, False)
        banned, allowed = _grade1_numbers(task)
        return "So kannst du es versuchen", lines, figure, False, banned, allowed
    lines, figure = _arith(task, True)
    banned, allowed = _reveal_numbers(task)
    title = "So findest du die Lücke" if "□" in (task.get("prompt") or "") else "So rechnest du"
    return title, lines, figure, True, banned, allowed


def _grade1_numbers(task: dict) -> tuple[set[int], set[int]]:
    meta = task["meta"]
    skill = meta["skill"]
    left, right, total = int(meta["a"]), int(meta["b"]), int(meta["result"])
    unknown = _unknown(task.get("prompt") or "")
    if skill == "add":
        if unknown == "left":
            return {left}, {right, total}
        if unknown == "right":
            return {right}, {left, total}
        return {total}, {left, right}
    if skill == "sub":
        if unknown == "left":
            return {left}, {right, total}
        if unknown == "right":
            return {right}, {left, total}
        return {total}, {left, right}
    return set(), set()


def _reveal_numbers(task: dict) -> tuple[set[int], set[int]]:
    meta = task["meta"]
    skill = meta["skill"]
    prompt = task.get("prompt") or ""
    unknown = _unknown(prompt)
    if skill in {"add", "written_add", "sub", "written_sub"}:
        left, right, total = int(meta["a"]), int(meta["b"]), int(meta["result"])
        if unknown == "left":
            answer = left
            allowed = {right, total}
        elif unknown == "right":
            answer = right
            allowed = {left, total}
        else:
            answer = total
            allowed = {left, right}
        return {answer}, allowed
    if skill == "mul":
        left, right = int(meta["a"]), int(meta["b"])
        product = left * right
        if unknown == "left":
            return {left}, {right, product}
        if unknown == "right":
            return {right}, {left, product}
        return {product}, {left, right}
    if skill == "div_exact":
        dividend = int(meta["dividend"])
        divisor = int(meta["divisor"])
        quotient = int(meta["quotient"])
        if unknown == "left":
            return {dividend}, {divisor, quotient}
        if unknown == "right":
            return {divisor}, {dividend, quotient}
        return {quotient}, {dividend, divisor}
    if skill == "div_rest":
        dividend = int(meta["dividend"])
        divisor = int(meta["divisor"])
        quotient = int(meta["q"])
        remainder = int(meta["r"])
        allowed = {dividend, divisor}
        banned = {quotient, remainder}
        return banned, allowed
    return set(), set()


def _quiet_numbers(task: dict) -> tuple[set[int], set[int]]:
    meta = task.get("meta") or {}
    skill = meta.get("skill")
    banned: set[int] = set()
    allowed: set[int] = set()
    if skill in {"add", "sub", "written_add", "written_sub"}:
        banned.add(int(meta["result"]))
        allowed.update({int(meta["a"]), int(meta["b"])})
    elif skill == "mul":
        banned.add(int(meta["a"]) * int(meta["b"]))
        allowed.update({int(meta["a"]), int(meta["b"])})
    elif skill == "div_exact":
        banned.add(int(meta["quotient"]))
        allowed.update({int(meta["dividend"]), int(meta["divisor"])})
    elif skill == "div_rest":
        banned.update({int(meta["q"]), int(meta["r"])})
        allowed.update({int(meta["dividend"]), int(meta["divisor"])})
    elif skill == "neighbor":
        banned.add(int(meta["result"]))
        allowed.add(int(meta["n"]))
    elif "result" in meta and isinstance(meta["result"], int):
        banned.add(int(meta["result"]))
    expect = task.get("expect") or {}
    if expect.get("type") == "int":
        banned.add(int(expect["value"]))
    if expect.get("type") == "euro":
        cents = int(expect["cents"])
        banned.add(cents)
        if cents % 100 == 0:
            banned.add(cents // 100)
    if expect.get("type") == "div":
        banned.update({int(expect["q"]), int(expect["r"])})
    return banned, allowed


def build_coach(task: dict) -> dict:
    title, lines, figure, reveal_last, banned, allowed = _titles_and_lines(task)
    if not lines:
        raise AssertionError("leere Hilfe")
    lines = _shield(lines, banned, allowed, task.get("solution") or "", reveal_last)
    coach = {"title": title, "lines": lines}
    if figure:
        coach["figure"] = figure
    return coach


def check_examples() -> None:
    lines = written_add_lines(347, 258, True, "Das Ergebnis ist")
    lines = _shield(lines, {605}, {347, 258}, "347 + 258 = 605", True)
    text = " ".join(lines)
    earlier = " ".join(lines[:-1])
    if "Hunderter" not in text or "Zehner" not in text or "Einer" not in text:
        raise AssertionError(text)
    if "Übertrag" not in text:
        raise AssertionError(text)
    if not lines[-1].endswith("605."):
        raise AssertionError(lines[-1])
    if _contains_number(earlier, 605):
        raise AssertionError(earlier)
    if "diese Zahl" in text:
        raise AssertionError(text)

    for a in range(0, 21):
        for b in range(0, 21 - a):
            sample = " ".join(grade1_add_lines(a, b))
            if a + b not in {a, b} and _contains_number(sample, a + b):
                raise AssertionError(f"Plus {a}+{b}: {sample}")
        for b in range(0, a + 1):
            sample = " ".join(grade1_sub_lines(a, b))
            if a - b not in {a, b} and _contains_number(sample, a - b):
                raise AssertionError(f"Minus {a}-{b}: {sample}")

    for unknown in ("left", "right"):
        for left in range(0, 21):
            for right in range(0, 21 - left):
                total = left + right
                sample = " ".join(_grade1_gap("add", left, right, total, unknown))
                missing = left if unknown == "left" else right
                known = {right, total} if unknown == "left" else {left, total}
                if missing not in known and _contains_number(sample, missing):
                    raise AssertionError(f"Lücke Plus {sample}")
            for right in range(0, left + 1):
                total = left - right
                sample = " ".join(_grade1_gap("sub", left, right, total, unknown))
                missing = left if unknown == "left" else right
                known = {right, total} if unknown == "left" else {left, total}
                if missing not in known and _contains_number(sample, missing):
                    raise AssertionError(f"Lücke Minus {sample}")

    for left in range(0, 120, 3):
        for right in range(0, 120, 5):
            total = left + right
            pack = halb_add_lines(left, right, True, "Das Ergebnis ist")
            pack = _shield(pack, {total}, {left, right}, "", True)
            if total not in {left, right} and len(_fmt(total)) >= 2 and _contains_number(" ".join(pack[:-1]), total):
                raise AssertionError(pack)
    for left in range(0, 120, 4):
        for right in range(0, left + 1, 5):
            total = left - right
            pack = halb_sub_lines(left, right, True, "Das Ergebnis ist")
            pack = _shield(pack, {total}, {left, right}, "", True)
            if total not in {left, right} and len(_fmt(total)) >= 2 and _contains_number(" ".join(pack[:-1]), total):
                raise AssertionError(pack)

    from mathe.tasks import add_steps, sub_steps

    for left in (0, 5, 19, 20, 99, 100, 347, 500, 999, 1000):
        for right in (0, 1, 8, 25, 258, 500, 1000):
            facts = _add_facts(left, right)
            again = add_steps(left, right)
            got = []
            for fact in facts:
                got.append(fact["write"])
            want = [step["expect"]["value"] for step in again]
            if got != want:
                raise AssertionError(f"{left}+{right}: {got} != {want}")
            if left >= right:
                got = [fact["write"] for fact in _sub_facts(left, right)]
                want = [step["expect"]["value"] for step in sub_steps(left, right)]
                if got != want:
                    raise AssertionError(f"{left}-{right}: {got} != {want}")
