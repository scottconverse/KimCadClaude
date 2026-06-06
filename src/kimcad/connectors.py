"""Build a send-to-printer connector from config (ROADMAP Stage 2).

The factory that turns a named ``connectors:`` entry in config into a concrete
:class:`~kimcad.printer_connector.PrinterConnector`. Lives in its own module so the
abstraction (``printer_connector``) and a leaf connector (``octoprint_connector``) don't
have to import each other.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from kimcad.moonraker_connector import MoonrakerConnector
from kimcad.octoprint_connector import OctoPrintConnector
from kimcad.printer_connector import ConnectorError, LoopbackConnector, PrinterConnector
from kimcad.prusalink_connector import PrusaLinkConnector

if TYPE_CHECKING:
    from kimcad.config import ConnectorConfig

# Map a config ``type`` to its connector class. This is the SINGLE source of truth for
# whether a connection drives real hardware: each class sets ``drives_hardware``, and
# ``connector_is_simulated`` derives the UI's honest label from that attribute — so the label
# can never drift from the class (the failure mode behind the Stage 2 UX-001 Critical). The
# lookup needs no instantiation, so a dropdown can be labeled without an API key.
_CONNECTOR_CLASSES: dict[str, type] = {
    "loopback": LoopbackConnector,
    "octoprint": OctoPrintConnector,
    "moonraker": MoonrakerConnector,
    "prusalink": PrusaLinkConnector,
}


def connector_is_simulated(cc: ConnectorConfig) -> bool:
    """Whether a :class:`~kimcad.config.ConnectorConfig` names a simulated (no-hardware)
    connector, derived from the connector class's ``drives_hardware``. An unknown type is
    treated as real — the safe direction (never mislabel a real printer as a simulation)."""
    cls = _CONNECTOR_CLASSES.get(cc.type)
    return cls is not None and not getattr(cls, "drives_hardware", True)


def connector_is_configured(config: Any, name: str) -> bool:
    """Whether the named connector is set up enough to actually send — right config plus any
    required secret present — *without* driving the printer. A loopback is always usable; a real
    connector missing its ``base_url`` or API-key env var reports False. Cheap (no network I/O):
    derived from whether :func:`build_connector` succeeds, so it can never drift from the real
    send path's requirements. QA-002: lets the connectors list say honestly, at a glance, that an
    OctoPrint template with no API key isn't actually ready — not just that it's "not simulated"."""
    try:
        build_connector(config, name)
        return True
    except ConnectorError:
        return False
    except Exception:  # noqa: BLE001 — unknown/malformed config is "not configured", never a crash
        return False


def build_connector(config: Any, name: str) -> PrinterConnector:
    """Construct the connector named ``name`` from ``config``'s ``connectors:`` section.

    Raises :class:`ConnectorError` for an unknown name, an unknown type, or a missing
    required setting (e.g. an OctoPrint connector whose API-key env var is unset) — with a
    plain-English message the CLI/web can show.
    """
    if name not in config.connectors():
        known = ", ".join(config.connectors()) or "(none configured)"
        raise ConnectorError(
            f"unknown connector {name!r}; configured connectors: {known}",
            reason="unknown",
            user_message=f"There's no printer connection named '{name}'.",
        )
    cc = config.connector_config(name)

    if cc.type == "loopback":
        return LoopbackConnector(name=name)

    if cc.type == "octoprint":
        if not cc.base_url:
            raise ConnectorError(
                f"connector {name!r} (octoprint) has no base_url configured",
                reason="config",
                user_message=f"The '{name}' connection has no address configured.",
            )
        api_key = os.environ.get(cc.api_key_env) if cc.api_key_env else None
        if not api_key:
            raise ConnectorError(
                f"set the {cc.api_key_env} environment variable to send to {name!r}",
                reason="config",
                user_message=f"The '{name}' printer needs an API key that isn't set up yet. "
                "See the README's send-to-printer setup.",
            )
        return OctoPrintConnector(cc.base_url, api_key, name=name)

    if cc.type == "moonraker":
        if not cc.base_url:
            raise ConnectorError(
                f"connector {name!r} (moonraker) has no base_url configured",
                reason="config",
                user_message=f"The '{name}' connection has no address configured.",
            )
        # Moonraker often runs unauthenticated on a trusted LAN, so a missing key is NOT an
        # error here — it just sends no X-Api-Key. A key is used only when configured.
        api_key = os.environ.get(cc.api_key_env) if cc.api_key_env else None
        return MoonrakerConnector(cc.base_url, api_key, name=name)

    if cc.type == "prusalink":
        if not cc.base_url:
            raise ConnectorError(
                f"connector {name!r} (prusalink) has no base_url configured",
                reason="config",
                user_message=f"The '{name}' connection has no address configured.",
            )
        api_key = os.environ.get(cc.api_key_env) if cc.api_key_env else None
        if not api_key:
            raise ConnectorError(
                f"set the {cc.api_key_env} environment variable to send to {name!r}",
                reason="config",
                user_message=f"The '{name}' printer needs an API key that isn't set up yet. "
                "See the README's send-to-printer setup.",
            )
        return PrusaLinkConnector(cc.base_url, api_key, name=name, storage=cc.storage or "usb")

    raise ConnectorError(
        f"connector {name!r} has unknown type {cc.type!r}",
        reason="config",
        user_message=f"The '{name}' connection is misconfigured.",
    )
