"""Application configuration — clinic constants live here, not in MongoDB."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# Fixed daily slots: morning 10:00–13:00 + evening 17:00–20:00, 30 min each
VALID_SLOTS: List[str] = [
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
]

ALLOWED_SYMPTOMS: List[str] = [
    "fever",
    "cough",
    "cold",
    "bodyache",
    "headache",
    "other",
]


class Settings(BaseSettings):
    """Loads from environment / .env — never hardcode secrets in source."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "citycare"

    secret_key: str = "change-me-to-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    # Clinic facts (single-doctor clinic — configuration, not a collection)
    doctor_display_name: str = "Dr. Meera Kulkarni"
    doctor_qualification: str = "MBBS, MD - General Physician"
    clinic_name: str = "CityCare Clinic"
    clinic_location: str = "Dharampeth, Nagpur"
    morning_hours: str = "10:00 to 13:00"
    evening_hours: str = "17:00 to 20:00"
    slot_duration_minutes: int = 30
    booking_window_days: int = 7

    # Seeded doctor account
    doctor_first_name: str = "Meera"
    doctor_last_name: str = "Kulkarni"
    doctor_email: str = "doctor@citycare.clinic"
    doctor_password: str = "Doctor@123"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
