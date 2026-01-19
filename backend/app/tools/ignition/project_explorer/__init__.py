# backend/app/tools/ignition/project_explorer/__init__.py
"""
Ignition Project Explorer tool package.

This package implements the "ignition.project.explorer" tool:
- Parse a Designer project export ZIP
- Build dependency graphs (full + UI-filtered)
- Emit artifacts for fast UI rendering (including per-node source payloads)

Public entrypoint:
- service.run_tool
"""
