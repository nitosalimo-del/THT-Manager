import socket
import threading
import time
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from communication_manager import LimaClient


def _start_server(response: str):
    port_holder = []

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port_holder.append(s.getsockname()[1])
            conn, _ = s.accept()
            with conn:
                conn.recv(1024)
                conn.sendall(response.encode("utf-8"))

    thread = threading.Thread(target=server, daemon=True)
    thread.start()

    while not port_holder:
        time.sleep(0.01)
    return port_holder[0], thread


def test_send_command_receives_response():
    port, thread = _start_server("<TOk/>\n")
    client = LimaClient("127.0.0.1", port, timeout=1.0)

    result = client.send_command("<T/>")

    assert result == "<TOk/>"
    thread.join(timeout=1)
