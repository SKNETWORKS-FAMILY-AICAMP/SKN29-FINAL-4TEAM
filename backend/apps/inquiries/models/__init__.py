"""Public inquiry model exports."""

from apps.inquiries.models.inquiry import Inquiry
from apps.inquiries.models.symptom_entry import SymptomEntry


__all__ = ["Inquiry", "SymptomEntry"]
