"""CityCare CLI — entry point.

Usage:
    python -m cli.main --help
    python -m cli.main health [--json]
    python -m cli.main doctors [--json]
    python -m cli.main appointments [--token <JWT>] [--json]
    python -m cli.main prescriptions [--token <JWT>] [--json]
    python -m cli.main ask "question" [--token <JWT>] [--json]
"""

import argparse
import asyncio
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="citycare",
        description="CityCare Clinic — Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.main health
  python -m cli.main doctors --json
  python -m cli.main appointments --token <JWT>
  python -m cli.main prescriptions --token <JWT>
  python -m cli.main ask "What are the consultation hours?"
  python -m cli.main ask "Show my prescriptions" --token <JWT>

Authentication:
  Private commands (appointments, prescriptions) require a valid JWT.
  Pass it with --token <JWT> or set the CITYCARE_JWT_TOKEN environment variable.
""",
    )

    # Global --json flag (not on subparser so it appears in main --help too)
    # Subparsers also add --json individually to keep things clean.
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # ------------------------------------------------------------------ health
    health_parser = subparsers.add_parser(
        "health",
        help="Check backend configuration and database connectivity",
        description="Verify that the backend is configured correctly and MongoDB is reachable.",
    )
    health_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # ----------------------------------------------------------------- doctors
    doctors_parser = subparsers.add_parser(
        "doctors",
        help="List clinic info and registered doctors",
        description="Display clinic information and all registered doctor accounts.",
    )
    doctors_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # ------------------------------------------------------------ appointments
    appt_parser = subparsers.add_parser(
        "appointments",
        help="List your appointments (requires authentication)",
        description=(
            "Patients see their own appointments; doctors/managers see the schedule. "
            "Requires a valid JWT via --token or CITYCARE_JWT_TOKEN env var."
        ),
    )
    appt_parser.add_argument(
        "--token", metavar="JWT", help="JWT access token (overrides CITYCARE_JWT_TOKEN)"
    )
    appt_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # ----------------------------------------------------------- prescriptions
    rx_parser = subparsers.add_parser(
        "prescriptions",
        help="List your prescriptions (requires authentication)",
        description=(
            "Lists all prescriptions for the authenticated patient. "
            "Requires a valid JWT via --token or CITYCARE_JWT_TOKEN env var."
        ),
    )
    rx_parser.add_argument(
        "--token", metavar="JWT", help="JWT access token (overrides CITYCARE_JWT_TOKEN)"
    )
    rx_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    # ----------------------------------------------------------------------- ask
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask the CityCare AI a question",
        description=(
            "Sends a question to the CityCare AI assistant. "
            "General clinic questions work without authentication; "
            "personal prescription queries require a valid JWT."
        ),
    )
    ask_parser.add_argument("question", help="The question to ask")
    ask_parser.add_argument(
        "--token", metavar="JWT", help="JWT access token for personalized answers"
    )
    ask_parser.add_argument(
        "--json", action="store_true", help="Output result as JSON"
    )

    return parser


async def _dispatch(args: argparse.Namespace) -> None:
    """Route parsed args to the correct command handler."""
    if args.command == "health":
        from cli.commands.health import run
    elif args.command == "doctors":
        from cli.commands.doctors import run
    elif args.command == "appointments":
        from cli.commands.appointments import run
    elif args.command == "prescriptions":
        from cli.commands.prescriptions import run
    elif args.command == "ask":
        from cli.commands.ask import run
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

    await run(args)  # type: ignore[arg-type]


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(_dispatch(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
