from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Callable

from nicegui import app, ui

import database as db


db.initialize_database()

ui.add_head_html(
    """
    <style>
        :root {
            --app-radius: 18px;
            --app-control-radius: 12px;
        }

        body,
        .q-layout,
        .q-page-container {
            transition: background-color 180ms ease, color 180ms ease;
        }

        .app-header {
            box-shadow: 0 1px 0 rgba(15, 23, 42, 0.12), 0 8px 24px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(14px);
        }

        .q-card {
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: var(--app-radius) !important;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.07) !important;
            transition: background-color 180ms ease, border-color 180ms ease,
                        box-shadow 180ms ease, transform 180ms ease;
        }

        .q-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 34px rgba(15, 23, 42, 0.10) !important;
        }

        .q-btn {
            border-radius: var(--app-control-radius) !important;
            letter-spacing: 0.01em;
        }

        .q-btn--round {
            border-radius: 50% !important;
        }

        .q-field--outlined .q-field__control,
        .q-field--filled .q-field__control,
        .q-field--standard .q-field__control {
            border-radius: var(--app-control-radius) !important;
        }

        .q-menu,
        .q-notification {
            border-radius: var(--app-control-radius) !important;
        }

        body.body--dark,
        .body--dark .q-layout,
        .body--dark .q-page-container {
            background: #0b0b0d !important;
            color: #f4f4f5;
        }

        .body--dark .app-header {
            background: rgba(17, 17, 19, 0.96) !important;
            border-bottom: 1px solid #2a2a2e;
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.32);
        }

        .body--dark .q-card {
            background: #171719 !important;
            border-color: #2c2c31;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28) !important;
        }

        .body--dark .q-card:hover {
            border-color: #3a3a40;
            box-shadow: 0 14px 38px rgba(0, 0, 0, 0.38) !important;
        }

        .body--dark .q-field__control {
            background: #121214;
        }

        .body--dark .q-field__native,
        .body--dark .q-field__input,
        .body--dark .q-field__label {
            color: #eeeeef;
        }

        .body--dark .q-field__control::before {
            border-color: #3a3a40 !important;
        }

        .body--dark .q-field--focused .q-field__control::after {
            border-color: #f0643f !important;
        }

        .body--dark .q-btn.bg-primary {
            background: linear-gradient(135deg, #ef5b38, #d9482b) !important;
            box-shadow: 0 6px 18px rgba(239, 91, 56, 0.20);
        }

        .body--dark .q-btn.text-primary {
            color: #ff7654 !important;
        }

        .body--dark .text-grey-7,
        .body--dark .text-grey-6 {
            color: #a7a7ae !important;
        }

        .body--dark .text-orange-8 {
            color: #ff8a5f !important;
        }

        .body--dark .border-grey-3 {
            border-color: #303035 !important;
        }

        .body--dark .q-separator {
            background: #303035;
        }

        @media (max-width: 760px) {
            .app-header {
                gap: 0.15rem;
                overflow-x: auto;
                flex-wrap: nowrap;
            }

            .app-header .q-btn {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
            }
        }
    </style>
    """,
    shared=True,
)


def navigation() -> None:
    app.storage.user.setdefault("dark_mode", False)
    dark_mode = ui.dark_mode(app.storage.user["dark_mode"]).bind_value(
        app.storage.user, "dark_mode"
    )
    with ui.header().classes("app-header items-center"):
        ui.icon("fitness_center", size="sm")
        ui.label("Workout Tracker").classes("text-h6 whitespace-nowrap")
        ui.space()
        for label, target in (
            ("Today", "/"),
            ("Gyms", "/gyms"),
            ("Exercises", "/exercises"),
            ("Templates", "/templates"),
            ("Machine settings", "/settings"),
            ("History", "/history"),
        ):
            ui.button(label, on_click=lambda path=target: ui.navigate.to(path)).props("flat color=white")
        ui.button(icon="contrast", on_click=dark_mode.toggle).props(
            "flat round color=white aria-label='Toggle dark mode'"
        ).tooltip("Toggle light/dark mode")


def page_title(title: str, subtitle: str = "") -> None:
    ui.label(title).classes("text-h4 font-bold")
    if subtitle:
        ui.label(subtitle).classes("text-grey-7 mb-4")


def notify_database_error(error: sqlite3.IntegrityError) -> None:
    message = str(error)
    if "UNIQUE constraint failed" in message:
        ui.notify("That item already exists.", type="negative")
    elif "FOREIGN KEY constraint failed" in message:
        ui.notify("This item is already used and cannot be deleted.", type="negative")
    else:
        ui.notify(message, type="negative")


def options(rows: list[dict], label_key: str = "name") -> dict[int, str]:
    return {row["id"]: row[label_key] for row in rows}


@ui.page("/")
def home_page() -> None:
    navigation()
    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-4"):
        page_title("Train today", "Choose a gym and workout day, then record your sets.")
        gyms = db.list_gyms()
        templates = db.list_templates()

        if not gyms or not templates:
            ui.label("Add at least one gym and one workout template before starting.").classes(
                "text-orange-8"
            )
            with ui.row():
                ui.button("Add a gym", on_click=lambda: ui.navigate.to("/gyms"))
                ui.button("Build a template", on_click=lambda: ui.navigate.to("/templates"))
            return

        gym = ui.select(options(gyms), label="Gym").classes("w-full")
        template = ui.select(options(templates), label="Workout day").classes("w-full")

        def start_workout() -> None:
            if gym.value is None or template.value is None:
                ui.notify("Select both a gym and a workout day.", type="warning")
                return
            session_id = db.create_session(int(gym.value), int(template.value))
            ui.navigate.to(f"/session/{session_id}")

        ui.button("Start workout", icon="fitness_center", on_click=start_workout).props("unelevated")


def simple_management_page(
    title: str,
    subtitle: str,
    load_rows: Callable[[], list[dict]],
    add_row: Callable[[str, str], int],
    delete_row: Callable[[int], None],
    second_label: str,
) -> None:
    navigation()
    with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
        page_title(title, subtitle)
        name = ui.input("Name").classes("w-full")
        second = ui.input(second_label).classes("w-full")

        def save() -> None:
            if not name.value or not name.value.strip():
                ui.notify("A name is required.", type="warning")
                return
            try:
                add_row(name.value, second.value or "")
            except sqlite3.IntegrityError as error:
                notify_database_error(error)
                return
            ui.notify("Saved", type="positive")
            ui.navigate.reload()

        ui.button("Add", on_click=save)
        ui.separator().classes("my-4")
        rows = load_rows()
        if not rows:
            ui.label("Nothing added yet.").classes("text-grey-7")
        for row in rows:
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("gap-0"):
                        ui.label(row["name"]).classes("font-medium")
                        detail = row.get("notes") or row.get("muscle_group") or ""
                        if detail:
                            ui.label(detail).classes("text-sm text-grey-7")
                    ui.space()

                    def remove(row_id: int = row["id"]) -> None:
                        try:
                            delete_row(row_id)
                        except sqlite3.IntegrityError as error:
                            notify_database_error(error)
                            return
                        ui.navigate.reload()

                    ui.button(icon="delete", on_click=remove).props("flat round color=negative")


@ui.page("/gyms")
def gyms_page() -> None:
    simple_management_page(
        "Gyms",
        "Add the places where you train.",
        db.list_gyms,
        db.add_gym,
        db.delete_gym,
        "Notes (optional)",
    )


@ui.page("/exercises")
def exercises_page() -> None:
    simple_management_page(
        "Exercises",
        "Create the exercises used by your workout templates.",
        db.list_exercises,
        lambda name, group: db.add_exercise(name, group),
        db.delete_exercise,
        "Muscle group (optional)",
    )


@ui.page("/templates")
def templates_page() -> None:
    navigation()
    with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
        page_title("Workout templates", "Create workout days and add exercises in training order.")
        template_name = ui.input("New template name (for example Push A)").classes("w-full")
        template_notes = ui.input("Notes (optional)").classes("w-full")

        def create_template() -> None:
            if not template_name.value or not template_name.value.strip():
                ui.notify("A template name is required.", type="warning")
                return
            try:
                db.add_template(template_name.value, template_notes.value or "")
            except sqlite3.IntegrityError as error:
                notify_database_error(error)
                return
            ui.navigate.reload()

        ui.button("Create template", on_click=create_template)
        ui.separator().classes("my-4")

        templates = db.list_templates()
        exercises = db.list_exercises()
        if not templates:
            ui.label("No templates yet.").classes("text-grey-7")
            return

        for template in templates:
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center"):
                    ui.label(template["name"]).classes("text-h6")
                    ui.space()

                    def remove_template(template_id: int = template["id"]) -> None:
                        try:
                            db.delete_template(template_id)
                        except sqlite3.IntegrityError as error:
                            notify_database_error(error)
                            return
                        ui.navigate.reload()

                    ui.button(icon="delete", on_click=remove_template).props(
                        "flat round color=negative"
                    )

                template_items = db.list_template_exercises(template["id"])
                for item in template_items:
                    with ui.row().classes("w-full items-center border-b border-grey-3 py-2"):
                        ui.label(f'{item["position"]}. {item["exercise_name"]}')
                        ui.label(f'{item["target_sets"]} sets × {item["target_reps"]} reps').classes(
                            "text-grey-7"
                        )
                        ui.space()

                        def remove_item(item_id: int = item["id"]) -> None:
                            db.remove_template_exercise(item_id)
                            ui.navigate.reload()

                        ui.button(icon="close", on_click=remove_item).props("flat round dense")

                if not exercises:
                    ui.label("Add exercises before filling this template.").classes("text-orange-8")
                    continue
                exercise = ui.select(options(exercises), label="Exercise").classes("w-64")
                target_sets = ui.number("Sets", value=3, min=1, step=1).classes("w-28")
                target_reps = ui.input("Target reps", value="8-12").classes("w-32")

                def add_item(
                    template_id: int = template["id"],
                    exercise_select=exercise,
                    sets_input=target_sets,
                    reps_input=target_reps,
                ) -> None:
                    if exercise_select.value is None:
                        ui.notify("Select an exercise.", type="warning")
                        return
                    try:
                        db.add_template_exercise(
                            template_id,
                            int(exercise_select.value),
                            int(sets_input.value or 1),
                            reps_input.value or "",
                        )
                    except sqlite3.IntegrityError as error:
                        notify_database_error(error)
                        return
                    ui.navigate.reload()

                ui.button("Add exercise", icon="add", on_click=add_item).props("flat")


@ui.page("/settings")
def settings_page() -> None:
    navigation()
    with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
        page_title(
            "Machine settings",
            "Save equipment adjustments for each gym and exercise. Reusing a name updates its value.",
        )
        gyms = db.list_gyms()
        exercises = db.list_exercises()
        if not gyms or not exercises:
            ui.label("Add at least one gym and one exercise first.").classes("text-orange-8")
            return

        gym = ui.select(options(gyms), label="Gym").classes("w-full")
        exercise = ui.select(options(exercises), label="Exercise").classes("w-full")
        setting_name = ui.input("Setting name (for example Seat)").classes("w-full")
        setting_value = ui.input("Value (for example 4)").classes("w-full")

        def save_setting() -> None:
            if gym.value is None or exercise.value is None:
                ui.notify("Select a gym and exercise.", type="warning")
                return
            if not setting_name.value or not setting_name.value.strip():
                ui.notify("A setting name is required.", type="warning")
                return
            if setting_value.value is None or not str(setting_value.value).strip():
                ui.notify("A value is required.", type="warning")
                return
            db.save_machine_setting(
                int(gym.value),
                int(exercise.value),
                setting_name.value,
                str(setting_value.value),
            )
            ui.navigate.reload()

        ui.button("Save setting", on_click=save_setting)
        ui.separator().classes("my-4")
        for setting in db.list_machine_settings():
            with ui.row().classes("w-full items-center border-b border-grey-3 py-2"):
                ui.label(f'{setting["gym_name"]} · {setting["exercise_name"]}').classes(
                    "font-medium w-72"
                )
                ui.label(f'{setting["setting_name"]}: {setting["setting_value"]}')
                ui.space()

                def remove_setting(setting_id: int = setting["id"]) -> None:
                    db.delete_machine_setting(setting_id)
                    ui.navigate.reload()

                ui.button(icon="delete", on_click=remove_setting).props("flat round color=negative")


@ui.page("/session/{session_id}")
def session_page(session_id: int) -> None:
    navigation()
    session = db.get_session(session_id)
    with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
        if session is None:
            page_title("Workout not found")
            ui.button("Back home", on_click=lambda: ui.navigate.to("/"))
            return

        page_title(
            session["template_name"],
            f'{session["gym_name"]} · started {session["started_at"].replace("T", " ")}',
        )
        template_items = db.list_template_exercises(session["template_id"])
        if not template_items:
            ui.label("This template has no exercises yet.").classes("text-orange-8")

        for item in template_items:
            with ui.card().classes("w-full"):
                ui.label(item["exercise_name"]).classes("text-h6")
                ui.label(
                    f'Target: {item["target_sets"]} sets × {item["target_reps"]} reps'
                ).classes("text-grey-7")

                settings = db.list_machine_settings(session["gym_id"], item["exercise_id"])
                if settings:
                    ui.label("Machine settings").classes("font-medium mt-2")
                    ui.label(" · ".join(f'{s["setting_name"]}: {s["setting_value"]}' for s in settings))
                else:
                    ui.label("No machine settings saved for this gym.").classes("text-grey-6")

                previous_session, old_sets = db.previous_sets(
                    session_id, session["gym_id"], item["exercise_id"]
                )
                if previous_session:
                    previous_date = datetime.fromisoformat(previous_session["started_at"]).strftime(
                        "%Y-%m-%d"
                    )
                    ui.label(f"Last time here ({previous_date})").classes("font-medium mt-2")
                    ui.label(
                        " · ".join(f'{s["weight"]:g} kg × {s["reps"]}' for s in old_sets)
                    ).classes("text-grey-7")
                else:
                    ui.label("No previous sets recorded at this gym.").classes("text-grey-6")

                current_sets = db.list_session_sets(session_id, item["exercise_id"])
                set_inputs: list[tuple] = []
                for set_number in range(1, item["target_sets"] + 1):
                    saved = next((s for s in current_sets if s["set_number"] == set_number), None)
                    previous = next((s for s in old_sets if s["set_number"] == set_number), None)
                    with ui.row().classes("items-center"):
                        ui.label(f"Set {set_number}").classes("w-14")
                        weight = ui.number(
                            "Weight (kg)",
                            value=saved["weight"] if saved else (previous["weight"] if previous else None),
                            min=0,
                            step=0.5,
                        ).classes("w-40")
                        reps = ui.number(
                            "Reps",
                            value=saved["reps"] if saved else (previous["reps"] if previous else None),
                            min=0,
                            step=1,
                        ).classes("w-32")
                        set_inputs.append((set_number, weight, reps))

                def save_sets(
                    exercise_id: int = item["exercise_id"],
                    inputs: list[tuple] = set_inputs,
                ) -> None:
                    completed: list[tuple[int, float, int]] = []
                    for set_number, weight_input, reps_input in inputs:
                        if weight_input.value is None and reps_input.value is None:
                            continue
                        if weight_input.value is None or reps_input.value is None:
                            ui.notify("Enter both weight and reps for each set.", type="warning")
                            return
                        completed.append(
                            (set_number, float(weight_input.value), int(reps_input.value))
                        )
                    db.save_exercise_sets(session_id, exercise_id, completed)
                    ui.notify("Sets saved", type="positive")

                ui.button("Save sets", icon="save", on_click=save_sets).props("flat")

        notes = ui.textarea("Workout notes (optional)").classes("w-full")

        def complete_workout() -> None:
            db.finish_session(session_id, notes.value or "")
            ui.notify("Workout completed", type="positive")
            ui.navigate.to("/history")

        ui.button("Finish workout", icon="check", on_click=complete_workout).props(
            "unelevated color=positive"
        )


@ui.page("/history")
def history_page() -> None:
    navigation()
    with ui.column().classes("w-full max-w-4xl mx-auto p-6"):
        page_title("Workout history", "Your 20 most recent sessions.")
        sessions = db.list_sessions()
        if not sessions:
            ui.label("No workouts recorded yet.").classes("text-grey-7")
        for session in sessions:
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("gap-0"):
                        ui.label(session["template_name"]).classes("font-medium")
                        date = datetime.fromisoformat(session["started_at"]).strftime("%Y-%m-%d %H:%M")
                        status = "finished" if session["finished_at"] else "in progress"
                        ui.label(
                            f'{session["gym_name"]} · {date} · {session["recorded_sets"]} sets · {status}'
                        ).classes("text-sm text-grey-7")
                    ui.space()
                    ui.button(
                        "Open", on_click=lambda session_id=session["id"]: ui.navigate.to(
                            f"/session/{session_id}"
                        )
                    ).props("flat")


ui.run(
    title="Workout Tracker",
    favicon="🏋️",
    reload=False,
    storage_secret=os.environ.get(
        "WORKOUT_TRACKER_STORAGE_SECRET", "workout-tracker-local-development"
    ),
)
