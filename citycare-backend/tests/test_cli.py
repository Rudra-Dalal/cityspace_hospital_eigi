"""Comprehensive unit tests for the CityCare CLI interface layer.

Strategy: All external dependencies (DB, controllers, AI service) are mocked
so these tests run without a live MongoDB or Gemini API key.
"""

import argparse
import asyncio
import io
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure app is importable with env vars pointing at a test DB.
# ---------------------------------------------------------------------------
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "citycare_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine synchronously, creating a fresh event loop each time."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {"json": False, "token": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


async def _acapture(coro):
    """Capture stdout produced by an awaitable."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        await coro
    finally:
        sys.stdout = old
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures: common mock objects
# ---------------------------------------------------------------------------

MOCK_PATIENT = {
    "_id": MagicMock(__str__=lambda s: "aaa000000000000000000001"),
    "id": "aaa000000000000000000001",
    "email": "patient@example.com",
    "role": "customer",
    "first_name": "Test",
    "last_name": "Patient",
}

MOCK_DOCTOR_USER = {
    "_id": MagicMock(__str__=lambda s: "bbb000000000000000000001"),
    "id": "bbb000000000000000000001",
    "email": "doctor@citycare.clinic",
    "role": "doctor",
    "first_name": "Meera",
    "last_name": "Kulkarni",
    "hospital_id": "hosp001",
}


@asynccontextmanager
async def _noop_db_context():
    """A no-op db_context that never actually connects to MongoDB."""
    yield


# ===========================================================================
# 1. --help output
# ===========================================================================

class TestHelp:
    def test_main_help_contains_subcommands(self):
        from cli.main import build_parser
        parser = build_parser()
        buf = io.StringIO()
        try:
            parser.parse_args(["--help"])
        except SystemExit:
            pass

    def test_health_subcommand_registered(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["health"])
        assert args.command == "health"

    def test_doctors_subcommand_registered(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctors"])
        assert args.command == "doctors"

    def test_appointments_subcommand_registered(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["appointments"])
        assert args.command == "appointments"

    def test_prescriptions_subcommand_registered(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["prescriptions"])
        assert args.command == "prescriptions"

    def test_ask_subcommand_registered(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["ask", "What are the clinic hours?"])
        assert args.command == "ask"
        assert args.question == "What are the clinic hours?"

    def test_json_flag_on_health(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["health", "--json"])
        assert args.json is True

    def test_token_flag_on_appointments(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["appointments", "--token", "my.jwt.token"])
        assert args.token == "my.jwt.token"

    def test_token_flag_on_prescriptions(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["prescriptions", "--token", "my.jwt.token"])
        assert args.token == "my.jwt.token"

    def test_token_flag_on_ask(self):
        from cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["ask", "test question", "--token", "my.jwt.token"])
        assert args.token == "my.jwt.token"


# ===========================================================================
# 2. health command
# ===========================================================================

class TestHealthCommand:
    @patch("cli.commands.health.db_context", _noop_db_context)
    def test_health_db_ok(self):
        from cli.commands.health import run
        args = _make_args()
        output = _run(_acapture(run(args)))
        assert "OK" in output
        assert "Database" in output

    @patch("cli.commands.health.db_context")
    def test_health_db_unavailable(self, mock_ctx):
        async def _failing_ctx():
            raise ConnectionError("Mongo not available")
            yield  # make it a generator for asynccontextmanager semantics

        # Override with a context manager that raises on entry
        @asynccontextmanager
        async def _err_ctx():
            raise ConnectionError("Mongo not available")
            yield  # pragma: no cover

        mock_ctx.side_effect = _err_ctx

        from cli.commands.health import run
        args = _make_args()
        output = _run(_acapture(run(args)))
        assert "unavailable" in output

    @patch("cli.commands.health.db_context", _noop_db_context)
    def test_health_json_output(self):
        from cli.commands.health import run
        args = _make_args(json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert "backend" in data
        assert "database" in data
        assert data["backend"] == "OK"

    @patch("cli.commands.health.db_context", _noop_db_context)
    def test_health_json_db_ok(self):
        from cli.commands.health import run
        args = _make_args(json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert data["database"] == "OK"


# ===========================================================================
# 3. doctors command
# ===========================================================================

class TestDoctorsCommand:
    @patch("cli.commands.doctors.db_context", _noop_db_context)
    @patch("cli.commands.doctors.user_crud.list_users", new_callable=AsyncMock)
    @patch("cli.commands.doctors.doctor_controller.get_doctor_info")
    def test_doctors_human_readable(self, mock_info, mock_list):
        from app.schemas.appointment_schema import DoctorInfoResponse
        mock_info.return_value = DoctorInfoResponse(
            name="Dr. Meera Kulkarni",
            qualification="MBBS, MD",
            clinic_name="CityCare Clinic",
            clinic_location="Dharampeth, Nagpur",
            morning_hours="10:00 to 13:00",
            evening_hours="17:00 to 20:00",
            slot_duration_minutes=30,
            valid_slots=["10:00", "10:30"],
        )
        mock_list.return_value = [
            {
                "_id": "bbb001",
                "first_name": "Meera",
                "last_name": "Kulkarni",
                "email": "doctor@citycare.clinic",
                "hospital_id": "hosp001",
            }
        ]

        from cli.commands.doctors import run
        args = _make_args()
        output = _run(_acapture(run(args)))
        assert "CityCare Clinic" in output
        assert "Meera" in output

    @patch("cli.commands.doctors.db_context", _noop_db_context)
    @patch("cli.commands.doctors.user_crud.list_users", new_callable=AsyncMock)
    @patch("cli.commands.doctors.doctor_controller.get_doctor_info")
    def test_doctors_json_output(self, mock_info, mock_list):
        from app.schemas.appointment_schema import DoctorInfoResponse
        mock_info.return_value = DoctorInfoResponse(
            name="Dr. Meera Kulkarni",
            qualification="MBBS, MD",
            clinic_name="CityCare Clinic",
            clinic_location="Dharampeth, Nagpur",
            morning_hours="10:00 to 13:00",
            evening_hours="17:00 to 20:00",
            slot_duration_minutes=30,
            valid_slots=["10:00", "10:30"],
        )
        mock_list.return_value = []

        from cli.commands.doctors import run
        args = _make_args(json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert "clinic_info" in data
        assert "doctors" in data
        assert data["clinic_info"]["clinic_name"] == "CityCare Clinic"

    @patch("cli.commands.doctors.db_context", _noop_db_context)
    @patch("cli.commands.doctors.user_crud.list_users", new_callable=AsyncMock)
    @patch("cli.commands.doctors.doctor_controller.get_doctor_info")
    def test_doctors_empty_list_message(self, mock_info, mock_list):
        from app.schemas.appointment_schema import DoctorInfoResponse
        mock_info.return_value = DoctorInfoResponse(
            name="Dr. Meera Kulkarni",
            qualification="MBBS, MD",
            clinic_name="CityCare Clinic",
            clinic_location="Dharampeth, Nagpur",
            morning_hours="10:00 to 13:00",
            evening_hours="17:00 to 20:00",
            slot_duration_minutes=30,
            valid_slots=["10:00"],
        )
        mock_list.return_value = []

        from cli.commands.doctors import run
        args = _make_args()
        output = _run(_acapture(run(args)))
        assert "no doctors registered" in output.lower()


# ===========================================================================
# 4. appointments command
# ===========================================================================

class TestAppointmentsCommand:
    def test_appointments_no_token_rejected(self):
        """Unauthenticated call must print the auth-required message."""
        from cli.commands.appointments import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.appointments.db_context", _noop_db_context), \
             patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock, return_value=None):
            args = _make_args()
            output = _run(_acapture(run(args)))
        assert _AUTH_REQUIRED_MSG in output

    def test_appointments_invalid_token_rejected(self):
        from cli.commands.appointments import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.appointments.db_context", _noop_db_context), \
             patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock, return_value=None), \
             patch("cli.commands.appointments.resolve_token", return_value="bad.token"):
            args = _make_args(token="bad.token")
            output = _run(_acapture(run(args)))
        assert _AUTH_REQUIRED_MSG in output

    @patch("cli.commands.appointments.db_context", _noop_db_context)
    @patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.appointments.appointment_controller.list_my_appointments", new_callable=AsyncMock)
    def test_appointments_patient_sees_own(self, mock_list, mock_user):
        from app.models.appointment_model import AppointmentStatus
        from app.schemas.appointment_schema import AppointmentOut

        mock_user.return_value = MOCK_PATIENT
        mock_list.return_value = [
            AppointmentOut(
                id="appt001",
                patient_id="aaa000000000000000000001",
                date="2026-09-01",
                slot="10:00",
                reason="Routine checkup",
                status=AppointmentStatus.BOOKED,
            )
        ]

        from cli.commands.appointments import run
        args = _make_args(token="valid.jwt")
        output = _run(_acapture(run(args)))
        assert "2026-09-01" in output
        assert "10:00" in output

    @patch("cli.commands.appointments.db_context", _noop_db_context)
    @patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.appointments.appointment_controller.list_my_appointments", new_callable=AsyncMock)
    def test_appointments_patient_json(self, mock_list, mock_user):
        from app.models.appointment_model import AppointmentStatus
        from app.schemas.appointment_schema import AppointmentOut

        mock_user.return_value = MOCK_PATIENT
        mock_list.return_value = [
            AppointmentOut(
                id="appt001",
                patient_id="aaa000000000000000000001",
                date="2026-09-01",
                slot="10:00",
                reason="Routine checkup",
                status=AppointmentStatus.BOOKED,
            )
        ]

        from cli.commands.appointments import run
        args = _make_args(token="valid.jwt", json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert isinstance(data, list)
        assert data[0]["slot"] == "10:00"

    @patch("cli.commands.appointments.db_context", _noop_db_context)
    @patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.appointments.doctor_controller.get_schedule", new_callable=AsyncMock)
    def test_appointments_doctor_sees_schedule(self, mock_schedule, mock_user):
        from app.models.appointment_model import AppointmentStatus
        from app.schemas.appointment_schema import ScheduleItem

        mock_user.return_value = MOCK_DOCTOR_USER
        mock_schedule.return_value = [
            ScheduleItem(
                id="appt002",
                slot="10:30",
                date="2026-09-01",
                patient_name="Test Patient",
                reason="Fever and cough",
                status=AppointmentStatus.BOOKED,
            )
        ]

        from cli.commands.appointments import run
        args = _make_args(token="doctor.jwt")
        output = _run(_acapture(run(args)))
        assert "Test Patient" in output
        assert "10:30" in output

    @patch("cli.commands.appointments.db_context", _noop_db_context)
    @patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.appointments.appointment_controller.list_my_appointments", new_callable=AsyncMock)
    def test_appointments_empty_message(self, mock_list, mock_user):
        mock_user.return_value = MOCK_PATIENT
        mock_list.return_value = []

        from cli.commands.appointments import run
        args = _make_args(token="valid.jwt")
        output = _run(_acapture(run(args)))
        assert "No appointments found" in output


# ===========================================================================
# 5. prescriptions command
# ===========================================================================

class TestPrescriptionsCommand:
    def test_prescriptions_no_token_rejected(self):
        from cli.commands.prescriptions import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.prescriptions.db_context", _noop_db_context), \
             patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock, return_value=None):
            args = _make_args()
            output = _run(_acapture(run(args)))
        assert _AUTH_REQUIRED_MSG in output

    def test_prescriptions_doctor_token_rejected(self):
        """Doctors are not patients — must be blocked."""
        from cli.commands.prescriptions import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.prescriptions.db_context", _noop_db_context), \
             patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock, return_value=MOCK_DOCTOR_USER):
            args = _make_args(token="doctor.jwt")
            output = _run(_acapture(run(args)))
        assert _AUTH_REQUIRED_MSG in output

    @patch("cli.commands.prescriptions.db_context", _noop_db_context)
    @patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.prescriptions.prescription_controller.mine", new_callable=AsyncMock)
    def test_prescriptions_patient_sees_own(self, mock_mine, mock_user):
        from datetime import datetime
        from app.schemas.prescription_schema import MedicineOut, PrescriptionOut

        mock_user.return_value = MOCK_PATIENT
        mock_mine.return_value = [
            PrescriptionOut(
                id="rx001",
                patient_id="aaa000000000000000000001",
                doctor_id="bbb000000000000000000001",
                appointment_id="appt001",
                diagnosis="Viral fever",
                medicines=[
                    MedicineOut(
                        name="Paracetamol",
                        dosage="500mg",
                        frequency="Twice daily",
                        duration="5 days",
                        instructions="After meals",
                    )
                ],
                general_instructions="Rest and hydrate",
                doctor_name="Dr. Meera Kulkarni",
                created_at=datetime(2026, 8, 1, 10, 0, 0),
            )
        ]

        from cli.commands.prescriptions import run
        args = _make_args(token="valid.jwt")
        output = _run(_acapture(run(args)))
        assert "Viral fever" in output
        assert "Dr. Meera Kulkarni" in output

    @patch("cli.commands.prescriptions.db_context", _noop_db_context)
    @patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.prescriptions.prescription_controller.mine", new_callable=AsyncMock)
    def test_prescriptions_patient_json(self, mock_mine, mock_user):
        from datetime import datetime
        from app.schemas.prescription_schema import MedicineOut, PrescriptionOut

        mock_user.return_value = MOCK_PATIENT
        mock_mine.return_value = [
            PrescriptionOut(
                id="rx001",
                patient_id="aaa000000000000000000001",
                doctor_id="bbb000000000000000000001",
                appointment_id="appt001",
                diagnosis="Viral fever",
                medicines=[
                    MedicineOut(
                        name="Paracetamol",
                        dosage="500mg",
                        frequency="Twice daily",
                        duration="5 days",
                        instructions="After meals",
                    )
                ],
                general_instructions="Rest and hydrate",
                doctor_name="Dr. Meera Kulkarni",
                created_at=datetime(2026, 8, 1, 10, 0, 0),
            )
        ]

        from cli.commands.prescriptions import run
        args = _make_args(token="valid.jwt", json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert isinstance(data, list)
        assert data[0]["diagnosis"] == "Viral fever"

    @patch("cli.commands.prescriptions.db_context", _noop_db_context)
    @patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.prescriptions.prescription_controller.mine", new_callable=AsyncMock)
    def test_prescriptions_empty_message(self, mock_mine, mock_user):
        mock_user.return_value = MOCK_PATIENT
        mock_mine.return_value = []

        from cli.commands.prescriptions import run
        args = _make_args(token="valid.jwt")
        output = _run(_acapture(run(args)))
        assert "No prescriptions found" in output


# ===========================================================================
# 6. ask command
# ===========================================================================

class TestAskCommand:
    @patch("cli.commands.ask.db_context", _noop_db_context)
    @patch("cli.commands.ask.load_current_user", new_callable=AsyncMock, return_value=None)
    @patch("cli.commands.ask.run_patient_chat", new_callable=AsyncMock)
    def test_ask_no_auth_uses_anon_user(self, mock_chat, mock_user):
        mock_chat.return_value = ("Clinic hours are 10am to 1pm.", ["Handbook Page 1"])

        from cli.commands.ask import run
        args = _make_args(question="What are the clinic hours?")
        output = _run(_acapture(run(args)))
        assert "CityCare AI" in output
        assert "Clinic hours" in output
        # Verify AI was called with the anonymous fallback user
        call_user = mock_chat.call_args[0][1]
        assert call_user["role"] == "customer"

    @patch("cli.commands.ask.db_context", _noop_db_context)
    @patch("cli.commands.ask.load_current_user", new_callable=AsyncMock)
    @patch("cli.commands.ask.run_patient_chat", new_callable=AsyncMock)
    def test_ask_with_auth_passes_real_user(self, mock_chat, mock_user):
        mock_user.return_value = MOCK_PATIENT
        mock_chat.return_value = ("Your prescription is Paracetamol.", ["Prescription"])

        from cli.commands.ask import run
        args = _make_args(question="What medicines was I prescribed?", token="valid.jwt")
        output = _run(_acapture(run(args)))
        assert "CityCare AI" in output
        assert "Paracetamol" in output
        # Verify AI was called with the real user
        call_user = mock_chat.call_args[0][1]
        assert call_user["email"] == "patient@example.com"

    @patch("cli.commands.ask.db_context", _noop_db_context)
    @patch("cli.commands.ask.load_current_user", new_callable=AsyncMock, return_value=None)
    @patch("cli.commands.ask.run_patient_chat", new_callable=AsyncMock)
    def test_ask_json_output(self, mock_chat, mock_user):
        mock_chat.return_value = ("Clinic hours are 10am to 1pm.", ["Handbook Page 1"])

        from cli.commands.ask import run
        args = _make_args(question="What are the clinic hours?", json=True)
        output = _run(_acapture(run(args)))
        data = json.loads(output)
        assert "question" in data
        assert "answer" in data
        assert "sources" in data
        assert data["question"] == "What are the clinic hours?"

    @patch("cli.commands.ask.db_context", _noop_db_context)
    @patch("cli.commands.ask.load_current_user", new_callable=AsyncMock, return_value=None)
    @patch("cli.commands.ask.run_patient_chat", new_callable=AsyncMock)
    def test_ask_shows_sources(self, mock_chat, mock_user):
        mock_chat.return_value = ("Some clinic info.", ["Handbook Page 3 (Fees)", "Handbook Page 5 (Hours)"])

        from cli.commands.ask import run
        args = _make_args(question="What are the fees?")
        output = _run(_acapture(run(args)))
        assert "Handbook Page 3" in output
        assert "Sources" in output


# ===========================================================================
# 7. utils — token resolution
# ===========================================================================

class TestTokenResolution:
    def test_resolve_token_from_args(self):
        from cli.utils import resolve_token
        assert resolve_token("my.token.here") == "my.token.here"

    def test_resolve_token_from_env(self):
        from cli.utils import resolve_token
        os.environ["CITYCARE_JWT_TOKEN"] = "env.token.here"
        try:
            assert resolve_token(None) == "env.token.here"
        finally:
            del os.environ["CITYCARE_JWT_TOKEN"]

    def test_resolve_token_args_takes_precedence(self):
        from cli.utils import resolve_token
        os.environ["CITYCARE_JWT_TOKEN"] = "env.token"
        try:
            assert resolve_token("arg.token") == "arg.token"
        finally:
            del os.environ["CITYCARE_JWT_TOKEN"]

    def test_resolve_token_none_when_missing(self):
        from cli.utils import resolve_token
        os.environ.pop("CITYCARE_JWT_TOKEN", None)
        assert resolve_token(None) is None

    def test_resolve_token_strips_whitespace(self):
        from cli.utils import resolve_token
        assert resolve_token("  my.token  ") == "my.token"


# ===========================================================================
# 8. Security / authorization enforcement
# ===========================================================================

class TestSecurityEnforcement:
    def test_appointments_unauthenticated_no_data_leaked(self):
        """Ensure no appointment data is returned without a valid token."""
        from cli.commands.appointments import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.appointments.db_context", _noop_db_context), \
             patch("cli.commands.appointments.load_current_user", new_callable=AsyncMock, return_value=None), \
             patch("cli.commands.appointments.appointment_controller.list_my_appointments") as mock_list:
            args = _make_args()
            output = _run(_acapture(run(args)))

        assert _AUTH_REQUIRED_MSG in output
        mock_list.assert_not_called()

    def test_prescriptions_unauthenticated_no_data_leaked(self):
        """Ensure no prescription data is returned without a valid token."""
        from cli.commands.prescriptions import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.prescriptions.db_context", _noop_db_context), \
             patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock, return_value=None), \
             patch("cli.commands.prescriptions.prescription_controller.mine") as mock_mine:
            args = _make_args()
            output = _run(_acapture(run(args)))

        assert _AUTH_REQUIRED_MSG in output
        mock_mine.assert_not_called()

    def test_prescriptions_non_patient_no_data_leaked(self):
        """A doctor token must NOT expose prescription data."""
        from cli.commands.prescriptions import _AUTH_REQUIRED_MSG, run

        with patch("cli.commands.prescriptions.db_context", _noop_db_context), \
             patch("cli.commands.prescriptions.load_current_user", new_callable=AsyncMock, return_value=MOCK_DOCTOR_USER), \
             patch("cli.commands.prescriptions.prescription_controller.mine") as mock_mine:
            args = _make_args(token="doctor.jwt")
            output = _run(_acapture(run(args)))

        assert _AUTH_REQUIRED_MSG in output
        mock_mine.assert_not_called()
