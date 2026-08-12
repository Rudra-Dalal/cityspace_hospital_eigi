"""CLI doctors command — lists clinic doctor info and registered doctors."""

import argparse
from typing import Any, Dict, List

from app.controllers import doctor_controller
from app.cruds import user_crud
from cli.utils import db_context, print_json, print_key_value, print_table


async def run(args: argparse.Namespace) -> None:
    """List clinic doctor info and registered doctor accounts."""
    async with db_context():
        # Get static clinic/doctor configuration
        info = doctor_controller.get_doctor_info()

        # Fetch all doctor users from the DB
        doctor_users: List[Dict[str, Any]] = await user_crud.list_users(role="doctor")

    if args.json:
        data = {
            "clinic_info": info.model_dump(),
            "doctors": [
                {
                    "id": str(d.get("_id", "")),
                    "name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                    "email": d.get("email", ""),
                    "hospital_id": d.get("hospital_id", ""),
                }
                for d in doctor_users
            ],
        }
        print_json(data)
    else:
        print("=== CityCare Clinic Info ===")
        print_key_value(
            {
                "Clinic": info.clinic_name,
                "Location": info.clinic_location,
                "Morning Hours": info.morning_hours,
                "Evening Hours": info.evening_hours,
                "Slot Duration": f"{info.slot_duration_minutes} min",
            }
        )

        print()
        print("=== Registered Doctors ===")
        if not doctor_users:
            print("  (no doctors registered)")
        else:
            rows = [
                {
                    "Name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                    "Qualification": info.qualification,
                    "Email": d.get("email", ""),
                    "Hospital ID": d.get("hospital_id", "N/A"),
                }
                for d in doctor_users
            ]
            print_table(rows, ["Name", "Qualification", "Email", "Hospital ID"])
