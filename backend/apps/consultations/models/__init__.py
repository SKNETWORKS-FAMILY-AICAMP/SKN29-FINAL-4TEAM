"""Public model exports for the consultation domain."""

from apps.consultations.models.consultation import Consultation
from apps.consultations.models.consultation_handoff import ConsultationHandoff


__all__ = ["Consultation", "ConsultationHandoff"]
