"""Forensic-grade integrity and engineering (features 351–360)."""

from usb_recovery.forensics.dashboard import evidence_dashboard
from usb_recovery.forensics.inject import FailureInjector, malformed_image
from usb_recovery.forensics.isolate import isolate_validate
from usb_recovery.forensics.manifest import provenance_chain, sign_manifest
from usb_recovery.forensics.pipeline import run_pipeline, save_pipeline
from usb_recovery.forensics.plugin_caps import check_plugin_capabilities
from usb_recovery.forensics.regression import differential_results, golden_regression
from usb_recovery.forensics.validate import independent_validate

__all__ = [
    "FailureInjector",
    "check_plugin_capabilities",
    "differential_results",
    "evidence_dashboard",
    "golden_regression",
    "independent_validate",
    "isolate_validate",
    "malformed_image",
    "provenance_chain",
    "run_pipeline",
    "save_pipeline",
    "sign_manifest",
]
