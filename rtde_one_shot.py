import socket
import struct
import logging
from typing import Tuple

RTDE_PORT = 30004
RTDE_REQUEST_PROTOCOL_VERSION = 86
RTDE_PROTOCOL_VERSION = 0x50
RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS = 79
RTDE_CONTROL_PACKAGE_START = 0x53
RTDE_CONTROL_PACKAGE_STOP = 0x50
RTDE_DATA_PACKAGE = 0x55

log = logging.getLogger(__name__)


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    """Receive exactly *length* bytes from *sock*."""
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("Socket connection closed")
        data += chunk
    return data


def read_rtde_pose(host: str, timeout: float = 1.0) -> Tuple[float, float, float, float, float, float]:
    """Liest einmalig die actual_TCP_pose via RTDE.

    Args:
        host: IP-Adresse des UR-Roboters
        timeout: Socket-Timeout in Sekunden

    Returns:
        Tuple aus (x, y, z, rx, ry, rz) in SI-Einheiten.

    Raises:
        TimeoutError: wenn der Roboter nicht rechtzeitig antwortet
        RuntimeError: bei Protokollfehlern
        ConnectionError: bei Netzwerkproblemen
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        log.debug("Connecting to %s:%s", host, RTDE_PORT)
        sock.connect((host, RTDE_PORT))

        def send(cmd: int, payload: bytes = b"") -> None:
            size = len(payload) + 3
            sock.sendall(struct.pack(">HB", size, cmd) + payload)

        def recv() -> Tuple[int, bytes]:
            header = _recv_exact(sock, 3)
            size, cmd = struct.unpack(">HB", header)
            payload = _recv_exact(sock, size - 3)
            return cmd, payload

        # Request protocol version 2
        protocol_version = 2
        send(RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", protocol_version))
        cmd, payload = recv()
        if (
            cmd != RTDE_PROTOCOL_VERSION
            or len(payload) < 2
            or struct.unpack(">H", payload[:2])[0] != protocol_version
        ):
            raise RuntimeError("RTDE Protocol version not supported")

        # Setup outputs for actual_TCP_pose at 125Hz
        variables = "actual_TCP_pose".encode("utf-8")
        send(
            RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS,
            struct.pack(">HH%ds" % len(variables), 125, len(variables), variables),
        )
        cmd, payload = recv()
        if cmd != RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS or not payload:
            raise RuntimeError("Failed to setup RTDE outputs")
        recipe_id = payload[0]

        # Start data transmission
        send(RTDE_CONTROL_PACKAGE_START)
        cmd, payload = recv()
        if cmd != RTDE_CONTROL_PACKAGE_START or not payload or payload[0] == 0:
            raise RuntimeError("RTDE start failed")

        # Read one data package
        cmd, payload = recv()
        if cmd != RTDE_DATA_PACKAGE or not payload or payload[0] != recipe_id:
            raise RuntimeError("Invalid RTDE data package")
        if len(payload) < 1 + 6 * 8:
            raise RuntimeError("Incomplete RTDE pose data")
        pose = struct.unpack(">6d", payload[1:49])

        return pose

    except socket.timeout as exc:
        raise TimeoutError("RTDE timeout") from exc
    except ConnectionError:
        raise
    except Exception as exc:
        log.exception("RTDE communication error")
        raise RuntimeError("RTDE communication error") from exc
    finally:
        try:
            sock.settimeout(0.5)
            send(RTDE_CONTROL_PACKAGE_STOP)
        except Exception:
            pass
        sock.close()
