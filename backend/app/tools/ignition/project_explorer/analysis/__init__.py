"""
Ignition Project Explorer analysis package.

This package builds higher-level outputs (graphs, trees, metrics, source artifacts)
from a parsed Ignition project export (ProjectExport).

Public API:
- build_graph_bundle(...)
- ArtifactToWrite
"""

from .bundle import ArtifactToWrite, build_graph_bundle

__all__ = ["ArtifactToWrite", "build_graph_bundle"]
