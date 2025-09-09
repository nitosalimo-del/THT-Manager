"""RTDE One-Shot Client mit Fallback.
=====================================

Liest einmalig ``actual_TCP_pose`` von einem UR-Cobot. Primär wird das
RTDE-Protokoll (Port ``30004``) verwendet. Schlägt der Handshake fehl, wird
automatisch auf das Secondary Client Interface (Port ``30002``) umgeschaltet.

Die zurückgegebene Pose ist immer in Millimeter und Grad.

CLI-Beispiel::

    python rtde_one_shot.py --host 10.3.218.4 --debug
"""

from __future__ import annotations

import argparse
import logging
import math
import re
import socket
import struct
from typing import Iterable, Tuple

from exceptions import CommunicationError


# ---------------------------------------------------------------------------
# RTDE-Konstanten
# ---------------------------------------------------------------------------
RTDE_REQUEST_PROTOCOL_VERSION = 0x56  # 'V'
RTDE_PROTOCOL_VERSION_REPLY = RTDE_REQUEST_PROTOCOL_VERSION
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F  # 'O'
RTDE_CONTROL_PACKAGE_START = 0x53  # 'S'
RTDE_CONTROL_PACKAGE_PAUSE = 0x50  # 'P'
RTDE_DATA_PACKAGE = 0x55  # 'U'
RTDE_TEXT_MESSAGE_UR = 0x4D  # 'M'
RTDE_TEXT_MESSAGE_DUMMY = 0x62  # 'b'
RTDE_TEXT_MESSAGES = {RTDE_TEXT_MESSAGE_UR, RTDE_TEXT_MESSAGE_DUMMY}

RTDE_PORT = 30004


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def hexdump(data: bytes, max_len: int = 64) -> str:
    """Gibt die ersten ``max_len`` Bytes als Hexdump zurück."""

    return " ".join(f"{b:02X}" for b in data[:max_len])


def type_name(msg_type: int) -> str:
    """Bekannter Name eines RTDE-Message-Typs."""

    names = {
        RTDE_REQUEST_PROTOCOL_VERSION: "REQUEST_PROTOCOL_VERSION",
        RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS: "CONTROL_PACKAGE_SETUP_OUTPUTS",
        RTDE_CONTROL_PACKAGE_START: "CONTROL_PACKAGE_START",
        RTDE_CONTROL_PACKAGE_PAUSE: "CONTROL_PACKAGE_PAUSE",
        RTDE_DATA_PACKAGE: "DATA_PACKAGE",
        RTDE_TEXT_MESSAGE_UR: "TEXT_MESSAGE_UR",
        RTDE_TEXT_MESSAGE_DUMMY: "TEXT_MESSAGE_DUMMY",
    }
    return names.get(msg_type, "UNKNOWN")


def frame_str(msg_type: int, payload: bytes) -> str:
    """Formatiert Typ, Länge und Hexdump eines RTDE-Frames."""

    char = chr(msg_type) if 32 <= msg_type <= 126 else "?"
    return (
        f"type=0x{msg_type:02X}('{char}','{type_name(msg_type)}'), "
        f"len={len(payload)}, payload_hex={hexdump(payload)}"
    )


def send_frame(sock: socket.socket, msg_type: int, payload: bytes = b"") -> None:
    """Sendet ein RTDE-Frame."""

    frame = struct.pack(">HB", len(payload) + 3, msg_type) + payload
    sock.sendall(frame)
    log.debug("RTDE: send %s", frame_str(msg_type, payload))


def _recv_exact(sock: socket.socket, size: int, context: str) -> bytes:
    """Liest genau ``size`` Bytes vom Socket."""

    data = b""
    while len(data) < size:
        try:
            chunk = sock.recv(size - len(data))
        except socket.timeout as exc:  # pragma: no cover - Netzfehler
            msg = f"RTDE: Timeout beim Lesen {context}"
            log.error(msg)
            raise CommunicationError(msg) from exc
        if not chunk:
            msg = f"RTDE: Verbindung beendet {context}"
            log.error(msg)
            raise CommunicationError(msg)
        data += chunk
    return data


def recv_frame(sock: socket.socket) -> Tuple[int, bytes]:
    """Empfängt ein RTDE-Frame."""

    header = _recv_exact(sock, 3, "des Frame-Headers")
    length, msg_type = struct.unpack(">HB", header)
    if length < 3:
        msg = f"RTDE: unplausible Länge {length} im Header"
        log.error(msg)
        raise CommunicationError(msg)
    payload = _recv_exact(sock, length - 3, "des Frame-Payloads")
    log.debug("RTDE: recv %s", frame_str(msg_type, payload))
    return msg_type, payload


def recv_non_text(sock: socket.socket) -> Tuple[int, bytes]:
    """Empfängt das nächste Nicht-Text-Frame."""

    while True:
        msg_type, payload = recv_frame(sock)
        if msg_type in RTDE_TEXT_MESSAGES:
            text = payload.decode("utf-8", errors="replace").strip()
            log.debug("RTDE: Textnachricht ignoriert: %s", text)
            continue
        return msg_type, payload


def convert_pose_m_rad_to_mm_deg(pose: Iterable[float]) -> tuple[float, ...]:
    """Konvertiert Pose von m/rad nach mm/deg."""

    x, y, z, rx, ry, rz = pose
    factor = 180.0 / math.pi
    return (x * 1000, y * 1000, z * 1000, rx * factor, ry * factor, rz * factor)


# ---------------------------------------------------------------------------
# Kernklasse
# ---------------------------------------------------------------------------
class RTDEOneShotClient:
    """Liest genau eine TCP-Pose."""

    def __init__(
        self,
        host: str = "10.3.218.4",
        rtde_port: int = RTDE_PORT,
        sec_port: int = 30002,
        timeout: float = 3.0,
        debug: bool = False,
    ) -> None:
        self.host = host
        self.rtde_port = rtde_port
        self.sec_port = sec_port
        self.timeout = timeout
        self.debug = debug
        self.recipe_id: int | None = None
        if debug:
            log.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    def read_pose(self) -> tuple[float, ...]:
        """Liest die Pose mit RTDE oder Secondary Client."""

        try:
            pose = self._read_rtde_pose()
        except CommunicationError as exc:
            log.warning("RTDE: %s, versuche Secondary Client", exc)
            pose = self._read_secondary_pose()
        return convert_pose_m_rad_to_mm_deg(pose)

    # ------------------------------------------------------------------
    # RTDE
    def _read_rtde_pose(self) -> tuple[float, ...]:
        """Verbindet sich mit RTDE und liest genau eine Pose."""

        with socket.create_connection(
            (self.host, self.rtde_port), self.timeout
        ) as sock:
            sock.settimeout(self.timeout)
            self._handshake(sock)
            msg_type, payload = recv_non_text(sock)
            if msg_type != RTDE_DATA_PACKAGE:
                self._unexpected(
                    RTDE_DATA_PACKAGE,
                    msg_type,
                    payload,
                    "beim Warten auf DATA_PACKAGE",
                )
            if len(payload) < 1 + 6 * 8:
                msg = f"RTDE: zu kurzes DATA_PACKAGE: {frame_str(msg_type, payload)}"
                log.error(msg)
                raise CommunicationError(msg)
            recipe = payload[0]
            if recipe != self.recipe_id:
                msg = (
                    f"RTDE: recipe_id-Mismatch, erwartet {self.recipe_id}, erhalten {recipe}"
                )
                log.error(msg)
                raise CommunicationError(msg)
            pose = struct.unpack(">6d", payload[1:49])
            try:
                send_frame(sock, RTDE_CONTROL_PACKAGE_PAUSE)
                recv_non_text(sock)
            except Exception:  # pragma: no cover - Pause darf fehlschlagen
                pass
            log.info("RTDE: Pose empfangen")
            return pose

    def _handshake(self, sock: socket.socket) -> None:
        """Verhandelt Protokollversion und startet den Datenstrom."""

        if not self._request_version(sock, 2):
            log.warning("RTDE: Version 2 abgelehnt, versuche Version 1")
            if not self._request_version(sock, 1):
                msg = "RTDE: Protokollversion nicht akzeptiert"
                log.error(msg)
                raise CommunicationError(msg)

        payload = struct.pack(">d", 125.0) + b"actual_TCP_pose"
        send_frame(sock, RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS, payload)
        msg_type, payload = recv_non_text(sock)
        if msg_type != RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS or len(payload) < 1:
            self._unexpected(
                RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS,
                msg_type,
                payload,
                "während SETUP_OUTPUTS",
            )
        recipe = payload[0]
        if recipe == 0:
            msg = f"RTDE: SETUP_OUTPUTS abgelehnt: {frame_str(msg_type, payload)}"
            log.error(msg)
            raise CommunicationError(msg)
        self.recipe_id = recipe
        log.info("RTDE: Outputs konfiguriert (recipe_id=%d)", recipe)

        send_frame(sock, RTDE_CONTROL_PACKAGE_START)
        msg_type, payload = recv_non_text(sock)
        if (
            msg_type != RTDE_CONTROL_PACKAGE_START
            or len(payload) < 1
            or payload[0] != 1
        ):
            self._unexpected(
                RTDE_CONTROL_PACKAGE_START,
                msg_type,
                payload,
                "während START",
            )
        log.info("RTDE: Datenstrom gestartet")

    def _request_version(self, sock: socket.socket, version: int) -> bool:
        """Versucht eine Protokollversion zu aktivieren."""

        send_frame(sock, RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", version))
        msg_type, payload = recv_non_text(sock)
        if msg_type != RTDE_PROTOCOL_VERSION_REPLY or len(payload) < 1:
            self._unexpected(
                RTDE_PROTOCOL_VERSION_REPLY,
                msg_type,
                payload,
                "während Versions-Handshake",
            )
        accepted = payload[0]
        log.info(
            "RTDE: Protokollversion %d %s",
            version,
            "akzeptiert" if accepted else "abgelehnt",
        )
        return accepted == 1

    def _unexpected(
        self, expected: int, msg_type: int, payload: bytes, context: str
    ) -> None:
        """Erzeugt eine detaillierte Fehlermeldung."""

        exp_name = type_name(expected)
        msg = (
            f"RTDE: erwartet {exp_name}, erhalten {frame_str(msg_type, payload)} {context}"
        )
        log.error(msg)
        raise CommunicationError(msg)

    # ------------------------------------------------------------------
    # Secondary Client
    def _read_secondary_pose(self) -> tuple[float, ...]:
        """Liest die Pose über das Secondary Client Interface."""

        with socket.create_connection(
            (self.host, self.sec_port), self.timeout
        ) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(b"get_actual_tcp_pose()\n")
            data = sock.recv(4096)
        text = data.decode("utf-8", errors="ignore")
        numbers = re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", text)
        if len(numbers) < 6:
            msg = f"SEC: Antwort unplausibel: {text!r}"
            log.error(msg)
            raise CommunicationError(msg)
        pose = tuple(float(n) for n in numbers[:6])
        log.info("SEC: Pose empfangen")
        return pose


# ---------------------------------------------------------------------------
# Öffentliche Helfer
# ---------------------------------------------------------------------------
def read_rtde_pose(
    host: str,
    rtde_port: int = RTDE_PORT,
    sec_port: int = 30002,
    timeout: float = 3.0,
    debug: bool = False,
) -> tuple[float, ...]:
    """Komfortfunktion zum Lesen der TCP-Pose."""

    client = RTDEOneShotClient(
        host=host,
        rtde_port=rtde_port,
        sec_port=sec_port,
        timeout=timeout,
        debug=debug,
    )
    return client.read_pose()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Liest einmalig actual_TCP_pose")
    parser.add_argument("--host", default="10.3.218.4")
    parser.add_argument("--rtde-port", type=int, default=30004)
    parser.add_argument("--sec-port", type=int, default=30002)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    client = RTDEOneShotClient(
        host=args.host,
        rtde_port=args.rtde_port,
        sec_port=args.sec_port,
        timeout=args.timeout,
        debug=args.debug,
    )
    try:
        pose = client.read_pose()
        print("Pose:", pose)
    except CommunicationError as exc:  # pragma: no cover - CLI-Ausgabe
        log.error("Fehler: %s", exc)


if __name__ == "__main__":  # pragma: no cover - manuelles Ausführen
    _main()

