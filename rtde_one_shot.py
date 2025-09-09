"""RTDE One-Shot Client
=======================

Liest einmalig ``actual_TCP_pose`` von einem UR-kompatiblen RTDE-Server.

Der Client richtet die Ausgaben ein, startet den RTDE-Datenstrom, wartet auf
genau ein ``DATA_PACKAGE`` und beendet anschließend die Verbindung wieder. Die
Pose wird in SI-Einheiten (m, rad) zurückgegeben.

How-to-Test:
    1. Dummy-Server auf ``127.0.0.1:30004`` starten (Streaming aus, mm/deg aus).
    2. Im THT-Manager Roboter-IP auf ``127.0.0.1`` setzen.
    3. Button ``TCP-Pose (UR) testen`` klicken → Pose erscheint in Spalte
       „abgerufen“ und wird in die DB geschrieben.
"""
from __future__ import annotations

import logging
import socket
import struct
from dataclasses import dataclass
from typing import Tuple

from exceptions import CommunicationError

log = logging.getLogger(__name__)

# RTDE Message Type IDs -------------------------------------------------------
REQUEST_PROTOCOL_VERSION = 0x56  # 'V'
CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F  # 'O'
CONTROL_PACKAGE_SETUP_INPUTS = 0x4E  # 'N'
CONTROL_PACKAGE_SET_INPUTS = 0x49  # 'I'
CONTROL_PACKAGE_START = 0x53  # 'S'
CONTROL_PACKAGE_PAUSE = 0x50  # 'P'
DATA_PACKAGE = 0x55  # 'U'

# Public aliases (used by tests)
RTDE_REQUEST_PROTOCOL_VERSION = REQUEST_PROTOCOL_VERSION
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = CONTROL_PACKAGE_SETUP_OUTPUTS
RTDE_CONTROL_PACKAGE_START = CONTROL_PACKAGE_START
RTDE_CONTROL_PACKAGE_PAUSE = CONTROL_PACKAGE_PAUSE
RTDE_DATA_PACKAGE = DATA_PACKAGE

RTDE_PORT = 30004

MSG_NAMES = {
    REQUEST_PROTOCOL_VERSION: "REQUEST_PROTOCOL_VERSION",
    CONTROL_PACKAGE_SETUP_OUTPUTS: "CONTROL_PACKAGE_SETUP_OUTPUTS",
    CONTROL_PACKAGE_SETUP_INPUTS: "CONTROL_PACKAGE_SETUP_INPUTS",
    CONTROL_PACKAGE_SET_INPUTS: "CONTROL_PACKAGE_SET_INPUTS",
    CONTROL_PACKAGE_START: "CONTROL_PACKAGE_START",
    CONTROL_PACKAGE_PAUSE: "CONTROL_PACKAGE_PAUSE",
    DATA_PACKAGE: "DATA_PACKAGE",
}


def _msg_name(msg_type: int) -> str:
    return MSG_NAMES.get(msg_type, f"UNKNOWN(0x{msg_type:02X})")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly ``size`` bytes or raise ``CommunicationError``."""
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise CommunicationError("RTDE: Verbindung unerwartet geschlossen")
        data += chunk
    return data


DATA_FORMAT = ">6d"
DATA_SIZE = struct.calcsize(DATA_FORMAT)


@dataclass
class RTDEOneShotClient:
    """Minimaler RTDE-Client für eine einzige Pose."""

    host: str
    port: int = RTDE_PORT
    timeout: float = 3.0
    recipe_id: int | None = None

    def _send_frame(
        self, sock: socket.socket, msg_type: int, payload: bytes = b""
    ) -> None:
        frame = struct.pack(">HB", len(payload) + 3, msg_type) + payload
        sock.sendall(frame)
        log.debug("RTDE: send %s", _msg_name(msg_type))

    def _recv_frame(self, sock: socket.socket) -> Tuple[int, bytes]:
        header = _recv_exact(sock, 3)
        length, msg_type = struct.unpack(">HB", header)
        payload = _recv_exact(sock, length - 3)
        log.debug("RTDE: recv %s", _msg_name(msg_type))
        return msg_type, payload

    # Public API ------------------------------------------------------------
    def read_pose(self) -> Tuple[float, float, float, float, float, float]:
        """Liest ``actual_TCP_pose`` und gibt die Pose zurück."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))

                self._handshake(sock)

                msg_type, payload = self._recv_frame(sock)
                if msg_type != DATA_PACKAGE:
                    raise CommunicationError("RTDE: Erwartetes DATA_PACKAGE fehlt")
                if len(payload) < 1 + DATA_SIZE:
                    raise CommunicationError("RTDE: DATA_PACKAGE zu kurz")
                if payload[0] != self.recipe_id:
                    raise CommunicationError("RTDE: falsche recipe_id")

                pose = struct.unpack(DATA_FORMAT, payload[1 : 1 + DATA_SIZE])

                # Versuchsweise Pause senden (best effort)
                try:
                    self._send_frame(sock, CONTROL_PACKAGE_PAUSE)
                except OSError:
                    pass

                return pose

        except (socket.timeout, OSError) as exc:
            raise CommunicationError(f"RTDE: Netzwerkfehler: {exc}") from exc

    # Internals -------------------------------------------------------------
    def _handshake(self, sock: socket.socket) -> None:
        """Führt RTDE-Handshake aus und speichert ``recipe_id``."""
        # 1. Protokollversion aushandeln
        self._send_frame(sock, REQUEST_PROTOCOL_VERSION, struct.pack(">H", 2))
        msg_type, payload = self._recv_frame(sock)
        if msg_type != REQUEST_PROTOCOL_VERSION or len(payload) < 2:
            raise CommunicationError("RTDE: Protokollversion nicht akzeptiert")
        if struct.unpack(">H", payload[:2])[0] != 2:
            raise CommunicationError("RTDE: Falsche Protokollversion")

        # 2. Ausgaben für actual_TCP_pose konfigurieren
        var = b"actual_TCP_pose"
        payload = struct.pack(">HH", 125, len(var)) + var
        self._send_frame(sock, CONTROL_PACKAGE_SETUP_OUTPUTS, payload)
        msg_type, payload = self._recv_frame(sock)
        if msg_type != CONTROL_PACKAGE_SETUP_OUTPUTS or len(payload) < 2:
            raise CommunicationError("RTDE: Setup outputs fehlgeschlagen")
        if payload[0] != 1:
            raise CommunicationError("RTDE: Setup outputs rejected")
        self.recipe_id = payload[1]

        # 3. Datenstrom starten
        self._send_frame(sock, CONTROL_PACKAGE_START)
        msg_type, payload = self._recv_frame(sock)
        if msg_type != CONTROL_PACKAGE_START or len(payload) < 1 or payload[0] != 1:
            raise CommunicationError("RTDE: Start failed")


def read_rtde_pose(
    host: str, timeout: float = 3.0
) -> Tuple[float, float, float, float, float, float]:
    """Komfortfunktion für bestehenden Code.

    Args:
        host: Ziel-Host des UR-Roboters oder Dummy-Servers.
        timeout: Timeout in Sekunden.
    """
    client = RTDEOneShotClient(host=host, timeout=timeout)
    return client.read_pose()
