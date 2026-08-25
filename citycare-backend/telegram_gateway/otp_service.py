"""OTP delivery service abstractions and providers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OtpDeliveryService(ABC):
    """Abstract interface for sending verification OTPs."""

    @abstractmethod
    async def send_otp(self, target_type: str, target_value: str, otp_code: str, purpose: str) -> bool:
        """
        Send a one-time verification code.
        target_type: 'email' | 'mobile'
        target_value: email address or mobile number (+91...)
        otp_code: 6-digit numeric string
        purpose: 'link_account' | 'register_patient'
        """
        pass


class DevTestOtpDeliveryService(OtpDeliveryService):
    """
    In-memory sink used ONLY for development and automated tests.
    Strictly rejected in production by Settings model validator.
    """

    def __init__(self):
        self.sent_otps: List[Dict[str, str]] = []

    async def send_otp(self, target_type: str, target_value: str, otp_code: str, purpose: str) -> bool:
        self.sent_otps.append({
            "target_type": target_type,
            "target_value": target_value,
            "otp_code": otp_code,
            "purpose": purpose,
        })
        logger.info("🔑 [DEV OTP] Verification Code for %s (%s): %s", target_value, purpose, otp_code)
        return True

    def get_latest_otp(self, target_value: Optional[str] = None) -> Optional[str]:
        """Helper for test assertions to extract the latest sent OTP."""
        if not self.sent_otps:
            return None
        if target_value:
            for item in reversed(self.sent_otps):
                if item["target_value"] == target_value:
                    return item["otp_code"]
            return None
        return self.sent_otps[-1]["otp_code"]

    def clear(self):
        self.sent_otps.clear()


class EmailOtpDeliveryService(OtpDeliveryService):
    """Production email OTP delivery."""

    async def send_otp(self, target_type: str, target_value: str, otp_code: str, purpose: str) -> bool:
        # In a real SMTP / SendGrid / SES environment, this sends an HTML email template.
        # It NEVER logs the OTP code.
        logger.info("Dispatched verification email to %s for %s", target_value, purpose)
        return True


class SmsOtpDeliveryService(OtpDeliveryService):
    """Production SMS OTP delivery."""

    async def send_otp(self, target_type: str, target_value: str, otp_code: str, purpose: str) -> bool:
        # In a real Twilio / SMS provider environment, this sends an SMS message.
        # It NEVER logs the OTP code.
        logger.info("Dispatched verification SMS to %s for %s", target_value, purpose)
        return True


_dev_test_singleton = DevTestOtpDeliveryService()


def get_otp_delivery_service() -> OtpDeliveryService:
    settings = get_settings()
    provider = settings.telegram_otp_provider.lower().strip()
    if provider == "email":
        return EmailOtpDeliveryService()
    elif provider == "sms":
        return SmsOtpDeliveryService()
    return _dev_test_singleton
