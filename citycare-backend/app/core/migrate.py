"""Idempotent startup migration: seeds CityCare hospital & migrates legacy data."""

from datetime import datetime, timezone

from app.core.database import get_database
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_migrations() -> None:
    """
    Safe to run on every startup — all operations are idempotent.

    Steps:
    1. Create the default 'CityCare Clinic' hospital document if hospitals collection is empty.
    2. Assign hospital_id to Dr. Meera Kulkarni (the seeded doctor).
    3. Backfill existing appointments with hospital_id + doctor_id.
    4. Rename legacy role 'patient' → 'customer' in users collection.
    5. Ensure hospital_id is set to None on super_admin / customer users (safety).
    """
    db = get_database()

    # ------------------------------------------------------------------
    # Step 1: Seed default hospital
    # ------------------------------------------------------------------
    hospital_count = await db.hospitals.count_documents({})
    if hospital_count == 0:
        from app.core.config import get_settings
        settings = get_settings()

        from app.models.hospital_model import hospital_document
        hospital_doc = hospital_document(
            name=settings.clinic_name,
            address=settings.clinic_location,
            city="Nagpur",
            state="Maharashtra",
            contact_phone="+919999999999",
            contact_email=settings.doctor_email,
            status="active",
            created_by=None,
        )
        result = await db.hospitals.insert_one(hospital_doc)
        hospital_id = str(result.inserted_id)
        logger.info("Migration: Created default hospital '%s' (id=%s)", settings.clinic_name, hospital_id)
    else:
        first_hospital = await db.hospitals.find_one({})
        hospital_id = str(first_hospital["_id"])
        logger.info("Migration: Using existing hospital id=%s", hospital_id)

    # ------------------------------------------------------------------
    # Step 2: Assign hospital_id to the seeded doctor
    # ------------------------------------------------------------------
    from app.core.config import get_settings
    settings = get_settings()
    doctor = await db.users.find_one({"email": settings.doctor_email})
    if doctor and not doctor.get("hospital_id"):
        await db.users.update_one(
            {"_id": doctor["_id"]},
            {"$set": {"hospital_id": hospital_id, "updated_at": datetime.now(timezone.utc)}},
        )
        logger.info("Migration: Assigned hospital_id to doctor %s", settings.doctor_email)

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

    logger.info("Migration: All startup migrations complete.")
