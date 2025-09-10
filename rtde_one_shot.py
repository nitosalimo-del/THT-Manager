"""RTDE-Pose-Leser mithilfe der ur-rtde-Bibliothek."""

from __future__ import annotations

import logging
import math
from typing import Iterable, Tuple

from exceptions import CommunicationError

try:  # pragma: no cover - optional dependency
    from rtde_receive import RTDEReceiveInterface  # type: ignore
except Exception:  # pragma: no cover - ImportError oder ähnliches
    RTDEReceiveInterface = None  # type: ignore

RTDE_PORT = 30004
log = logging.getLogger(__name__)


def convert_pose_m_rad_to_mm_deg(pose: Iterable[float]) -> tuple[float, ...]:
    """Wandelt eine Pose von m/rad nach mm/deg um."""
    x, y, z, rx, ry, rz = pose
    factor = 180.0 / math.pi
    return (x * 1000.0, y * 1000.0, z * 1000.0, rx * factor, ry * factor, rz * factor)


def read_rtde_pose(
    host: str,
    *,
    rtde_port: int = RTDE_PORT,
    timeout: float = 1.0,
) -> tuple[float, ...]:
    """Liest einmalig die TCP-Pose eines UR-Roboters über RTDE.

    Args:
        host: IP-Adresse des Roboters.
        rtde_port: RTDE-Port (Standard 30004).
        timeout: Socket-Timeout in Sekunden (wird weitergereicht, falls unterstützt).

    Returns:
        Tuple mit (x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg).

    Raises:
        CommunicationError: bei Verbindungs- oder Leseproblemen.
    """
    if RTDEReceiveInterface is None:
        raise CommunicationError("ur-rtde ist nicht installiert")

    try:
        # Einige Versionen unterstützen kein Timeout im Konstruktor – daher best effort.
        rx = RTDEReceiveInterface(host, rtde_port)  # type: ignore[call-arg]
        # Falls verfügbar, Timeout setzen
        try:
            rx.socket.settimeout(timeout)  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - Netzwerkfehler
        log.error("RTDE-Verbindung fehlgeschlagen: %s", exc)
        raise CommunicationError(f"RTDE-Verbindung fehlgeschlagen: {exc}") from exc

    try:
        pose = rx.getActualTCPPose()  # type: ignore[assignment]
        if not pose or len(pose) != 6:
            raise CommunicationError("Ungültige RTDE-Pose empfangen")
        return convert_pose_m_rad_to_mm_deg(pose)
    except CommunicationError:
        raise
    except Exception as exc:  # pragma: no cover - andere Fehler
        log.error("RTDE-Pose konnte nicht gelesen werden: %s", exc)
        raise CommunicationError(f"RTDE-Pose konnte nicht gelesen werden: {exc}") from exc
    finally:
        try:
            rx.disconnect()  # type: ignore[attr-defined]
        except Exception:
            pass


# --- Tests ---


def test_convert_pose_m_rad_to_mm_deg() -> None:
    import math
    import pytest

    pose = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    expected = (
        100.0,
        200.0,
        300.0,
        math.degrees(0.4),
        math.degrees(0.5),
        math.degrees(0.6),
    )
    assert convert_pose_m_rad_to_mm_deg(pose) == pytest.approx(expected)


def test_read_rtde_pose(monkeypatch) -> None:
    import pytest

    class DummyRTDE:
        def __init__(self, host: str, port: int) -> None:
            assert host == "127.0.0.1"
            assert port == RTDE_PORT

        def getActualTCPPose(self):
            return (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)

        def disconnect(self) -> None:
            pass

    import sys

    monkeypatch.setattr(
        sys.modules[__name__], "RTDEReceiveInterface", DummyRTDE
    )
    result = read_rtde_pose("127.0.0.1")
    expected = convert_pose_m_rad_to_mm_deg((0.1, 0.2, 0.3, 0.4, 0.5, 0.6))
    assert result == pytest.approx(expected)


def test_read_rtde_pose_failure(monkeypatch) -> None:
    import pytest

    class FailingRTDE:
        def __init__(self, host: str, port: int) -> None:
            raise RuntimeError("connect failed")

    import sys

    monkeypatch.setattr(
        sys.modules[__name__], "RTDEReceiveInterface", FailingRTDE
    )
    with pytest.raises(CommunicationError):
        read_rtde_pose("127.0.0.1")

