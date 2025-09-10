import socket
import threading
import time
from typing import List

import pytest

from device_tcp_client import DeviceTCPClient, DeviceTCPConfig


TEST_PORT = 35001


def _start_mock_server(messages: List[str], ready_event: threading.Event, stop_event: threading.Event) -> threading.Thread:
    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", TEST_PORT))
            sock.listen(1)
            ready_event.set()
            conn, _ = sock.accept()
            with conn:
                for msg in messages:
                    conn.sendall((msg + "\n").encode())
                    time.sleep(0.05)
                stop_event.wait()
    t = threading.Thread(target=server, daemon=True)
    t.start()
    return t


def test_client_receives_messages():
    ready = threading.Event()
    stop = threading.Event()
    server = _start_mock_server(["A", "B"], ready, stop)
    assert ready.wait(timeout=1)

    received: List[str] = []
    client = DeviceTCPClient(DeviceTCPConfig(ip="127.0.0.1", port=TEST_PORT), received.append)
    client.start()
    time.sleep(0.3)
    stop.set()
    server.join(timeout=1)
    client.stop()

    assert received == ["A", "B"]


def test_client_reconnects():
    first_ready = threading.Event()
    first_stop = threading.Event()
    srv1 = _start_mock_server(["one"], first_ready, first_stop)
    assert first_ready.wait(timeout=1)

    received: List[str] = []
    client = DeviceTCPClient(DeviceTCPConfig(ip="127.0.0.1", port=TEST_PORT), received.append)
    client.start()
    time.sleep(0.3)
    first_stop.set()
    srv1.join(timeout=1)

    second_ready = threading.Event()
    second_stop = threading.Event()
    srv2 = _start_mock_server(["two"], second_ready, second_stop)
    assert second_ready.wait(timeout=1)

    time.sleep(0.6)
    second_stop.set()
    srv2.join(timeout=1)
    client.stop()

    assert received == ["one", "two"]
