"""Build a send-to-printer connector from config (ROADMAP Stage 2).

The factory that turns a named ``connectors:`` entry in config into a concrete
:class:`~kimcad.printer_connector.PrinterConnector`. Lives in its own module so the
abstraction (``printer_connector``) and a leaf connector (``octoprint_connector``) don't
have to import each other.
"""

from __future__ import annotations

import os
from typing import Any

from kimcad.octoprint_connector import OctoPrintConnector
from kimcad.printer_connector import ConnectorError, LoopbackConnector, PrinterConnector


def build_connector(config: Any, name: str) -> PrinterConnector:
    """Construct the connector named ``name`` from ``config``'s ``connectors:`` section.

    Raises :class:`ConnectorError` for an unknown name, an unknown type, or a missing
    required setting (e.g. an OctoPrint connector whose API-key env var is unset) — with a
    plain-English message the CLI/web can show.
    """
    if name not in config.connectors():
        known = ", ".join(config.connectors()) or "(none configured)"
        raise ConnectorError(f"unknown connector {name!r}; configured connectors: {known}")
    cc = config.connector_config(name)

    if cc.type == "loopback":
        return LoopbackConnector(name=name)

    if cc.type == "octoprint":
        if not cc.base_url:
            raise ConnectorError(f"connector {name!r} (octoprint) has no base_url configured")
        api_key = os.environ.get(cc.api_key_env) if cc.api_key_env else None
        if not api_key:
            raise ConnectorError(
                f"set the {cc.api_key_env} environment variable to send to {name!r}"
            )
        return OctoPrintConnector(cc.base_url, api_key, name=name)

    raise ConnectorError(f"connector {name!r} has unknown type {cc.type!r}")
