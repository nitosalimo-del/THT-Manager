"""RTDE One-Shot Client
=======================

Liest einmalig ``actual_TCP_pose`` von einem UR-kompatiblen RTDE-Server.
Unterstützt Protokollversion 2 mit Fallback auf Version 1. Bei jeder
unerwarteten Antwort werden Typ, Länge und ein Hexdump des Payloads
ausgegeben. Textnachrichten werden übersprungen, aber im Debug-Modus
protokolliert.

Benutzung::

    python rtde_one_shot.py --host 10.3.218.4 --port 30004 --debug

Die Funktion :func:`read_rtde_pose` bietet eine einfache API für andere
Module.
"""

from __future__ import annotations

import argparse
import logging
import socket
import struct
from typing import Tuple

from exceptions import CommunicationError

# ---------------------------------------------------------------------------
# Konstanten laut UR-RTDE-Protokoll
# ---------------------------------------------------------------------------
RTDE_REQUEST_PROTOCOL_VERSION = 0x56  # 'V'
RTDE_PROTOCOL_VERSION_REPLY = RTDE_REQUEST_PROTOCOL_VERSION
RTDE_GET_URCONTROL_VERSION = 0x76  # 'v'
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F  # 'O'
RTDE_CONTROL_PACKAGE_SETUP_INPUTS = 0x49  # 'I'
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
    """Gibt die ersten ``max_len`` Bytes eines Byte-Strings als Hexdump zurück."""

    return " ".join(f"{b:02X}" for b in data[:max_len])


def type_name(msg_type: int) -> str:
    """Ermittelt den bekannten Namen eines RTDE-Message-Typs."""

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
    """Sendet ein vollständiges RTDE-Frame."""

    frame = struct.pack(">HB", len(payload) + 3, msg_type) + payload
    sock.sendall(frame)
    log.debug("RTDE: send %s", frame_str(msg_type, payload))


def _recv_exact(sock: socket.socket, size: int, context: str) -> bytes:
    """Liest exakt ``size`` Bytes vom Socket."""

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
        msg = f"RTDE: unplausible Laenge {length} im Header"
        log.error(msg)
        raise CommunicationError(msg)
    payload = _recv_exact(sock, length - 3, "des Frame-Payloads")
    log.debug("RTDE: recv %s", frame_str(msg_type, payload))
    return msg_type, payload


def recv_non_text(sock: socket.socket) -> Tuple[int, bytes]:
    """Empfängt das nächste Nicht-Text-RTDE-Frame."""

    while True:
        msg_type, payload = recv_frame(sock)
        if msg_type in RTDE_TEXT_MESSAGES:
            text = payload.decode("utf-8", errors="replace").strip()
            log.debug("RTDE: Textnachricht ignoriert: %s", text)
            continue
        return msg_type, payload


# ---------------------------------------------------------------------------
# Kernfunktionalität
# ---------------------------------------------------------------------------
class RTDEOneShotClient:
    """RTDE-Client, der genau ein ``DATA_PACKAGE`` liest."""

    def __init__(
        self,
        host: str = "10.3.218.4",
        port: int = RTDE_PORT,
        timeout: float = 3.0,
        debug: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.debug = debug
        self.recipe_id: int | None = None
        if debug:
            log.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    def read_pose(self) -> Tuple[float, float, float, float, float, float]:
        """Führt den RTDE-Handshake aus und liefert die TCP-Pose."""

        last_error: Exception | None = None
        for version in (2, 1):
            try:
                with socket.create_connection((self.host, self.port), self.timeout) as sock:
                    sock.settimeout(self.timeout)
                    self._handshake(sock, version)
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
                        recv_non_text(sock)  # Antwort ignorieren
                    except Exception:  # pragma: no cover - Pause darf fehlschlagen
                        pass
                    log.info("RTDE: Pose empfangen")
                    return pose
            except (OSError, CommunicationError) as exc:
                last_error = exc
                log.warning(
                    "RTDE: Versuch mit Protokollversion %d fehlgeschlagen: %s", version, exc
                )
                continue
        msg = "RTDE: Protokollversion nicht akzeptiert"
        if last_error:
            msg += f" ({last_error})"
        log.error(msg)
        raise CommunicationError(msg)

    # ------------------------------------------------------------------
    def _handshake(self, sock: socket.socket, version: int) -> None:
        """Verhandelt die Protokollversion und startet den Datenstrom."""

        if not self._request_version(sock, version):
            msg = f"RTDE: Protokollversion {version} abgelehnt"
            log.error(msg)
            raise CommunicationError(msg)

        payload = struct.pack(">d", 125.0) + b"actual_TCP_pose\x00"
        send_frame(sock, RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS, payload)
        msg_type, payload = recv_non_text(sock)
        if msg_type != RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS or len(payload) < 1:
            self._unexpected(
                RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS,
                msg_type,
                payload,
                "waehrend SETUP_OUTPUTS",
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
        if msg_type != RTDE_CONTROL_PACKAGE_START or len(payload) < 1 or payload[0] != 1:
            self._unexpected(
                RTDE_CONTROL_PACKAGE_START,
                msg_type,
                payload,
                "waehrend START",
            )
        log.info("RTDE: Datenstrom gestartet")

    # ------------------------------------------------------------------
    def _request_version(self, sock: socket.socket, version: int) -> bool:
        """Versucht eine Protokollversion zu aktivieren."""

        send_frame(sock, RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", version))
        msg_type, payload = recv_non_text(sock)
        if msg_type != RTDE_PROTOCOL_VERSION_REPLY or len(payload) < 1:
            self._unexpected(
                RTDE_PROTOCOL_VERSION_REPLY,
                msg_type,
                payload,
                "waehrend Versions-Handshake",
            )
        accepted = payload[0]
        log.info("RTDE: Protokollversion %d %s", version, "akzeptiert" if accepted else "abgelehnt")
        return accepted == 1

    # ------------------------------------------------------------------
    def _unexpected(
        self, expected: int, msg_type: int, payload: bytes, context: str
    ) -> None:
        """Erzeugt eine ausführliche Fehlermeldung."""

        exp_name = type_name(expected)
        msg = (
            f"RTDE: erwartet {exp_name}, erhalten {frame_str(msg_type, payload)} {context}"
        )
        log.error(msg)
        raise CommunicationError(msg)


# ---------------------------------------------------------------------------
# Öffentliche Helfer
# ---------------------------------------------------------------------------
def read_rtde_pose(
    host: str,
    port: int = RTDE_PORT,
    timeout: float = 3.0,
    debug: bool = False,
) -> Tuple[float, float, float, float, float, float]:
    """Komfortfunktion zum Lesen der TCP-Pose."""

    client = RTDEOneShotClient(host=host, port=port, timeout=timeout, debug=debug)
    return client.read_pose()


def _main() -> None:
    parser = argparse.ArgumentParser(description="Liest einmalig actual_TCP_pose")
    parser.add_argument("--host", default="10.3.218.4")
    parser.add_argument("--port", type=int, default=30004)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    client = RTDEOneShotClient(
        host=args.host, port=args.port, timeout=args.timeout, debug=args.debug
    )
    try:
        pose = client.read_pose()
        print("Pose:", pose)
    except CommunicationError as exc:  # pragma: no cover - CLI-Ausgabe
        log.error("RTDE: Fehler: %s", exc)


if __name__ == "__main__":  # pragma: no cover - manuelles Ausführen
    _main()

