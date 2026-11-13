"""Structured extraction: every value comes back with the line ids it was read from."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .llm import LLM


class Cited(BaseModel):
    value: str = Field(description='The value, or "" if the document does not state it.')
    line_ids: list[str] = Field(description="Ids of the lines the value is read from; [] when value is empty.")


class Coded(BaseModel):
    code: Cited = Field(description="An ICD-10-CM or CPT code exactly as printed, e.g. S13.4XXA or 99284.")
    description: str


class Encounter(BaseModel):
    date: Cited = Field(description="Date of care as YYYY-MM-DD.")
    provider: Cited = Field(description="The organization that provided the care, as printed.")
    clinician: Cited = Field(description="The treating clinician as printed, or empty.")
    kind: Literal["emergency", "imaging", "office_visit", "physical_therapy", "procedure", "other"]
    diagnoses: list[Coded] = Field(description="Only ICD-10 codes printed for this encounter.")
    procedures: list[Coded] = Field(description="Only CPT codes printed for this encounter.")
    key_facts: list[Cited] = Field(
        description="Up to 4 short facts a demand writer needs (findings, pain scores, treatment, plan). "
        "Each value is copied word for word from the cited line."
    )


class BillLine(BaseModel):
    date: Cited = Field(description="Date of service as YYYY-MM-DD.")
    code: Cited
    description: str
    units: str
    charge: Cited = Field(description="Charge as a plain number with two decimals, e.g. 1850.00.")


class Bill(BaseModel):
    provider: Cited
    account: Cited
    lines: list[BillLine]
    printed_total: Cited = Field(description="The total printed on the bill as a plain number, or empty.")


class DocumentExtraction(BaseModel):
    document_type: Literal["medical_record", "bill", "other"]
    patient_name: Cited
    encounters: list[Encounter]
    bills: list[Bill]


SYSTEM = """You extract facts from personal-injury case documents for a demand letter.

The document is given as numbered lines, each starting with its id in square brackets.
Rules:
- Every value you return must be read from the lines whose ids you cite. Cite only ids shown in this document.
- Never infer, compute or complete a value. If the document does not state it, return value "" and line_ids [].
- Dates: return YYYY-MM-DD. Two-digit years like 3/5/26 mean 2026.
- Money: return a plain number with two decimals and no $ or commas.
- Codes: return exactly as printed.
- An encounter is one date of care by one provider. A table of daily treatment notes is one encounter per row.
- A bill is extracted only into "bills", never as encounters. Each printed charge row is one bill line.
- Copy key facts word for word; keep them short but complete. A sentence often continues on the next line:
  quote the whole phrase across the break and cite every line it spans. Never quote a fragment that ends
  mid-phrase, such as "contacting the"."""


def extract_document(doc_id: str, file_name: str, lines: list[dict], llm: LLM) -> DocumentExtraction:
    body = "\n".join(f"[{l['id']}] {l['text']}" for l in lines)
    content = [{"type": "text", "text": f"Document {doc_id} (file {file_name}):\n\n{body}"}]
    return llm.parse(task=f"extract {doc_id}", system=SYSTEM, content=content, schema=DocumentExtraction)
