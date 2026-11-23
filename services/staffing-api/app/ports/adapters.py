"""Phase 5: register real adapters here (KB view, Azure PT writer, PT webhooks, JWT identity).

Swap via environment STAFFING_PORT_MODE=production and implement classes that satisfy
the Protocols in stubs.py without reading secrets from .env in logs.
"""

from app.ports.azure_data import AzureProjectTrackRead, AzureSkillsProvider
from app.ports.stubs import AzureProjectTrackWriter

__all__ = ["AzureProjectTrackRead", "AzureSkillsProvider", "AzureProjectTrackWriter"]