"""Intelligent analysis and automation (features 341–350)."""

from usb_recovery.intel.anomalies import detect_scan_anomalies
from usb_recovery.intel.classify import classify_candidate, extract_features
from usb_recovery.intel.filter import filter_false_positives
from usb_recovery.intel.group import group_correlated
from usb_recovery.intel.plan import adaptive_plan, algorithm_profile, estimate_cost
from usb_recovery.intel.reports import strategy_report, uncertainty_report
from usb_recovery.intel.scorecard import quality_scorecard

__all__ = [
    "adaptive_plan",
    "algorithm_profile",
    "classify_candidate",
    "detect_scan_anomalies",
    "estimate_cost",
    "extract_features",
    "filter_false_positives",
    "group_correlated",
    "quality_scorecard",
    "strategy_report",
    "uncertainty_report",
]
