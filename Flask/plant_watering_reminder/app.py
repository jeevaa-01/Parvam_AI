from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, flash, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "plants.json"

app = Flask(__name__)
app.secret_key = "plant-watering-reminder-dev-key"


def ensure_data_file() -> None:
    """Create the JSON store with starter data if it does not exist yet."""
    if DATA_FILE.exists():
        return

    starter_data = {
        "plants": [
            {
                "id": "1",
                "name": "Tulsi",
                "type": "Herb",
                "frequency_days": 2,
                "last_watered": "2025-08-01",
            },
            {
                "id": "2",
                "name": "Snake Plant",
                "type": "Indoor",
                "frequency_days": 7,
                "last_watered": str(date.today() - timedelta(days=4)),
            },
        ]
    }
    DATA_FILE.write_text(json.dumps(starter_data, indent=2), encoding="utf-8")


def load_plants() -> list[dict[str, Any]]:
    ensure_data_file()
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return data.get("plants", [])


def save_plants(plants: list[dict[str, Any]]) -> None:
    DATA_FILE.write_text(json.dumps({"plants": plants}, indent=2), encoding="utf-8")


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_plant_view(plant: dict[str, Any]) -> dict[str, Any]:
    today = date.today()
    last_watered = parse_iso_date(plant["last_watered"])
    next_water_date = last_watered + timedelta(days=int(plant["frequency_days"]))
    days_until = (next_water_date - today).days

    if days_until < 0:
        status = f"Overdue by {abs(days_until)} day{'s' if abs(days_until) != 1 else ''}"
        priority = 0
        badge_class = "badge-overdue"
    elif days_until == 0:
        status = "Due Today"
        priority = 1
        badge_class = "badge-due"
    elif days_until == 1:
        status = "Due Tomorrow"
        priority = 2
        badge_class = "badge-soon"
    else:
        status = f"Next in {days_until} days"
        priority = 3
        badge_class = "badge-ok"

    return {
        **plant,
        "next_water": next_water_date.isoformat(),
        "status": status,
        "is_urgent": priority < 2,
        "priority": priority,
        "badge_class": badge_class,
    }


def get_dashboard_plants() -> list[dict[str, Any]]:
    plants = [build_plant_view(plant) for plant in load_plants()]
    return sorted(plants, key=lambda plant: (plant["priority"], plant["next_water"], plant["name"].lower()))


@app.route("/")
def dashboard():
    plants = get_dashboard_plants()
    urgent_count = sum(1 for plant in plants if plant["is_urgent"])
    return render_template("dashboard.html", plants=plants, urgent_count=urgent_count, today=date.today().isoformat())


@app.route("/plants/add", methods=["POST"])
def add_plant():
    name = request.form.get("name", "").strip()
    plant_type = request.form.get("type", "").strip()
    frequency_raw = request.form.get("frequency_days", "").strip()
    last_watered = request.form.get("last_watered", "").strip()

    if not all([name, plant_type, frequency_raw, last_watered]):
        flash("All plant details are required.", "error")
        return redirect(url_for("dashboard"))

    try:
        frequency_days = int(frequency_raw)
        if frequency_days <= 0:
            raise ValueError
        parse_iso_date(last_watered)
    except ValueError:
        flash("Use a valid last-watered date and a watering frequency greater than 0.", "error")
        return redirect(url_for("dashboard"))

    plants = load_plants()
    next_id = str(max((int(plant["id"]) for plant in plants), default=0) + 1)
    plants.append(
        {
            "id": next_id,
            "name": name,
            "type": plant_type,
            "frequency_days": frequency_days,
            "last_watered": last_watered,
        }
    )
    save_plants(plants)
    flash(f"{name} has been added to your care list.", "success")
    return redirect(url_for("dashboard"))


@app.route("/plants/<plant_id>/water", methods=["POST"])
def water_plant(plant_id: str):
    plants = load_plants()
    updated = False

    for plant in plants:
        if plant["id"] == plant_id:
            plant["last_watered"] = date.today().isoformat()
            updated = True
            flash(f"{plant['name']} marked as watered today.", "success")
            break

    if updated:
        save_plants(plants)
    else:
        flash("Plant not found.", "error")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    ensure_data_file()
    app.run(debug=True)
