"""RTDE One-Shot Client
=======================

Liest einmalig ``actual_TCP_pose`` von einem UR-kompatiblen RTDE-Server und
liefert die Pose in Metern und Radiant.

Der Client implementiert die nötige Version-Aushandlung mit Fallback auf
Protokollversion 1 und gibt bei Fehlern ausführliche Diagnosen aus.
"""
from __future__ import annotations

import argparse
import logging
import socket
import struct
from typing import Tuple

from exceptions import CommunicationError

# -- Konstanten ---------------------------------------------------------------
REQUEST_PROTOCOL_VERSION = 0x56  # 'V'
PROTOCOL_VERSION_REPLY = 0x50  # 'P'
CONTROL_PACKAGE_SETUP_OUTPUTS = 0x4F  # 'O'
CONTROL_PACKAGE_START = 0x53  # 'S'
CONTROL_PACKAGE_PAUSE = 0x50  # 'P'
DATA_PACKAGE = 0x55  # 'U'
TEXT_MESSAGE = 0x62  # 'b'

RTDE_PORT = 30004

# Öffentliche Aliase (für Tests)
RTDE_REQUEST_PROTOCOL_VERSION = REQUEST_PROTOCOL_VERSION
RTDE_PROTOCOL_VERSION_REPLY = PROTOCOL_VERSION_REPLY
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = CONTROL_PACKAGE_SETUP_OUTPUTS
RTDE_CONTROL_PACKAGE_START = CONTROL_PACKAGE_START
RTDE_CONTROL_PACKAGE_PAUSE = CONTROL_PACKAGE_PAUSE
RTDE_DATA_PACKAGE = DATA_PACKAGE
RTDE_TEXT_MESSAGE = TEXT_MESSAGE

log = logging.getLogger(__name__)


# -- Hilfsfunktionen ---------------------------------------------------------
def hexdump(b: bytes, max_len: int = 64) -> str:
    """Gibt die ersten ``max_len`` Bytes als Hex-String zurück."""
    return " ".join(f"{byte:02X}" for byte in b[:max_len])


def type_name(msg_type: int) -> str:
    """Liefert den bekannten Namen eines Message-Typs."""
    names = {
        REQUEST_PROTOCOL_VERSION: "REQUEST_PROTOCOL_VERSION",
        PROTOCOL_VERSION_REPLY: "PROTOCOL_VERSION_REPLY",
        CONTROL_PACKAGE_SETUP_OUTPUTS: "CONTROL_PACKAGE_SETUP_OUTPUTS",
        CONTROL_PACKAGE_START: "CONTROL_PACKAGE_START",
        CONTROL_PACKAGE_PAUSE: "CONTROL_PACKAGE_PAUSE",
        DATA_PACKAGE: "DATA_PACKAGE",
        TEXT_MESSAGE: "TEXT_MESSAGE",
    }
    return names.get(msg_type, "UNKNOWN")


def frame_str(msg_type: int, payload: bytes) -> str:
    """Formatiert Typ, Länge und Hexdump eines Frames."""
    char = chr(msg_type) if 32 <= msg_type <= 126 else "?"
    return (
        f"type=0x{msg_type:02X}('{char}','{type_name(msg_type)}'), "
        f"len={len(payload)}, payload_hex={hexdump(payload)}"
    )


# -- Kernfunktionalität ------------------------------------------------------
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

    # -- Low-Level Frame Handling -----------------------------------------
    def _send_frame(self, sock: socket.socket, msg_type: int, payload: bytes = b"") -> None:
        frame = struct.pack(">HB", len(payload) + 3, msg_type) + payload
        sock.sendall(frame)
        log.debug("send %s", frame_str(msg_type, payload))

    def _recv_exact(self, sock: socket.socket, size: int, context: str) -> bytes:
        data = b""
        while len(data) < size:
            try:
                chunk = sock.recv(size - len(data))
            except socket.timeout as exc:
                msg = f"RTDE {self.host}:{self.port}: Timeout beim Lesen {context}"
                log.error(msg)
                raise CommunicationError(msg) from exc
            if not chunk:
                msg = f"RTDE {self.host}:{self.port}: Verbindung beendet {context}"
                log.error(msg)
                raise CommunicationError(msg)
            data += chunk
        return data

    def _recv_frame(self, sock: socket.socket) -> tuple[int, bytes]:
        header = self._recv_exact(sock, 3, "des Frame-Headers")
        length, msg_type = struct.unpack(">HB", header)
        if length < 3:
            msg = (
                f"RTDE {self.host}:{self.port}: unplausible Laenge {length} "
                f"im Header"
            )
            log.error(msg)
            raise CommunicationError(msg)
        payload = self._recv_exact(sock, length - 3, "des Frame-Payloads")
        log.debug("recv %s", frame_str(msg_type, payload))
        return msg_type, payload

    def _recv_non_text(self, sock: socket.socket) -> tuple[int, bytes]:
        """Liest das nächste Nicht-Text-Frame."""
        while True:
            msg_type, payload = self._recv_frame(sock)
            if msg_type == TEXT_MESSAGE:
                text = payload.decode("utf-8", errors="ignore").strip()
                log.info("RTDE Text: %s", text)
                continue
            return msg_type, payload

    # -- Fehlerbehandlung --------------------------------------------------
    def _raise_unexpected(
        self, expected: int, msg_type: int, payload: bytes, context: str
    ) -> None:
        exp_name = type_name(expected)
        msg = (
            f"RTDE {self.host}:{self.port}: erwartet {exp_name}, erhalten "
            f"{frame_str(msg_type, payload)} {context}"
        )
        log.error(msg)
        raise CommunicationError(msg)

    # -- Öffentliche API ---------------------------------------------------
    def read_pose(self) -> tuple[float, float, float, float, float, float]:
        """Führt Handshake aus und liefert die aktuelle TCP-Pose."""
        try:
            with socket.create_connection((self.host, self.port), self.timeout) as sock:
                sock.settimeout(self.timeout)
                self._handshake(sock)
                msg_type, payload = self._recv_non_text(sock)
                if msg_type != DATA_PACKAGE:
                    self._raise_unexpected(
                        DATA_PACKAGE, msg_type, payload, "beim Warten auf DATA_PACKAGE"
                    )
                if len(payload) < 49:  # 1 + 6 * 8
                    msg = (
                        f"RTDE {self.host}:{self.port}: zu kurzes DATA_PACKAGE: "
                        f"{frame_str(msg_type, payload)}"
                    )
                    log.error(msg)
                    raise CommunicationError(msg)
                recipe = payload[0]
                if recipe != self.recipe_id:
                    msg = (
                        f"RTDE {self.host}:{self.port}: recipe_id-Mismatch, erwartet "
                        f"{self.recipe_id}, erhalten {recipe}"
                    )
                    log.error(msg)
                    raise CommunicationError(msg)
                pose = struct.unpack(">6d", payload[1:49])
                try:
                    self._send_frame(sock, CONTROL_PACKAGE_PAUSE)
                except OSError:
                    pass
                log.info("Pose empfangen")
                return pose
        except OSError as exc:
            msg = f"RTDE {self.host}:{self.port}: Netzwerkfehler {exc}"
            log.error(msg)
            raise CommunicationError(msg) from exc

    # -- Interner Ablauf ---------------------------------------------------
    def _handshake(self, sock: socket.socket) -> None:
        accepted = self._request_version(sock, 2)
        if accepted != 2:
            log.warning("Version 2 abgelehnt (Server: %d)", accepted)
            accepted = self._request_version(sock, 1)
            if accepted != 1:
                payload = struct.pack(">H", accepted)
                msg = (
                    f"RTDE {self.host}:{self.port}: Protokollversion nicht akzeptiert: "
                    f"{frame_str(PROTOCOL_VERSION_REPLY, payload)}"
                )
                log.error(msg)
                raise CommunicationError(msg)

        var = b"actual_TCP_pose"
        payload = struct.pack(">HH", 125, len(var)) + var
        self._send_frame(sock, CONTROL_PACKAGE_SETUP_OUTPUTS, payload)
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != CONTROL_PACKAGE_SETUP_OUTPUTS or len(payload) < 2:
            self._raise_unexpected(
                CONTROL_PACKAGE_SETUP_OUTPUTS,
                msg_type,
                payload,
                "waehrend SETUP_OUTPUTS",
            )
        if payload[0] != 1:
            msg = (
                f"RTDE {self.host}:{self.port}: SETUP_OUTPUTS rejected: "
                f"{frame_str(msg_type, payload)}"
            )
            log.error(msg)
            raise CommunicationError(msg)
        self.recipe_id = payload[1]
        log.info("Outputs konfiguriert (recipe_id=%d)", self.recipe_id)

        self._send_frame(sock, CONTROL_PACKAGE_START)
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != CONTROL_PACKAGE_START or len(payload) < 1 or payload[0] != 1:
            self._raise_unexpected(
                CONTROL_PACKAGE_START, msg_type, payload, "waehrend START"
            )
        log.info("Datenstrom gestartet")

    def _request_version(self, sock: socket.socket, version: int) -> int:
        self._send_frame(sock, REQUEST_PROTOCOL_VERSION, struct.pack(">H", version))
        msg_type, payload = self._recv_non_text(sock)
        if msg_type != PROTOCOL_VERSION_REPLY:
            self._raise_unexpected(
                PROTOCOL_VERSION_REPLY, msg_type, payload, "waehrend Versions-Handshake"
            )
        if len(payload) < 2:
            msg = (
                f"RTDE {self.host}:{self.port}: Versionsantwort zu kurz: "
                f"{frame_str(msg_type, payload)}"
            )
            log.error(msg)
            raise CommunicationError(msg)
        accepted = struct.unpack(">H", payload[:2])[0]
        log.info("Protokollversion %d akzeptiert", accepted)
        return accepted


def read_rtde_pose(
    host: str, port: int = RTDE_PORT, timeout: float = 3.0
) -> tuple[float, float, float, float, float, float]:
    """Komfortfunktion für bestehenden Code."""
    client = RTDEOneShotClient(host=host, port=port, timeout=timeout)
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
    except CommunicationError as exc:
        log.error("Fehler: %s", exc)


if __name__ == "__main__":
    _main()
