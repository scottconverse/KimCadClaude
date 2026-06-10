"""Build a send-to-printer connector from config (ROADMAP Stage 2).

The factory that turns a named ``connectors:`` entry in config into a concrete
:class:`~kimcad.printer_connector.PrinterConnector`. Lives in its own module so the
abstraction (``printer_connector``) and a leaf connector (``octoprint_connector``) don't
have to import each other.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from kimcad.bambu_connector import BAMBU_INSTALL_HINT, BambuConnector, bambulabs_api_available
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
    "bambu": BambuConnector,
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

    if cc.type == "bambu":
        # Stage 10 — Bambu LAN mode. Needs: the printer's IP (base_url), its serial, the
        # access code (env var — a secret, never stored in config), and the OPTIONAL
        # bambulabs-api package. Each gap is its own actionable config message so
        # connector_is_configured / the UI can say exactly what's missing.
        if not bambulabs_api_available():
            raise ConnectorError(
                f"connector {name!r} (bambu) needs the optional bambulabs-api package",
                reason="config",
                user_message=BAMBU_INSTALL_HINT,
            )
        if not cc.base_url:
            raise ConnectorError(
                f"connector {name!r} (bambu) has no base_url (printer IP) configured",
                reason="config",
                user_message=f"The '{name}' connection has no printer address (IP) configured.",
            )
        if not cc.serial:
            raise ConnectorError(
                f"connector {name!r} (bambu) has no serial configured",
                reason="config",
                user_message=f"The '{name}' connection needs the printer's serial number "
                "(on the printer: Settings → Device).",
            )
        access_code = os.environ.get(cc.api_key_env) if cc.api_key_env else None
        if not access_code:
            raise ConnectorError(
                f"set the {cc.api_key_env} environment variable to send to {name!r}",
                reason="config",
                user_message=f"The '{name}' printer needs its LAN access code, which isn't "
                "set up yet (on the printer: Settings → WLAN → Access Code).",
            )
        # base_url may be given as a bare IP or with a scheme; the MQTT/FTPS client wants a host.
        host = cc.base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        return BambuConnector(
            host, access_code, cc.serial, name=name, use_ams=cc.use_ams,
        )

    raise ConnectorError(
        f"connector {name!r} has unknown type {cc.type!r}",
        reason="config",
        user_message=f"The '{name}' connection is misconfigured.",
    )
