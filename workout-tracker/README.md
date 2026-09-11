# Workout Tracker

A small learning project for recording gym-specific machine settings and workout performance.
The interface is built with [NiceGUI](https://nicegui.io/) and all data is stored locally in
SQLite.

## Features

- Add gyms and exercises.
- Build reusable workout templates such as Push A or Leg Day.
- Store several machine adjustments for every gym/exercise combination.
- Start a workout by choosing a gym and template.
- See the machine settings and the weight/reps used during the previous session at that gym.
- Record sets, finish sessions, and browse recent workout history.
- Switch between the original light theme and a charcoal dark theme with orange-red accents.

## Run locally

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

NiceGUI prints the local address in the terminal (normally `http://localhost:8080`). The app
creates `data/workout_tracker.db` on first launch. That database is intentionally ignored by
Git so personal workout data stays local.

The selected color theme is remembered in the browser. For a shared or deployed installation,
set `WORKOUT_TRACKER_STORAGE_SECRET` to a private random value before starting the app.

## Project structure

```text
workout-tracker/
├── app.py              # NiceGUI pages and event handlers
├── database.py         # SQLite queries and small CRUD functions
├── schema.sql          # Tables, constraints, and indexes
├── requirements.txt    # Python dependency
├── README.md           # Setup and project documentation
└── .gitignore          # Local database and Python artifacts
```

The project deliberately avoids an ORM and a large framework structure. UI code calls a small
database module, making the SQL visible and easy to learn.

## Database model

- `gyms`: training locations.
- `exercises`: reusable movements.
- `workout_templates`: named workout days.
- `template_exercises`: ordered exercises and targets within a template.
- `machine_settings`: flexible name/value adjustments scoped to a gym and exercise.
- `workout_sessions`: dated instances of a template performed at a gym.
- `workout_sets`: weight and reps recorded for an exercise in a session.

Templates are independent from gyms. This means one Push A template can be used everywhere,
while the machine settings shown during the workout change with the selected gym.
