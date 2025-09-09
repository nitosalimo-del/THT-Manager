import os
import socket
import struct
import threading
import time

import pytest

os.sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rtde_one_shot import (
    RTDE_CONTROL_PACKAGE_PAUSE,
    RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS,
    RTDE_CONTROL_PACKAGE_START,
    RTDE_DATA_PACKAGE,
    RTDE_PROTOCOL_VERSION_REPLY,
    RTDE_REQUEST_PROTOCOL_VERSION,
    RTDE_TEXT_MESSAGE_UR,
    RTDE_PORT,
    RTDEOneShotClient,
    frame_str,
    hexdump,
    read_rtde_pose,
    recv_frame,
    send_frame,
    type_name,
)


def test_util_functions() -> None:
    data = bytes([0, 1, 2, 255])
    assert hexdump(data) == "00 01 02 FF"
    assert type_name(RTDE_REQUEST_PROTOCOL_VERSION) == "REQUEST_PROTOCOL_VERSION"
    fstr = frame_str(RTDE_REQUEST_PROTOCOL_VERSION, b"\x00\x02")
    assert "type=0x56" in fstr and "len=2" in fstr and "00 02" in fstr


def _send_frame(conn: socket.socket, msg_type: int, payload: bytes = b"") -> None:
    send_frame(conn, msg_type, payload)


def _recv_frame(conn: socket.socket) -> tuple[int, bytes]:
    return recv_frame(conn)


def _start_dummy_server(
    pose: tuple[float, ...],
    *,
    accept_version: int = 2,
    send_text: bool = False,
) -> threading.Thread:
    def server() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", RTDE_PORT))
            srv.listen(1)
            conn, _ = srv.accept()
            with conn:
                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_REQUEST_PROTOCOL_VERSION
                if send_text:
                    _send_frame(conn, RTDE_TEXT_MESSAGE_UR, b"dummy")
                if accept_version == 2:
                    _send_frame(conn, RTDE_PROTOCOL_VERSION_REPLY, b"\x01")
                else:
                    _send_frame(conn, RTDE_PROTOCOL_VERSION_REPLY, b"\x00")
                    msg_type, payload = _recv_frame(conn)
                    assert msg_type == RTDE_REQUEST_PROTOCOL_VERSION
                    _send_frame(conn, RTDE_PROTOCOL_VERSION_REPLY, b"\x01")

                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS
                _send_frame(conn, RTDE_CONTROL_PACKAGE_SETUP_OUTPUTS, b"\x05types")

                msg_type, payload = _recv_frame(conn)
                assert msg_type == RTDE_CONTROL_PACKAGE_START
                _send_frame(conn, RTDE_CONTROL_PACKAGE_START, b"\x01")

                _send_frame(
                    conn,
                    RTDE_DATA_PACKAGE,
                    b"\x05" + struct.pack(">6d", *pose),
                )
                conn.settimeout(0.2)
                try:
                    msg_type, _ = _recv_frame(conn)
                    assert msg_type == RTDE_CONTROL_PACKAGE_PAUSE
                except Exception:
                    pass

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    time.sleep(0.1)
    return thread


def test_read_rtde_pose() -> None:
    pose = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    thread = _start_dummy_server(pose, send_text=True)
    result = read_rtde_pose("127.0.0.1", timeout=1.0, debug=True)
    assert result == pytest.approx(pose)
    thread.join(timeout=0.1)


def test_version_fallback() -> None:
    pose = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    thread = _start_dummy_server(pose, accept_version=1)
    client = RTDEOneShotClient(host="127.0.0.1", timeout=1.0)
    result = client.read_pose()
    assert result == pytest.approx(pose)
    thread.join(timeout=0.1)

