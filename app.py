"""Mathe-Trainer: lokale Flask-App mit serverseitigen Sessions."""

from __future__ import annotations

import os
import random
import re
import secrets

from flask import Flask, abort, g, redirect, render_template, request, url_for

from mathe.auth import check_password
from mathe.db import (
    SESSION_DAYS,
    DuplicateUser,
    close_db,
    create_child,
    create_session,
    delete_child,
    delete_session,
    ensure_init,
    list_users,
    progress_for_user,
    progress_overview,
    read_session,
    record_outcome,
    secret_key,
    skill_overview,
    update_best_streak,
    update_last_grade,
    update_user,
    user_by_id,
    user_by_username,
    write_session,
)
from mathe.practice import ROUND_SIZE, next_task, roll_round, round_identity
from mathe.tasks import MODES, mode_info, public_view, evaluate, skill_label, task_signature

SID_COOKIE = "mathe_sid"
CSRF_COOKIE = "mathe_csrf"
COOKIE_MAX_AGE = 60 * 60 * 24 * SESSION_DAYS

app = Flask(__name__)
app.secret_key = secret_key()
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


def safe_eq(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


def flash(message: str) -> None:
    if not getattr(g, "sid", None):
        return
    notes = g.sess.setdefault("flash", [])
    if len(notes) < 5:
        notes.append(message[:300])
    g.sess_dirty = True


def render(name: str, **context):
    notes = []
    if getattr(g, "sid", None):
        notes = g.sess.pop("flash", [])
        if notes:
            g.sess_dirty = True
    context["flashes"] = notes
    return render_template(name, **context)


def learner() -> dict:
    if g.user["role"] != "admin":
        return g.user
    wanted = g.sess.get("learner_id")
    person = user_by_id(int(wanted)) if wanted else None
    if person and person["role"] == "kind":
        return person
    for person in list_users():
        if person["role"] == "kind":
            g.sess["learner_id"] = person["id"]
            g.sess_dirty = True
            return person
    return g.user


def remember_task(task: dict, replay: bool) -> None:
    recent = list(g.sess.get("recent_sigs") or [])
    recent.insert(0, task_signature(task))
    g.sess["recent_sigs"] = recent[:8]
    g.sess["last_replay"] = bool(replay)
    g.sess_dirty = True


def round_memory_key(user_id: int, mode: str, grade: int) -> str:
    return f"{user_id}:{mode}:{grade}"


def remember_round(user_id: int, mode: str, grade: int, tasks: list[dict]) -> None:
    memory = dict(g.sess.get("round_memory") or {})
    memory[round_memory_key(user_id, mode, grade)] = [round_identity(task) for task in tasks]
    while len(memory) > 24:
        memory.pop(next(iter(memory)))
    g.sess["round_memory"] = memory


def previous_round(user_id: int, mode: str, grade: int) -> list[str]:
    memory = g.sess.get("round_memory") or {}
    found = memory.get(round_memory_key(user_id, mode, grade)) or []
    return list(found)


def take_queued_task(rnd: dict, mode: str, grade: int) -> dict:
    queue = list(rnd.get("queue") or [])
    if queue:
        task = queue.pop(0)
        rnd["queue"] = queue
        return task
    return draw_task(mode, grade)


def draw_task(mode: str, grade: int) -> dict:
    who = learner()
    task, replay = next_task(
        who["id"],
        mode,
        grade,
        list(g.sess.get("recent_sigs") or []),
        bool(g.sess.get("last_replay")),
    )
    remember_task(task, replay)
    return task


def finish_round(rnd: dict) -> None:
    solved = int(rnd.get("solved") or 0)
    length = int(rnd.get("length") or 1)
    good = solved * 5 >= length * 3
    rnd["active"] = False
    rnd["finished"] = True
    rnd["good"] = good
    rnd.pop("queue", None)
    if solved == length:
        text = f"Alle {length} Aufgaben geschafft. Toll gemacht!"
        fire = 3
    elif good:
        text = f"Du hast {solved} von {length} geschafft."
        fire = 2
    else:
        text = f"Schön geübt. Du hast {solved} von {length} geschafft."
        fire = 0
    g.sess["round"] = rnd
    g.sess["view"] = {"state": "round", "message": text, "fire_pending": fire}
    g.sess_dirty = True


def current_grade(user: dict) -> int:
    who = learner() if g.user else user
    raw = g.sess.get("grade", who.get("last_grade") or 1)
    try:
        grade = int(raw)
    except (TypeError, ValueError):
        grade = 1
    if grade not in (1, 2, 3, 4):
        grade = 1
    if g.sess.get("grade") != grade:
        g.sess["grade"] = grade
        g.sess_dirty = True
    return grade


def guard(role: str | None = None):
    if not g.user:
        return redirect(url_for("login"))
    if role and g.user["role"] != role:
        flash("Das ist nur für Erwachsene.")
        return redirect(url_for("trainer"))
    return None


def mode_cards(grade: int, stars: dict) -> list[dict]:
    cards = []
    for mode, title, text, minimum in MODES:
        cards.append(
            {
                "id": mode,
                "title": title,
                "text": text,
                "min_grade": minimum,
                "open": grade >= minimum,
                "stars": stars.get(mode, 0),
            }
        )
    return cards


def gentle(name: str) -> str:
    return random.choice(
        [
            f"Das war noch nicht ganz richtig, {name}. Versuch es noch einmal.",
            "Fast! Schau noch einmal genau hin.",
            "Nicht schlimm. Probier es gern noch einmal.",
            "Du schaffst das. Noch ein Versuch oder eine neue Aufgabe.",
        ]
    )


def praise(name: str, streak: int) -> str:
    if streak >= 5:
        pool = [
            f"Wahnsinn, {name}! Schon {streak} in Folge!",
            f"{streak} richtige Aufgaben hintereinander!",
            f"Du bist nicht zu stoppen, {name}!",
        ]
    elif streak >= 2:
        pool = [
            f"Schon {streak} in Folge, {name}!",
            f"Serie! Das ist Nummer {streak}.",
            f"Weiter so, {name}. {streak} Treffer hintereinander.",
        ]
    else:
        pool = [
            f"Super, {name}!",
            "Richtig! Das hast du toll gemacht.",
            f"Klasse, {name}!",
            "Hurra, das stimmt!",
            "Stark! Weiter so.",
        ]
    return random.choice(pool)


def fire_strength(streak: int) -> int:
    if streak >= 5:
        return 3
    if streak >= 2:
        return 2
    return 1


def bump_streak(mode: str, grade: int) -> int:
    if g.sess.get("streak_mode") != mode or g.sess.get("streak_grade") != grade:
        g.sess["streak"] = 0
        g.sess["streak_mode"] = mode
        g.sess["streak_grade"] = grade
    g.sess["streak"] = int(g.sess.get("streak") or 0) + 1
    return int(g.sess["streak"])


def clipped_form() -> dict:
    found = {}
    for key in ("answer", "q", "r"):
        value = (request.form.get(key) or "")[:40]
        if value:
            found[key] = value
    return found


def clean_username(raw: str) -> str:
    return (raw or "").strip().lower()


def valid_username(name: str) -> bool:
    return re.fullmatch(r"[a-z0-9_]{3,20}", name) is not None


def clean_display(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip()


def valid_display(name: str) -> bool:
    return re.fullmatch(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß' \-]{0,39}", name) is not None


def valid_password(password: str) -> bool:
    return 3 <= len(password) <= 100


def load_play(mode: str, grade: int, rnd: dict | None = None):
    task = g.sess.get("task")
    view = g.sess.get("view") or {"state": "open"}
    if not task or task.get("mode") != mode or int(task.get("grade", 0)) != grade:
        active = rnd or {}
        if active.get("active") and active.get("mode") == mode and int(active.get("grade") or 0) == grade:
            task = take_queued_task(active, mode, grade)
            g.sess["round"] = active
        else:
            task = draw_task(mode, grade)
        view = {"state": "open"}
        g.sess["task"] = task
        g.sess["view"] = view
        g.sess_dirty = True
    return task, view


@app.before_request
def prepare():
    if request.endpoint == "static":
        return
    ensure_init()
    g.sess_dirty = False
    g.clear_sid = False
    g.set_csrf = False
    g.user = None
    g.sid = None
    g.sess = {}
    cookie_csrf = request.cookies.get(CSRF_COOKIE, "")
    if not cookie_csrf:
        g.csrf = secrets.token_urlsafe(24)
        g.set_csrf = True
    else:
        g.csrf = cookie_csrf
    sid = request.cookies.get(SID_COOKIE, "")
    record = read_session(sid) if sid else None
    if record:
        g.sid = sid
        data = record["data"]
        g.sess = data if isinstance(data, dict) else {}
        g.user = user_by_id(record["user_id"])
        if g.user is None:
            delete_session(sid)
            g.sid = None
            g.sess = {}
            g.clear_sid = True
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not cookie_csrf or not sent or not safe_eq(cookie_csrf, sent):
            abort(400)


@app.after_request
def finish(response):
    if request.endpoint != "static":
        if getattr(g, "sess_dirty", False) and getattr(g, "sid", None):
            write_session(g.sid, g.sess)
        if getattr(g, "clear_sid", False):
            response.delete_cookie(SID_COOKIE, path="/")
        elif getattr(g, "sid", None):
            response.set_cookie(
                SID_COOKIE,
                g.sid,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                path="/",
            )
        if getattr(g, "set_csrf", False):
            response.set_cookie(
                CSRF_COOKIE,
                g.csrf,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                path="/",
            )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.teardown_appcontext
def teardown(exc):
    close_db(exc)


@app.context_processor
def inject():
    return {"csrf": getattr(g, "csrf", ""), "user": getattr(g, "user", None)}


@app.get("/")
def home():
    if not g.user:
        return redirect(url_for("login"))
    if g.user["role"] == "admin":
        return redirect(url_for("admin"))
    return redirect(url_for("trainer"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))
    error = ""
    if request.method == "POST":
        username = clean_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        if not username or not password:
            error = "Bitte schreibe den Namen und das Passwort."
        else:
            person = user_by_username(username)
            if check_password(person, password):
                if g.sid:
                    delete_session(g.sid)
                g.user = person
                g.sess = {"grade": person["last_grade"] or 1, "streak": 0}
                g.sid = create_session(person["id"], g.sess)
                g.clear_sid = False
                g.csrf = secrets.token_urlsafe(24)
                g.set_csrf = True
                return redirect(url_for("home"), code=303)
            error = "Das hat nicht geklappt. Schau noch einmal auf den Namen und das Passwort."
    return render("login.html", error=error)


@app.post("/logout")
def logout():
    if g.sid:
        delete_session(g.sid)
    g.sid = None
    g.user = None
    g.sess = {}
    g.sess_dirty = False
    g.clear_sid = True
    return redirect(url_for("login"), code=303)


@app.get("/trainer")
def trainer():
    blocked = guard()
    if blocked:
        return blocked
    who = learner()
    grade = current_grade(g.user)
    stars = {}
    total = 0
    for row in progress_for_user(who["id"]):
        total += row["correct"]
        if row["grade"] == grade:
            stars[row["mode"]] = row["correct"]
    kids = [person for person in list_users() if person["role"] == "kind"]
    return render(
        "trainer.html",
        grade=grade,
        cards=mode_cards(grade, stars),
        total=total,
        learner=who,
        kids=kids,
    )


@app.post("/klasse")
def klasse():
    blocked = guard()
    if blocked:
        return blocked
    try:
        grade = int(request.form.get("grade", "1"))
    except ValueError:
        grade = 1
    if grade not in (1, 2, 3, 4):
        grade = 1
    g.sess["grade"] = grade
    g.sess.pop("task", None)
    g.sess.pop("round", None)
    g.sess["view"] = {"state": "open"}
    g.sess_dirty = True
    update_last_grade(learner()["id"], grade)
    return redirect(url_for("trainer"), code=303)


@app.post("/spielen/<mode>/start")
def start(mode: str):
    blocked = guard()
    if blocked:
        return blocked
    info = mode_info(mode)
    if info is None:
        abort(404)
    grade = current_grade(g.user)
    if grade < info["min_grade"]:
        flash(f"Das übst du ab Klasse {info['min_grade']}.")
        return redirect(url_for("trainer"))
    g.sess.pop("round", None)
    g.sess["task"] = draw_task(mode, grade)
    g.sess["view"] = {"state": "open"}
    if g.sess.get("streak_mode") != mode or g.sess.get("streak_grade") != grade:
        g.sess["streak"] = 0
        g.sess["streak_mode"] = mode
        g.sess["streak_grade"] = grade
    g.sess_dirty = True
    return redirect(url_for("spielen", mode=mode), code=303)


@app.get("/spielen/<mode>")
def spielen(mode: str):
    blocked = guard()
    if blocked:
        return blocked
    info = mode_info(mode)
    if info is None:
        abort(404)
    rnd = g.sess.get("round") or {}
    if rnd.get("finished") and rnd.get("mode") == mode:
        view = g.sess.get("view") or {}
        fire = int(view.pop("fire_pending", 0) or 0)
        if fire:
            g.sess["view"] = view
            g.sess_dirty = True
        return render(
            "spielen.html",
            mode=mode,
            mode_title=info["title"],
            grade=int(rnd.get("grade") or 1),
            task=None,
            state="round",
            message=view.get("message", ""),
            previous={},
            show_solution=False,
            solution="",
            fire=fire,
            spark=0,
            streak=0,
            in_round=False,
            round_index=int(rnd.get("length") or 0),
            round_length=int(rnd.get("length") or 0),
        )
    grade = current_grade(g.user)
    if grade < info["min_grade"]:
        flash(f"Das übst du ab Klasse {info['min_grade']}.")
        return redirect(url_for("trainer"))
    if rnd.get("active") and rnd.get("mode") == mode and int(rnd.get("grade") or 0) != grade:
        g.sess.pop("round", None)
        rnd = {}
    task, view = load_play(mode, grade, rnd)
    fire = int(view.pop("fire_pending", 0) or 0)
    spark = int(view.pop("spark_pending", 0) or 0)
    if fire or spark:
        g.sess["view"] = view
        g.sess_dirty = True
    show = view.get("state") == "success"
    same = g.sess.get("streak_mode") == mode and g.sess.get("streak_grade") == grade
    streak = int(g.sess.get("streak") or 0) if same else 0
    return render(
        "spielen.html",
        mode=mode,
        mode_title=info["title"],
        grade=grade,
        task=public_view(task),
        state=view.get("state", "open"),
        message=view.get("message", ""),
        previous=view.get("previous") or {},
        show_solution=show,
        solution=task.get("solution", "") if show else "",
        fire=fire,
        spark=spark,
        streak=streak,
        in_round=bool(rnd.get("active") and rnd.get("mode") == mode),
        round_index=int(rnd.get("index") or 0),
        round_length=int(rnd.get("length") or 0),
    )


@app.post("/spielen/<mode>/pruefen")
def pruefen(mode: str):
    blocked = guard()
    if blocked:
        return blocked
    info = mode_info(mode)
    if info is None:
        abort(404)
    grade = current_grade(g.user)
    task = g.sess.get("task")
    view = g.sess.get("view") or {}
    if not task or task.get("mode") != mode or int(task.get("grade", 0)) != grade:
        return redirect(url_for("spielen", mode=mode))
    if view.get("state") == "success":
        return redirect(url_for("spielen", mode=mode))
    if request.form.get("token") != task.get("token"):
        flash("Diese Aufgabe ist schon vorbei.")
        return redirect(url_for("spielen", mode=mode))
    status, hint = evaluate(task, request.form)
    who = learner()
    name = who["display_name"]
    if status in {"empty", "invalid"}:
        g.sess["view"] = {
            "state": "retry",
            "message": hint,
            "previous": clipped_form(),
        }
    elif status == "wrong":
        if not task.get("noted"):
            record_outcome(who["id"], task, False)
            task["noted"] = True
        g.sess["streak"] = 0
        g.sess["view"] = {
            "state": "retry",
            "message": gentle(name),
            "previous": clipped_form(),
        }
    elif status == "step":
        g.sess["view"] = {
            "state": "step",
            "message": "Genau! Weiter zum nächsten Schritt.",
            "spark_pending": 1,
        }
    elif status == "correct":
        record_outcome(who["id"], task, True)
        streak = bump_streak(mode, grade)
        if streak > int(who["best_streak"] or 0):
            update_best_streak(who["id"], streak)
            who["best_streak"] = streak
        g.sess["view"] = {
            "state": "success",
            "message": praise(name, streak),
            "fire_pending": fire_strength(streak),
        }
    else:
        abort(500)
    g.sess["task"] = task
    g.sess_dirty = True
    return redirect(url_for("spielen", mode=mode), code=303)


@app.post("/spielen/<mode>/neu")
def neu(mode: str):
    blocked = guard()
    if blocked:
        return blocked
    info = mode_info(mode)
    if info is None:
        abort(404)
    grade = current_grade(g.user)
    if grade < info["min_grade"]:
        return redirect(url_for("trainer"))
    rnd = g.sess.get("round") or {}
    if rnd.get("active") and rnd.get("mode") == mode:
        view = g.sess.get("view") or {}
        state = view.get("state")
        if state == "success":
            rnd["solved"] = int(rnd.get("solved") or 0) + 1
            rnd["done"] = int(rnd.get("done") or 0) + 1
        elif state == "retry":
            rnd["done"] = int(rnd.get("done") or 0) + 1
        else:
            g.sess["task"] = draw_task(mode, grade)
            g.sess["view"] = {"state": "open"}
            g.sess["round"] = rnd
            g.sess_dirty = True
            return redirect(url_for("spielen", mode=mode), code=303)
        if int(rnd["done"]) >= int(rnd["length"]):
            finish_round(rnd)
            return redirect(url_for("spielen", mode=mode), code=303)
        rnd["index"] = int(rnd["done"]) + 1
        task = take_queued_task(rnd, mode, grade)
        g.sess["round"] = rnd
        g.sess["task"] = task
        remember_task(task, False)
        g.sess["view"] = {"state": "open"}
        g.sess_dirty = True
        return redirect(url_for("spielen", mode=mode), code=303)
    g.sess["task"] = draw_task(mode, grade)
    g.sess["view"] = {"state": "open"}
    g.sess_dirty = True
    return redirect(url_for("spielen", mode=mode), code=303)


@app.post("/runde/<mode>")
def runde(mode: str):
    blocked = guard()
    if blocked:
        return blocked
    info = mode_info(mode)
    if info is None:
        abort(404)
    grade = current_grade(g.user)
    if grade < info["min_grade"]:
        flash(f"Das übst du ab Klasse {info['min_grade']}.")
        return redirect(url_for("trainer"))
    who = learner()
    tasks = roll_round(who["id"], mode, grade, previous_round(who["id"], mode, grade), ROUND_SIZE)
    remember_round(who["id"], mode, grade, tasks)
    g.sess["round"] = {
        "active": True,
        "finished": False,
        "mode": mode,
        "grade": grade,
        "length": ROUND_SIZE,
        "index": 1,
        "done": 0,
        "solved": 0,
        "learner_id": who["id"],
        "queue": tasks[1:],
    }
    g.sess["streak"] = 0
    g.sess["streak_mode"] = mode
    g.sess["streak_grade"] = grade
    g.sess["task"] = tasks[0]
    remember_task(tasks[0], False)
    g.sess["view"] = {"state": "open"}
    g.sess_dirty = True
    return redirect(url_for("spielen", mode=mode), code=303)


@app.post("/lernen")
def lernen():
    blocked = guard("admin")
    if blocked:
        return blocked
    try:
        uid = int(request.form.get("learner_id", "0"))
    except ValueError:
        abort(400)
    person = user_by_id(uid)
    if person is None or person["role"] != "kind":
        abort(404)
    g.sess["learner_id"] = person["id"]
    g.sess.pop("task", None)
    g.sess.pop("round", None)
    g.sess["view"] = {"state": "open"}
    g.sess_dirty = True
    flash(f"Die Aufgaben zählen jetzt für {person['display_name']}.")
    return redirect(url_for("trainer"), code=303)


@app.get("/admin")
def admin():
    blocked = guard("admin")
    if blocked:
        return blocked
    return render("admin.html", people=list_users())


@app.get("/admin/fortschritt")
def fortschritt():
    blocked = guard("admin")
    if blocked:
        return blocked
    modes = [{"id": mode, "title": title} for mode, title, _text, _min in MODES]
    blocks = []
    for block in progress_overview():
        grid = {grade: {mode["id"]: None for mode in modes} for grade in (1, 2, 3, 4)}
        total_c = 0
        total_w = 0
        for row in block["rows"]:
            if row["grade"] in grid and row["mode"] in grid[row["grade"]]:
                grid[row["grade"]][row["mode"]] = row
            total_c += row["correct"]
            total_w += row["wrong"]
        blocks.append(
            {
                "user": block["user"],
                "grid": grid,
                "total_c": total_c,
                "total_w": total_w,
                "stats": [],
                "mistakes": [],
            }
        )
    titles = {mode: title for mode, title, _text, _min in MODES}
    extra = {item["user"]["id"]: item for item in skill_overview()}
    for block in blocks:
        item = extra.get(block["user"]["id"]) or {}
        block["stats"] = [
            {
                "grade": row["grade"],
                "mode": titles.get(row["mode"], row["mode"]),
                "skill": skill_label(row["skill"]),
                "correct": row["correct"],
                "wrong": row["wrong"],
            }
            for row in item.get("stats") or []
        ]
        block["mistakes"] = [
            {
                "grade": row["grade"],
                "mode": titles.get(row["mode"], row["mode"]),
                "skill": skill_label(row["skill"]),
                "prompt": row["prompt"],
                "open": row["resolved_at"] is None,
            }
            for row in item.get("mistakes") or []
        ]
    return render("fortschritt.html", blocks=blocks, modes=modes)


@app.route("/admin/kinder/neu", methods=["GET", "POST"])
def kind_neu():
    blocked = guard("admin")
    if blocked:
        return blocked
    error = ""
    display_name = ""
    username = ""
    if request.method == "POST":
        display_name = clean_display(request.form.get("display_name", ""))
        username = clean_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        if not valid_display(display_name):
            error = "Der Name darf Buchstaben, Leerzeichen und Bindestriche haben."
        elif not valid_username(username):
            error = "Der Benutzername braucht 3 bis 20 kleine Buchstaben oder Zahlen."
        elif not valid_password(password):
            error = "Das Passwort braucht mindestens 3 Zeichen."
        elif user_by_username(username):
            error = "Diesen Benutzernamen gibt es schon."
        else:
            try:
                create_child(username, display_name, password)
            except DuplicateUser:
                error = "Diesen Benutzernamen gibt es schon."
            else:
                flash(f"{display_name} kann sich jetzt anmelden.")
                return redirect(url_for("admin"), code=303)
    return render(
        "kind_form.html",
        error=error,
        display_name=display_name,
        username=username,
        person=None,
    )


@app.route("/admin/kinder/<int:uid>", methods=["GET", "POST"])
def kind_edit(uid: int):
    blocked = guard("admin")
    if blocked:
        return blocked
    person = user_by_id(uid)
    if person is None:
        abort(404)
    error = ""
    display_name = person["display_name"]
    username = person["username"]
    if request.method == "POST":
        display_name = clean_display(request.form.get("display_name", ""))
        password = request.form.get("password", "")
        if person["role"] == "kind":
            username = clean_username(request.form.get("username", ""))
        if not valid_display(display_name):
            error = "Der Name darf Buchstaben, Leerzeichen und Bindestriche haben."
        elif person["role"] == "kind" and not valid_username(username):
            error = "Der Benutzername braucht 3 bis 20 kleine Buchstaben oder Zahlen."
        elif password and not valid_password(password):
            error = "Das Passwort braucht mindestens 3 Zeichen."
        else:
            other = user_by_username(username)
            if other and other["id"] != person["id"]:
                error = "Diesen Benutzernamen gibt es schon."
            else:
                try:
                    if person["role"] == "admin":
                        update_user(
                            person["id"],
                            display_name=display_name,
                            password=password or None,
                        )
                    else:
                        update_user(
                            person["id"],
                            display_name=display_name,
                            username=username,
                            password=password or None,
                        )
                except DuplicateUser:
                    error = "Diesen Benutzernamen gibt es schon."
                else:
                    flash("Gespeichert.")
                    return redirect(url_for("admin"), code=303)
    return render(
        "kind_form.html",
        error=error,
        display_name=display_name,
        username=username,
        person=person,
    )


@app.route("/admin/kinder/<int:uid>/loeschen", methods=["GET", "POST"])
def kind_loeschen(uid: int):
    blocked = guard("admin")
    if blocked:
        return blocked
    person = user_by_id(uid)
    if person is None or person["role"] != "kind":
        abort(404)
    if request.method == "POST":
        if delete_child(uid):
            flash(f"{person['display_name']} wurde gelöscht.")
        return redirect(url_for("admin"), code=303)
    return render("loeschen.html", person=person)


@app.errorhandler(400)
def err400(_exc):
    return (
        render_template(
            "error.html",
            title="Bitte noch einmal",
            text="Die Seite braucht einen neuen Versuch. Geh zurück und lade sie neu.",
        ),
        400,
    )


@app.errorhandler(403)
def err403(_exc):
    return (
        render_template(
            "error.html",
            title="Das geht hier nicht",
            text="Diese Seite ist nicht für dich.",
        ),
        403,
    )


@app.errorhandler(404)
def err404(_exc):
    return (
        render_template(
            "error.html",
            title="Diese Seite gibt es nicht",
            text="Geh zurück zur Übersicht.",
        ),
        404,
    )


@app.errorhandler(500)
def err500(_exc):
    return (
        render_template(
            "error.html",
            title="Das hat nicht geklappt",
            text="Bitte versuch es noch einmal.",
        ),
        500,
    )


if __name__ == "__main__":
    ensure_init()
    host = os.environ.get("MATHE_HOST", "127.0.0.1")
    port = int(os.environ.get("MATHE_PORT", "5050"))
    print(f"Mathe-Trainer: http://{host}:{port}", flush=True)
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
