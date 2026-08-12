"""CLI appointments command — lists appointments for the authenticated user."""

import argparse
from typing import Any, Dict, List

from app.controllers import appointment_controller, doctor_controller
from cli.utils import db_context, load_current_user, print_json, print_table, resolve_token

_AUTH_REQUIRED_MSG = "Authentication required to access patient appointments."
_PATIENT_ROLES = ("customer", "patient")
_STAFF_ROLES = ("doctor", "hospital_manager", "super_admin")


async def run(args: argparse.Namespace) -> None:
    """List appointments — patients see their own, staff see the schedule."""
    token = resolve_token(getattr(args, "token", None))

    async with db_context():
        current_user = await load_current_user(token)

        if not current_user:
            print(_AUTH_REQUIRED_MSG)
            return

        role = current_user.get("role", "")

        if role in _PATIENT_ROLES:
            appointments = await appointment_controller.list_my_appointments(current_user)
        elif role in _STAFF_ROLES:
            appointments = await doctor_controller.get_schedule(None, current_user)
        else:
            print(_AUTH_REQUIRED_MSG)
            return

    if args.json:
        records = [a.model_dump() for a in appointments]
        print_json(records)
    else:
        if not appointments:
            print("No appointments found.")
            return

        role = current_user.get("role", "")

        if role in _PATIENT_ROLES:
            rows = [
                {
                    "Date": a.date,
                    "Slot": a.slot,
                    "Reason": a.reason[:40],
                    "Status": a.status.value,
                }
                for a in appointments
            ]
            print(f"=== Your Appointments ({len(rows)}) ===")
            print_table(rows, ["Date", "Slot", "Reason", "Status"])
        else:
            rows = [
                {
                    "Date": a.date,
                    "Slot": a.slot,
                    "Patient": a.patient_name,
                    "Reason": a.reason[:35],
                    "Status": a.status.value,
                }
                for a in appointments
            ]
            print(f"=== Schedule ({len(rows)} upcoming appointments) ===")
            print_table(rows, ["Date", "Slot", "Patient", "Reason", "Status"])
