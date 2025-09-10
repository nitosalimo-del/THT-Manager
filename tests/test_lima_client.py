import socket
import threading
import time
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from communication_manager import LimaClient


def _start_chunked_server(response_chunks):
    port_holder = []

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port_holder.append(s.getsockname()[1])
            conn, _ = s.accept()
            with conn:
                conn.recv(1024)  # receive command
                for chunk in response_chunks:
                    conn.sendall(chunk.encode("utf-8"))
                    time.sleep(0.05)
                conn.sendall(b"\n")

    thread = threading.Thread(target=server, daemon=True)
    thread.start()

    while not port_holder:
        time.sleep(0.01)
    return port_holder[0], thread


def test_send_command_reads_chunked_response():
    port, thread = _start_chunked_server(["<TO", "k/>"])
    client = LimaClient("127.0.0.1", port, timeout=1.0)

    result = client.send_command("<T/>")

    assert result == "<TOk/>"
    thread.join(timeout=1)
