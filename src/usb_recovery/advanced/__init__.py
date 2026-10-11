"""Advanced recovery algorithms (features 311–320)."""

from usb_recovery.advanced.dependencies import missing_sections
from usb_recovery.advanced.engine import fuse_methods, rank_multi_evidence, refine_candidates
from usb_recovery.advanced.evidence import explain_evidence
from usb_recovery.advanced.fragments import (
    boundary_confidence,
    compare_hypotheses,
    fragment_graph,
    reconstruct_with_constraints,
)
from usb_recovery.advanced.known import match_known_content

__all__ = [
    "boundary_confidence",
    "compare_hypotheses",
    "explain_evidence",
    "fragment_graph",
    "fuse_methods",
    "match_known_content",
    "missing_sections",
    "rank_multi_evidence",
    "reconstruct_with_constraints",
    "refine_candidates",
]
