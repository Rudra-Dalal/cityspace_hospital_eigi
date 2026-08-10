"""Cloudinary upload boundary; credentials stay in environment settings."""

from app.core.config import get_settings


def upload_prescription_pdf(pdf_bytes: bytes, prescription_id: str) -> tuple[str, str]:
    settings = get_settings()
    if not all([settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret]):
        raise RuntimeError("Cloudinary is not configured.")
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(cloud_name=settings.cloudinary_cloud_name, api_key=settings.cloudinary_api_key, api_secret=settings.cloudinary_api_secret, secure=True)
        result = cloudinary.uploader.upload(pdf_bytes, resource_type="raw", folder=settings.prescription_pdf_folder, public_id=prescription_id, overwrite=True)
        return result["secure_url"], result["public_id"]
    except Exception as exc:
        raise RuntimeError("Prescription PDF upload failed.") from exc
