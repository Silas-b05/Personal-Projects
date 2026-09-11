# Workout Tracker

A small learning project for recording gym-specific machine settings and workout performance.
The interface is built with [NiceGUI](https://nicegui.io/) and data is stored in Turso using its
SQLite-compatible libSQL service.

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
export TURSO_DATABASE_URL="libsql://your-database.turso.io"
export TURSO_AUTH_TOKEN="your-token"
python app.py
```

NiceGUI prints the local address in the terminal (normally `http://localhost:8080`). Create the
database URL and token in Turso before starting the app. Never place the real values in source
files; local `.env` files are ignored by Git.

The selected color theme is remembered in the browser. For a shared or deployed installation,
set `WORKOUT_TRACKER_STORAGE_SECRET` to a private random value before starting the app.

## Use on iPhone

Open the app's address in Safari, tap **Share**, then choose **Add to Home Screen**. The mobile
layout accounts for the iPhone safe areas and provides a fixed bottom navigation bar for quick
access during workouts. Keep the computer running the app and the iPhone on a network that can
reach it.

## Project structure

```text
workout-tracker/
├── app.py              # NiceGUI pages and event handlers
├── database.py         # Turso connection, SQLite queries, and small CRUD functions
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

## Deploy on Render

The repository includes a root-level `render.yaml` Blueprint. In Render, create a new Blueprint,
connect the `Personal-Projects` repository, and approve the proposed `workout-tracker` service.
Render will build and start the app from this subdirectory automatically.

The Blueprint uses Render's free web-service plan. Workout data remains in Turso, so Render's
ephemeral filesystem does not affect it.

The deployed service uses these environment variables:

- `PORT`: provided automatically by Render and used by NiceGUI.
- `WORKOUT_TRACKER_STORAGE_SECRET`: generated automatically by the Blueprint.
- `TURSO_DATABASE_URL`: your Turso database URL, such as `libsql://...`.
- `TURSO_AUTH_TOKEN`: a token created for that Turso database.

For a new Blueprint, Render prompts for the two Turso values. For an existing Render service, add
them manually under **Environment** and redeploy. The values are secrets and are never stored in
this repository.

The app has no login screen, so anyone with the public Render URL can use and change its data.
