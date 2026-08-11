"""PDF text extraction and section-aware chunking for CityCare Patient Handbook."""

import os
import re
from typing import Any, Dict, List, Optional
import pypdf

POLICY_MAP = {
    "hours": "POL-HRS-00",
    "holidays": "POL-HRS-00",
    "appointment": "POL-APT-01",
    "walk-in": "POL-APT-01",
    "late": "POL-APT-01",
    "cancellation": "POL-CAN-02",
    "rescheduling": "POL-CAN-02",
    "no-show": "POL-CAN-02",
    "teleconsultation": "POL-TEL-03",
    "fee": "POL-FEE-04",
    "payment": "POL-FEE-04",
    "record": "POL-REC-05",
    "privacy": "POL-REC-05",
    "emergency": "POL-EMG-06",
    "referral": "POL-EMG-06",
    "vaccination": "POL-VAC-07",
    "vaccine": "POL-VAC-07",
    "insurance": "POL-INS-08",
    "reimbursement": "POL-INS-08",
}


def load_pdf_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract page number and raw text for every page in the PDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Handbook PDF not found at path: {pdf_path}")

    reader = pypdf.PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({
            "page": i + 1,
            "text": text,
        })
    return pages


def extract_handbook_chunks(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract section-aware semantic chunks with page, section, policy code,
    and chunk index metadata from the handbook PDF.
    """
    pages = load_pdf_pages(pdf_path)
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    current_section = "Overview"
    current_policy: Optional[str] = None

    for page_info in pages:
        page_num = page_info["page"]
        text = page_info["text"]
        lines = text.split("\n")
        current_block: List[str] = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check if line explicitly references a policy code (e.g. POL-APT-01)
            pol_match = re.search(r"(POL-[A-Z]+-\d+)", line_str)

            # Check if line is a section heading (e.g. "1. About the clinic", "4.5 Cancellation (Policy POL-CAN-02)", "18. Frequently asked questions")
            sec_match = re.match(r"^(\d+(\.\d+)?)\s+([A-Z].*)", line_str)
            if sec_match:
                # Flush previous block if non-empty
                if current_block:
                    block_text = " ".join(current_block).strip()
                    if len(block_text) > 20:
                        chunks.append({
                            "document": "CityCare-Clinic-Patient-Handbook",
                            "version": "3.2",
                            "page": page_num,
                            "section": current_section,
                            "policy": current_policy,
                            "chunk_index": chunk_index,
                            "text": block_text,
                        })
                        chunk_index += 1
                    current_block = []

                current_section = line_str
                if pol_match:
                    current_policy = pol_match.group(1)
                else:
                    current_policy = None
                    for key, pol in POLICY_MAP.items():
                        if key in current_section.lower():
                            current_policy = pol
                            break
                continue

            if pol_match:
                current_policy = pol_match.group(1)

            current_block.append(line_str)

            # Flush when block accumulates a good semantic length (~400 chars)
            if sum(len(x) for x in current_block) > 400:
                block_text = " ".join(current_block).strip()
                chunks.append({
                    "document": "CityCare-Clinic-Patient-Handbook",
                    "version": "3.2",
                    "page": page_num,
                    "section": current_section,
                    "policy": current_policy,
                    "chunk_index": chunk_index,
                    "text": block_text,
                })
                chunk_index += 1
                current_block = []

        if current_block:
            block_text = " ".join(current_block).strip()
            if len(block_text) > 20:
                chunks.append({
                    "document": "CityCare-Clinic-Patient-Handbook",
                    "version": "3.2",
                    "page": page_num,
                    "section": current_section,
                    "policy": current_policy,
                    "chunk_index": chunk_index,
                    "text": block_text,
                })
                chunk_index += 1

    return chunks
