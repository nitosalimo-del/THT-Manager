"""TCP-Client für Machine-Vision-Geräte"""
import os
import socket
import threading
import time
import logging
from dataclasses import dataclass
from typing import Callable, Optional


class DeviceTCPError(Exception):
    """Allgemeiner Fehler für DeviceTCPClient"""


@dataclass
class DeviceTCPConfig:
    """Konfigurationsdaten für die TCP-Verbindung"""
    ip: str
    port: int = 34000
    reconnect_delay: float = 1.0
    timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "DeviceTCPConfig":
        """Erstellt Konfiguration aus Umgebungsvariablen"""
        return cls(
            ip=os.getenv("DEVICE_IP", "127.0.0.1"),
            port=int(os.getenv("DEVICE_PORT", "34000")),
            reconnect_delay=float(os.getenv("DEVICE_RECONNECT_DELAY", "1.0")),
            timeout=float(os.getenv("DEVICE_TIMEOUT", "5.0")),
        )


class DeviceTCPClient:
    """TCP-Client für Machine-Vision-Geräte"""

    def __init__(self, config: DeviceTCPConfig, handler: Callable[[str], None]):
        self.config = config
        self.handler = handler
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.logger = logging.getLogger(__name__)

    def start(self) -> None:
        """Startet den Listener-Thread"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Beendet den Listener-Thread"""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _connect(self) -> socket.socket:
        sock = socket.create_connection(
            (self.config.ip, self.config.port), timeout=self.config.timeout
        )
        sock.settimeout(1.0)
        return sock

    def _run(self) -> None:
        backoff = self.config.reconnect_delay
        while self._running:
            try:
                self._socket = self._connect()
                self.logger.info(
                    "Verbunden mit %s:%s", self.config.ip, self.config.port
                )
                buffer = ""
                backoff = self.config.reconnect_delay
                while self._running:
                    try:
                        data = self._socket.recv(4096)
                        if not data:
                            raise DeviceTCPError("Verbindung getrennt")
                        buffer += data.decode("utf-8", errors="ignore")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line:
                                self.handler(line)
                    except socket.timeout:
                        continue
            except Exception as exc:  # Netzwerkfehler und Handler-Fehler
                if self._running:
                    self.logger.warning("Verbindungsfehler: %s", exc)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            finally:
                if self._socket:
                    try:
                        self._socket.close()
                    except OSError:
                        pass
                    self._socket = None
