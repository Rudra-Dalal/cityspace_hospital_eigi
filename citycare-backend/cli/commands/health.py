"""CLI health command — verifies backend configuration and MongoDB connectivity."""

import argparse
from typing import Any, Dict

from app.core.config import get_settings
from cli.utils import db_context, print_json, print_key_value


async def run(args: argparse.Namespace) -> None:
    """Check backend config and MongoDB reachability."""
    settings = get_settings()
    result: Dict[str, Any] = {
        "backend": "OK",
        "clinic": settings.clinic_name,
        "environment": settings.app_env,
        "database": "unavailable",
    }

    try:
        async with db_context():
            result["database"] = "OK"
    except Exception:
        # DB is not reachable — report gracefully without traceback
        result["database"] = "unavailable"

    if args.json:
        print_json(result)
    else:
        db_status = "[OK]" if result["database"] == "OK" else "[X]"
        print(f"CityCare Clinic -- Health Check")
        print(f"  Backend     : {result['backend']}")
        print(f"  Clinic      : {result['clinic']}")
        print(f"  Environment : {result['environment']}")
        print(f"  Database    : {db_status} {result['database']}")
