import os
import socket
import struct
import threading
import time

import pytest

os.sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rtde_one_shot import (
    RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS,
    RTDE_CONTROL_PACKAGE_START,
    RTDE_DATA_PACKAGE,
    RTDE_PORT,
    RTDE_REQUEST_PROTOCOL_VERSION,
    read_rtde_pose,
)


def _send_frame(conn: socket.socket, msg_type: int, payload: bytes = b"") -> None:
    conn.sendall(struct.pack(">HB", len(payload) + 3, msg_type) + payload)


def _recv_frame(conn: socket.socket) -> tuple[int, bytes]:
    header = conn.recv(3)
    if not header:
        raise ConnectionError("empty header")
    length, msg_type = struct.unpack(">HB", header)
    payload = conn.recv(length - 3)
    return msg_type, payload


def _start_dummy_server(pose: tuple[float, ...]) -> threading.Thread:
    def server() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", RTDE_PORT))
            srv.listen(1)
            conn, _ = srv.accept()
            with conn:
                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_REQUEST_PROTOCOL_VERSION
                ver = struct.unpack(">H", payload)[0]
                _send_frame(conn, RTDE_REQUEST_PROTOCOL_VERSION, struct.pack(">H", ver))

                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS
                _send_frame(conn, RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS, b"\x01\x01")

                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_CONTROL_PACKAGE_START
                _send_frame(conn, RTDE_CONTROL_PACKAGE_START, b"\x01")

                _send_frame(
                    conn,
                    RTDE_DATA_PACKAGE,
                    b"\x01" + struct.pack(">6d", *pose),
                )

                try:
                    _recv_frame(conn)  # optional pause
                except Exception:
                    pass

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    time.sleep(0.1)
    return thread


def test_read_rtde_pose() -> None:
    pose = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    thread = _start_dummy_server(pose)
    result = read_rtde_pose("127.0.0.1", timeout=1.0)
    assert result == pytest.approx(pose)
    thread.join(timeout=0.1)

