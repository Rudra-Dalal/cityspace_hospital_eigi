"""CLI prescriptions command — lists prescriptions for the authenticated patient."""

import argparse

from app.controllers import prescription_controller
from cli.utils import db_context, load_current_user, print_json, print_table, resolve_token

_AUTH_REQUIRED_MSG = "Authentication required to access patient prescriptions."
_PATIENT_ROLES = ("customer", "patient")


async def run(args: argparse.Namespace) -> None:
    """List prescriptions for the authenticated patient."""
    token = resolve_token(getattr(args, "token", None))

    async with db_context():
        current_user = await load_current_user(token)

        if not current_user:
            print(_AUTH_REQUIRED_MSG)
            return

        role = current_user.get("role", "")
        if role not in _PATIENT_ROLES:
            print(_AUTH_REQUIRED_MSG)
            return

        prescriptions = await prescription_controller.mine(current_user)

    if args.json:
        records = [p.model_dump() for p in prescriptions]
        print_json(records)
    else:
        if not prescriptions:
            print("No prescriptions found.")
            return

        rows = [
            {
                "Date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "N/A",
                "Doctor": p.doctor_name or "N/A",
                "Diagnosis": p.diagnosis[:45],
                "Medicines": str(len(p.medicines)),
                "PDF": "Yes" if p.pdf_url else "No",
            }
            for p in prescriptions
        ]

        print(f"=== Your Prescriptions ({len(rows)}) ===")
        print_table(rows, ["Date", "Doctor", "Diagnosis", "Medicines", "PDF"])
