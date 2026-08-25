"""Application configuration — clinic constants live here, not in MongoDB."""

from functools import lru_cache
from typing import List

from pydantic import model_validator
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

    app_env: str = "development"
    secret_key: str = "change-me-to-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:5173"

    # Clinic facts (used for seeding; once in DB they become the source of truth)
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

    # Seeded super-admin account
    super_admin_first_name: str = "Super"
    super_admin_last_name: str = "Admin"
    super_admin_email: str = "admin@citycare.clinic"
    super_admin_password: str = "Admin@123"

    # -----------------------------------------------------------------------
    # Gemini AI configuration — Doctor Assistant
    # -----------------------------------------------------------------------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_enabled: bool = True
    gemini_timeout_seconds: int = 30
    gemini_max_output_tokens: int = 2048
    gemini_temperature: float = 0.2

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    prescription_pdf_folder: str = "citycare/prescriptions"

    # -----------------------------------------------------------------------
    # Telegram Patient Assistant configuration
    # -----------------------------------------------------------------------
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_mode: str = "polling"  # "polling" | "webhook"
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    telegram_allowed_users: str = ""  # comma-separated Telegram numeric user IDs, empty = open to all
    telegram_session_ttl_minutes: int = 240
    telegram_rate_limit_per_minute: int = 30
    telegram_otp_ttl_minutes: int = 10
    telegram_otp_max_attempts: int = 3
    telegram_timezone: str = "Asia/Kolkata"
    telegram_web_app_url: str = "http://localhost:5173"
    telegram_otp_provider: str = "dev"  # "dev" | "email" | "sms"
    telegram_request_timeout_seconds: float = 30.0


    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> "Settings":
        """Prevent sample credentials and permissive browser access in production."""
        if self.app_env.strip().lower() not in {"production", "prod"}:
            return self

        unsafe_secret_prefixes = ("change-me", "your-", "replace-with", "test-")
        if len(self.secret_key) < 32 or self.secret_key.lower().startswith(unsafe_secret_prefixes):
            raise ValueError("SECRET_KEY must be a unique, randomly generated value of at least 32 characters in production.")

        default_passwords = {"Doctor@123", "Admin@123"}
        if (
            len(self.doctor_password) < 12
            or len(self.super_admin_password) < 12
            or self.doctor_password in default_passwords
            or self.super_admin_password in default_passwords
        ):
            raise ValueError("Seeded account passwords must be strong, non-default values in production.")

        origins = self.cors_origins_list
        if not origins or "*" in origins or any("localhost" in origin.lower() for origin in origins):
            raise ValueError("CORS_ORIGINS must list explicit non-localhost HTTPS origins in production.")

        if self.telegram_enabled:
            if not self.telegram_bot_token or self.telegram_bot_token.lower().startswith(unsafe_secret_prefixes):
                raise ValueError("TELEGRAM_BOT_TOKEN must be a valid non-default token in production.")
            if self.telegram_mode.lower() != "webhook":
                raise ValueError("TELEGRAM_MODE must be 'webhook' in production deployments.")
            if not self.telegram_webhook_url or not self.telegram_webhook_url.startswith("https://") or "localhost" in self.telegram_webhook_url:
                raise ValueError("TELEGRAM_WEBHOOK_URL must be a public HTTPS URL in production.")
            if not self.telegram_webhook_secret or len(self.telegram_webhook_secret) < 16:
                raise ValueError("TELEGRAM_WEBHOOK_SECRET must be at least 16 characters in production.")
            if "localhost" in self.telegram_web_app_url.lower() or not self.telegram_web_app_url.startswith("https://"):
                raise ValueError("TELEGRAM_WEB_APP_URL must be an HTTPS URL in production.")
            if self.telegram_otp_provider.lower() == "dev":
                raise ValueError("TELEGRAM_OTP_PROVIDER cannot be 'dev' in production.")

        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def telegram_allowed_users_set(self) -> set:
        if not self.telegram_allowed_users:
            return set()
        result = set()
        for u in self.telegram_allowed_users.split(","):
            u_str = u.strip()
            if u_str.isdigit():
                result.add(int(u_str))
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()

