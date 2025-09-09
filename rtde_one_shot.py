"""RTDE One-Shot Client
=======================

Liest einmalig ``actual_TCP_pose`` von einem UR-kompatiblen RTDE-Server.

Der Client führt den RTDE-Handshake aus, startet den Datenstrom und
wartet auf genau ein ``DATA_PACKAGE``. Die Pose wird in SI-Einheiten
(m, rad) zurückgegeben.

How-to-Test:
    1. Dummy-Server auf ``127.0.0.1:30004`` starten.
    2. Im THT-Manager Roboter-IP auf ``127.0.0.1`` setzen.
    3. Button ``TCP-Pose (UR) testen`` klicken.
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
PROTOCOL_VERSION_REPLY = 0x50  # 'P'
CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F  # 'O'
CONTROL_PACKAGE_INPUTS = 0x4E  # 'N'
CONTROL_PACKAGE_SET_INPUTS = 0x49  # 'I'
CONTROL_PACKAGE_START = 0x53  # 'S'
CONTROL_PACKAGE_PAUSE = 0x50  # 'P' (gleiche ID wie PROTOCOL_VERSION_REPLY)
DATA_PACKAGE = 0x55  # 'U'
TEXT_MESSAGE = 0x62  # 'b'

RTDE_PORT = 30004

# Öffentliche Aliase für Tests ------------------------------------------------
RTDE_REQUEST_PROTOCOL_VERSION = REQUEST_PROTOCOL_VERSION
RTDE_PROTOCOL_VERSION_REPLY = PROTOCOL_VERSION_REPLY
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = CONTROL_PACKAGE_SETUP_OUTPUTS
RTDE_CONTROL_PACKAGE_START = CONTROL_PACKAGE_START
RTDE_CONTROL_PACKAGE_PAUSE = CONTROL_PACKAGE_PAUSE
RTDE_DATA_PACKAGE = DATA_PACKAGE
RTDE_TEXT_MESSAGE = TEXT_MESSAGE

MSG_NAMES = {
    REQUEST_PROTOCOL_VERSION: "REQUEST_PROTOCOL_VERSION",
    PROTOCOL_VERSION_REPLY: "PROTOCOL_VERSION_REPLY",
    CONTROL_PACKAGE_SETUP_OUTPUTS: "CONTROL_PACKAGE_SETUP_OUTPUTS",
    CONTROL_PACKAGE_START: "CONTROL_PACKAGE_START",
    CONTROL_PACKAGE_PAUSE: "CONTROL_PACKAGE_PAUSE",
    DATA_PACKAGE: "DATA_PACKAGE",
    TEXT_MESSAGE: "TEXT_MESSAGE",
}


def _msg_name(msg_type: int) -> str:
    return MSG_NAMES.get(msg_type, f"UNKNOWN(0x{msg_type:02X})")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    """Empfängt exakt ``size`` Bytes oder wirft ``CommunicationError``."""
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

    host: str = "10.3.218.4"
    port: int = RTDE_PORT
    timeout: float = 3.0
    recipe_id: int | None = None

    # Low-Level Frame-Handling ---------------------------------------------
    def _send_frame(self, sock: socket.socket, msg_type: int, payload: bytes = b"") -> None:
        frame = struct.pack(">HB", len(payload) + 3, msg_type) + payload
        sock.sendall(frame)
        log.debug("RTDE: send %s", _msg_name(msg_type))

    def _recv_frame(self, sock: socket.socket) -> Tuple[int, bytes]:
        header = _recv_exact(sock, 3)
        length, msg_type = struct.unpack(">HB", header)
        payload = _recv_exact(sock, length - 3)
        log.debug("RTDE: recv %s", _msg_name(msg_type))
        return msg_type, payload

    def _recv_non_text(self, sock: socket.socket) -> Tuple[int, bytes]:
        """Liest das nächste Nicht-Text-Paket."""
        while True:
            msg_type, payload = self._recv_frame(sock)
            if msg_type == TEXT_MESSAGE:
                try:
                    text = payload.decode("utf-8", errors="ignore").strip()
                except Exception:
                    text = "<unlesbar>"
                log.info("RTDE: Text: %s", text)
                continue
            return msg_type, payload

    # Public API -----------------------------------------------------------
    def read_pose(self) -> Tuple[float, float, float, float, float, float]:
        """Liest ``actual_TCP_pose`` und gibt die Pose zurück."""
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as sock:
                sock.settimeout(self.timeout)
                self._handshake(sock)

                msg_type, payload = self._recv_non_text(sock)
                if msg_type != DATA_PACKAGE:
                    raise CommunicationError("RTDE: Erwartetes DATA_PACKAGE fehlt")
                if len(payload) < 1 + DATA_SIZE:
                    raise CommunicationError("RTDE: DATA_PACKAGE zu kurz")
                if payload[0] != self.recipe_id:
                    raise CommunicationError("RTDE: falsche recipe_id")

                pose = struct.unpack(DATA_FORMAT, payload[1 : 1 + DATA_SIZE])

                # Best-Effort Pause
                try:
                    self._send_frame(sock, CONTROL_PACKAGE_PAUSE)
                except OSError:
                    pass

                log.info("RTDE: Pose empfangen")
                return pose
        except (socket.timeout, OSError) as exc:
            log.error("RTDE: Netzwerkfehler: %s", exc)
            raise CommunicationError(f"RTDE: Netzwerkfehler: {exc}") from exc

    # Internals ------------------------------------------------------------
    def _handshake(self, sock: socket.socket) -> None:
        """Führt RTDE-Handshake aus und speichert ``recipe_id``."""
        # 1. Protokollversion aushandeln
        accepted = self._request_version(sock, 2)
        if accepted != 2:
            log.warning("RTDE: Version 2 abgelehnt, versuche Version 1")
            accepted = self._request_version(sock, 1)
            if accepted != 1:
                raise CommunicationError("RTDE: Protokollversion nicht akzeptiert")

        # 2. Outputs konfigurieren
        var = b"actual_TCP_pose"
        payload = struct.pack(">HH", 125, len(var)) + var
        self._send_frame(sock, CONTROL_PACKAGE_SETUP_OUTPUTS, payload)
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != CONTROL_PACKAGE_SETUP_OUTPUTS or len(payload) < 2:
            raise CommunicationError("RTDE: Setup outputs fehlgeschlagen")
        if payload[0] != 1:
            raise CommunicationError("RTDE: Setup outputs rejected")
        self.recipe_id = payload[1]
        log.info("RTDE: Outputs konfiguriert (recipe_id=%d)", self.recipe_id)

        # 3. Start
        self._send_frame(sock, CONTROL_PACKAGE_START)
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != CONTROL_PACKAGE_START or len(payload) < 1 or payload[0] != 1:
            raise CommunicationError("RTDE: Start fehlgeschlagen")
        log.info("RTDE: Datenstrom gestartet")

    def _request_version(self, sock: socket.socket, version: int) -> int:
        """Fragt Protokollversion an und liefert akzeptierte Version."""
        self._send_frame(sock, REQUEST_PROTOCOL_VERSION, struct.pack(">H", version))
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != PROTOCOL_VERSION_REPLY or len(payload) < 2:
            raise CommunicationError("RTDE: Ungültige Versionsantwort")
        accepted = struct.unpack(">H", payload[:2])[0]
        log.info("RTDE: Version %d akzeptiert", accepted)
        return accepted


def read_rtde_pose(
    host: str,
    port: int = RTDE_PORT,
    timeout: float = 3.0,
) -> Tuple[float, float, float, float, float, float]:
    """Komfortfunktion für bestehenden Code."""
    client = RTDEOneShotClient(host=host, port=port, timeout=timeout)
    return client.read_pose()

