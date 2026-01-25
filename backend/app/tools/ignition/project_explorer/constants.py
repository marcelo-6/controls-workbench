# backend/app/tools/ignition/project_explorer/constants.py
"""
Shared constants for the Ignition project explorer tool.

Parser, indexer, and UI builders should import from here to avoid divergence.
"""

from __future__ import annotations

# -------------------------
# Designer-like sections
# -------------------------

SECTION_PERSPECTIVE = "Perspective"
SECTION_SCRIPTS = "Scripting"
SECTION_NAMED_QUERIES = "Named Queries"
SECTION_SFC = "Sequential Function Charts (SFC)"
SECTION_EVENT_STREAMS = "Event Streams"
SECTION_REPORTS = "Reports"
SECTION_ALARM_PIPELINES = "Alarm Notification Pipelines"
SECTION_PROPERTIES = "Properties"

SECTION_ORDER = [
    SECTION_PERSPECTIVE,
    SECTION_SCRIPTS,
    SECTION_NAMED_QUERIES,
    SECTION_SFC,
    SECTION_EVENT_STREAMS,
    SECTION_REPORTS,
    SECTION_ALARM_PIPELINES,
    SECTION_PROPERTIES,
]

# -------------------------
# Multi-project archives
# -------------------------

# Gateway backup can use either casing.
PROJECTS_DIR_CANDIDATES = ("projects/", "Projects/")

# -------------------------
# Resource type keys
# -------------------------

TYPE_UNKNOWN = "unknown"

TYPE_PERSPECTIVE_VIEW = "perspective.view"
TYPE_PERSPECTIVE_PAGE_CONFIG = "perspective.page_config"
TYPE_PERSPECTIVE_STYLE_CLASS = "perspective.style_class"
TYPE_PERSPECTIVE_STYLESHEET = "perspective.stylesheet"
TYPE_PERSPECTIVE_MESSAGE_HANDLER = "perspective.message_handler"
TYPE_PERSPECTIVE_SESSION_EVENT = "perspective.session_event"
TYPE_PERSPECTIVE_FORM_SUBMISSION = "perspective.form_submission_handler"
TYPE_PERSPECTIVE_KEY_EVENT = "perspective.key_event"
TYPE_PERSPECTIVE_STARTUP = "perspective.startup"
TYPE_PERSPECTIVE_SHUTDOWN = "perspective.shutdown"
TYPE_PERSPECTIVE_ACCELEROMETER = "perspective.accelerometer"
TYPE_PERSPECTIVE_BARCODE = "perspective.barcode"
TYPE_PERSPECTIVE_BLUETOOTH = "perspective.bluetooth"
TYPE_PERSPECTIVE_AUTH_CHALLENGE = "perspective.auth_challenge"
TYPE_PERSPECTIVE_NFC_SCAN = "perspective.nfc_scan"
TYPE_PERSPECTIVE_PAGE_STARTUP = "perspective.page_startup"
TYPE_PERSPECTIVE_SESSION_PROPS = "perspective.session_props"

TYPE_SCRIPT_PYTHON = "script.python"
TYPE_SCRIPT_GATEWAY_EVENT = "script.gateway_event"

TYPE_NAMED_QUERY = "named_query"

TYPE_SFC = "sfc"
TYPE_EVENT_STREAM = "event_stream"
TYPE_REPORT = "report"
TYPE_ALARM_PIPELINE = "alarm_pipeline"

TYPE_PROJECT_PROPERTIES = "project_properties"  # ignition/global-props

# -------------------------
# Folder prefixes (relative to project root)
# -------------------------

# Perspective
PFX_PERSPECTIVE = "com.inductiveautomation.perspective/"
PFX_PERSPECTIVE_VIEWS = "com.inductiveautomation.perspective/views/"
PFX_PERSPECTIVE_PAGE_CONFIG = "com.inductiveautomation.perspective/page-config/"
PFX_PERSPECTIVE_STYLE_CLASSES = "com.inductiveautomation.perspective/style-classes/"
PFX_PERSPECTIVE_STYLESHEET = "com.inductiveautomation.perspective/stylesheet/"
PFX_PERSPECTIVE_MESSAGE = "com.inductiveautomation.perspective/message/"
PFX_PERSPECTIVE_FORM_SUBMISSION = "com.inductiveautomation.perspective/form-submission-handler/"
PFX_PERSPECTIVE_KEY_EVENT = "com.inductiveautomation.perspective/key-event/"
PFX_PERSPECTIVE_ACCELEROMETER = "com.inductiveautomation.perspective/accelerometer/"
PFX_PERSPECTIVE_AUTH_CHALLENGE = "com.inductiveautomation.perspective/auth-challenge/"
PFX_PERSPECTIVE_BARCODE = "com.inductiveautomation.perspective/barcode/"
PFX_PERSPECTIVE_BLUETOOTH = "com.inductiveautomation.perspective/bluetooth/"
PFX_PERSPECTIVE_NFC_SCAN = "com.inductiveautomation.perspective/nfc-scan/"
PFX_PERSPECTIVE_PAGE_STARTUP = "com.inductiveautomation.perspective/page-startup/"
PFX_PERSPECTIVE_SESSION_PROPS = "com.inductiveautomation.perspective/session-props/"
PFX_PERSPECTIVE_STARTUP = "com.inductiveautomation.perspective/startup/"
PFX_PERSPECTIVE_SHUTDOWN = "com.inductiveautomation.perspective/shutdown/"

# Alarm pipelines
PFX_ALARM_PIPELINES = "com.inductiveautomation.alarm-notification/alarm-pipelines/"

# Event streams
PFX_EVENT_STREAMS = "com.inductiveautomation.eventstream/event-streams/"

# Reports
PFX_REPORTS = "com.inductiveautomation.reporting/reports/"

# SFC
PFX_SFC = "com.inductiveautomation.sfc/charts/"

# Ignition scripting + named queries + global props
PFX_IGNITION_SCRIPT_PYTHON = "ignition/script-python/"
PFX_IGNITION_NAMED_QUERY = "ignition/named-query/"
PFX_IGNITION_GLOBAL_PROPS = "ignition/global-props/"

# Ignition gateway event scripts
PFX_IGNITION_MESSAGE = "ignition/message/"
PFX_IGNITION_SCHEDULED = "ignition/scheduled/"
PFX_IGNITION_SHUTDOWN = "ignition/shutdown/"
PFX_IGNITION_STARTUP = "ignition/startup/"
PFX_IGNITION_TAG_CHANGE = "ignition/tag-change/"
PFX_IGNITION_TIMER = "ignition/timer/"
PFX_IGNITION_UPDATE = "ignition/update/"
