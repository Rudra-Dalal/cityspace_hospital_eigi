"""CLI ask command — sends a question to the CityCare AI patient assistant."""

import argparse
from typing import Any, Dict

from app.ai.patient_service import run_patient_chat
from cli.utils import db_context, load_current_user, print_json, resolve_token

# A minimal anonymous user used when no token is provided.
# run_patient_chat will still serve handbook-grounded answers without a patient_id match.
_ANON_USER: Dict[str, Any] = {"_id": "000000000000000000000000", "role": "customer"}


async def run(args: argparse.Namespace) -> None:
    """Ask the CityCare AI a question, optionally with patient context."""
    token = resolve_token(getattr(args, "token", None))
    question: str = args.question

    async with db_context():
        current_user = await load_current_user(token)
        # Fall back to an anonymous user so handbook RAG still works without auth
        if current_user is None:
            current_user = _ANON_USER

        answer, sources = await run_patient_chat(question, current_user)

    if args.json:
        print_json({"question": question, "answer": answer, "sources": sources})
    else:
        print("CityCare AI:")
        print()
        print(answer)
        if sources:
            print()
            print("Sources:")
            for src in sources:
                print(f"  - {src}")
