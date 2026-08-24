"""Idempotent startup migration: seeds CityCare hospital & migrates legacy data."""

from datetime import datetime, timezone

from app.core.config import VALID_SLOTS, get_settings
from app.core.database import get_database
from app.models.hospital_model import hospital_document
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_migrations() -> None:
    """
    Safe to run on every startup — all operations are idempotent and non-destructive.

    Steps:
    1. Create default hospital if collection is empty, or non-destructively backfill missing fields.
    2. Assign hospital_id and doctor profile fields to seeded doctor.
    3. Backfill existing appointments with hospital_id + doctor_id.
    4. Rename legacy role 'patient' → 'customer' in users collection.
    5. Backfill is_active=True on users missing the field.
    """
    db = get_database()
    settings = get_settings()

    # ------------------------------------------------------------------
    # Step 1: Seed default hospital / backfill missing hospital fields
    # ------------------------------------------------------------------
    hospital_count = await db.hospitals.count_documents({})
    if hospital_count == 0:
        default_doc = hospital_document(
            name=settings.clinic_name,
            address=settings.clinic_location,
            city="Nagpur",
            state="Maharashtra",
            contact_phone="+919999999999",
            contact_email=settings.doctor_email,
            facilities=["General Consultation", "Pharmacy", "Laboratory", "Emergency Care"],
            services=["General Medicine", "Pediatrics", "Preventive Healthcare", "Diagnostic Tests"],
            working_hours="09:00 - 20:00",
            emergency_contact="+919999999999",
            status="active",
            created_by=None,
        )
        result = await db.hospitals.insert_one(default_doc)
        hospital_id = str(result.inserted_id)
        logger.info("Migration: Created default hospital '%s' (id=%s)", settings.clinic_name, hospital_id)
    else:
        first_hospital = await db.hospitals.find_one({})
        hospital_id = str(first_hospital["_id"])
        logger.info("Migration: Using existing hospital id=%s", hospital_id)

        # Non-destructively backfill missing fields on existing hospitals
        await db.hospitals.update_many(
            {"facilities": {"$exists": False}},
            {"$set": {"facilities": ["General Consultation", "Pharmacy", "Laboratory"], "updated_at": datetime.now(timezone.utc)}},
        )
        await db.hospitals.update_many(
            {"services": {"$exists": False}},
            {"$set": {"services": ["General Medicine", "Preventive Care"], "updated_at": datetime.now(timezone.utc)}},
        )
        await db.hospitals.update_many(
            {"working_hours": {"$exists": False}},
            {"$set": {"working_hours": "09:00 - 20:00", "updated_at": datetime.now(timezone.utc)}},
        )
        await db.hospitals.update_many(
            {"status": {"$exists": False}},
            {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}},
        )

    # ------------------------------------------------------------------
    # Step 2: Assign hospital_id & profile to seeded doctor
    # ------------------------------------------------------------------
    doctor = await db.users.find_one({"email": settings.doctor_email})
    if doctor:
        doc_updates = {}
        if not doctor.get("hospital_id"):
            doc_updates["hospital_id"] = hospital_id
        if doctor.get("is_active") is None:
            doc_updates["is_active"] = True
        if not doctor.get("qualification"):
            doc_updates["qualification"] = settings.doctor_qualification
        if not doctor.get("specialization"):
            doc_updates["specialization"] = "General Physician"
        if not doctor.get("valid_slots"):
            doc_updates["valid_slots"] = list(VALID_SLOTS)

        if doc_updates:
            doc_updates["updated_at"] = datetime.now(timezone.utc)
            await db.users.update_one({"_id": doctor["_id"]}, {"$set": doc_updates})
            logger.info("Migration: Backfilled profile fields for doctor %s", settings.doctor_email)

    doctor_id = str(doctor["_id"]) if doctor else None

    # ------------------------------------------------------------------
    # Step 3: Backfill appointments with hospital_id and doctor_id
    # ------------------------------------------------------------------
    if doctor_id:
        unscoped_count = await db.appointments.count_documents({"hospital_id": {"$exists": False}})
        if unscoped_count > 0:
            await db.appointments.update_many(
                {"hospital_id": {"$exists": False}},
                {
                    "$set": {
                        "hospital_id": hospital_id,
                        "doctor_id": doctor_id,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(
                "Migration: Backfilled %d appointments with hospital_id and doctor_id",
                unscoped_count,
            )

    # ------------------------------------------------------------------
    # Step 4: Rename "patient" role → "customer"
    # ------------------------------------------------------------------
    patient_count = await db.users.count_documents({"role": "patient"})
    if patient_count > 0:
        await db.users.update_many(
            {"role": "patient"},
            {"$set": {"role": "customer", "updated_at": datetime.now(timezone.utc)}},
        )
        logger.info("Migration: Renamed %d 'patient' users to 'customer'", patient_count)

    # ------------------------------------------------------------------
    # Step 5: Backfill is_active=True on users missing the field
    # ------------------------------------------------------------------
    inactive_missing = await db.users.count_documents({"is_active": {"$exists": False}})
    if inactive_missing > 0:
        await db.users.update_many(
            {"is_active": {"$exists": False}},
            {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}},
        )
        logger.info("Migration: Set is_active=True for %d users missing status", inactive_missing)

    logger.info("Migration: All startup migrations completed successfully.")
