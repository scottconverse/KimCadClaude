"""Snapmaker U1 connector (Klipper/Moonraker, 4-toolhead).

The Snapmaker U1 runs Klipper + Moonraker, so it inherits the full send / job / control
lifecycle from :class:`~kimcad.moonraker_connector.MoonrakerConnector`. Only two methods
are overridden:

1. ``capabilities()`` — queries ``toolhead configfile extruder extruder1 extruder2 extruder3``
   to detect the number of active toolheads and returns ``toolhead_count`` accordingly.
2. ``status()`` — queries all four extruder objects to build a ``toolhead_temps`` tuple
   (T0..T3), falling back gracefully to fewer toolheads if some extruder objects are absent.

A ``"snapmaker"`` connector type is wired in :mod:`kimcad.connectors`.
"""

from __future__ import annotations

import urllib.error

from kimcad.moonraker_connector import MoonrakerConnector, _PRINT_STATE, _moonraker_error_detail
from kimcad.printer_connector import (
    AuthError,
    ConnectorError,
    PrinterCapabilities,
    PrinterOffline,
    PrinterState,
    PrinterStatus,
)

_EXTRUDER_OBJECTS = ("extruder", "extruder1", "extruder2", "extruder3")


class SnapmakerConnector(MoonrakerConnector):
    """Moonraker connector specialised for the Snapmaker U1 (up to 4 toolheads).

    All send / job_status / pause / resume / cancel behaviour is inherited from
    :class:`MoonrakerConnector` unchanged; only ``capabilities`` and ``status`` are
    overridden to surface per-extruder data.

    ENG-004/ENG-006: ``status().toolhead_temps`` contains ONLY the extruders currently
    reporting a numeric temperature, in T0..TN-1 order, and MAY be shorter than
    ``capabilities().toolhead_count`` if a head is disconnected — a head present in the query
    but reporting ``temperature: null`` is omitted. This is intentional so the tuple (and the
    JSON it serializes to) stays valid: no NaN/null ever enters ``toolhead_temps``.
    """

    def capabilities(self) -> PrinterCapabilities:
        try:
            status = self._query("toolhead", "configfile", *_EXTRUDER_OBJECTS)
        except urllib.error.HTTPError as e:
            detail = _moonraker_error_detail(e)
            if e.code in (401, 403):
                raise AuthError(
                    f"{self.name} rejected the API key (HTTP {e.code}){detail}",
                    user_message=f"The printer '{self.name}' rejected the API key - "
                    "check that it's correct.",
                ) from e
            raise ConnectorError(
                f"{self.name} capabilities query failed (HTTP {e.code}){detail}"
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        toolhead = status.get("toolhead") or {}
        axis_max = toolhead.get("axis_maximum")
        axis_min = toolhead.get("axis_minimum") or [0.0, 0.0, 0.0, 0.0]
        build_volume = None
        if isinstance(axis_max, (list, tuple)) and len(axis_max) >= 3:
            build_volume = tuple(
                float(axis_max[i]) - float(axis_min[i] if len(axis_min) > i else 0.0)
                for i in range(3)
            )
        settings = (status.get("configfile") or {}).get("settings") or {}
        nozzle = (settings.get("extruder") or {}).get("nozzle_diameter")
        toolhead_count = max(1, sum(1 for obj in _EXTRUDER_OBJECTS if obj in status))
        return PrinterCapabilities(
            name=self.name,
            build_volume_mm=build_volume,
            nozzle_diameter_mm=float(nozzle) if nozzle is not None else None,
            toolhead_count=toolhead_count,
        )

    def status(self) -> PrinterStatus:
        """Snapshot the printer + per-extruder temps.

        ENG-004/ENG-006/ENG-101: ``toolhead_temps`` carries one entry per extruder object
        *present* in the query response, in T0..TN-1 order. An object that is absent (a machine
        with fewer heads) is dropped, so the tuple MAY be shorter than
        ``capabilities().toolhead_count``. An object that is present but reporting
        ``temperature: null`` (a disconnected head on an N-head machine) keeps its index as
        ``None`` — the position is index-stable so a non-reporting *middle* head never shifts the
        T-labels of the heads after it. ``None`` is valid JSON (unlike NaN), so the serialized
        response stays well-formed; the SPA renders a non-reporting slot as "—". ``nozzle_temp_c``
        is T0's temperature (``None`` if T0 itself isn't reporting).
        """
        try:
            status = self._query("print_stats", "heater_bed", *_EXTRUDER_OBJECTS)
        except urllib.error.HTTPError as e:
            label = "authentication failed" if e.code in (401, 403) else "request rejected"
            return PrinterStatus(
                online=e.code < 500, state=PrinterState.error,
                detail=f"{label} (HTTP {e.code})"
            )
        except (urllib.error.URLError, OSError):
            return PrinterStatus(
                online=False, state=PrinterState.offline, detail="could not connect"
            )
        except ConnectorError:
            return PrinterStatus(
                online=True, state=PrinterState.error,
                detail="unexpected response from printer"
            )
        print_stats = status.get("print_stats") or {}
        raw = str(print_stats.get("state") or "").lower()
        state = _PRINT_STATE.get(raw, PrinterState.error if raw else PrinterState.operational)
        temps: list[float | None] = []
        for obj in _EXTRUDER_OBJECTS:
            block = status.get(obj)
            if block is None:
                continue  # extruder object absent → this machine simply has fewer heads
            # ENG-101: a present-but-non-reporting head (temperature: null) keeps its T-index
            # as None so the heads after it don't shift onto the wrong T-label.
            t = block.get("temperature")
            temps.append(float(t) if t is not None else None)
        return PrinterStatus(
            online=True,
            state=state,
            detail=str(print_stats.get("state") or ""),
            nozzle_temp_c=temps[0] if temps else None,
            bed_temp_c=(status.get("heater_bed") or {}).get("temperature"),
            toolhead_temps=tuple(temps) if temps else None,
        )
