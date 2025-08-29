import socket
import time
import re
import math
import logging
from typing import Optional, Tuple, List

# Port descriptions
PORTS = {
    30001: "Primary Client Interface",
    30002: "Secondary Client Interface (Script)",
    30003: "Real-time Client Interface"
}

# Debug flag
DEBUG = True

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def debug_print(message: str) -> None:
    """Helper to print debug messages when DEBUG is True"""
    if DEBUG:
        print(f"[DEBUG] {message}")


def decode_robot_data(raw_data: bytes) -> Optional[str]:
    """Tries different encodings for robust decoding"""
    for encoding in ['utf-8', 'latin-1', 'ascii', 'cp1252']:
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def receive_tcp_data(sock: socket.socket) -> Optional[str]:
    """Receives and decodes robot data robustly"""
    raw_data = b""
    start_time = time.time()

    while time.time() - start_time < 3.0:
        try:
            sock.settimeout(0.2)
            chunk = sock.recv(1024)
            if not chunk:
                break
            raw_data += chunk

            decoded = decode_robot_data(raw_data)
            if decoded and '[' in decoded and ']' in decoded:
                return decoded
        except socket.timeout:
            continue
        except Exception as exc:
            logger.error(f"Fehler beim Empfang der Daten: {exc}")
            break

    if raw_data:
        logger.error(f"Rohdaten (Hex): {raw_data.hex()[:100]}")
    return None


def parse_tcp_position(response: str) -> Optional[List[float]]:
    """Parses TCP position from different formats"""
    values = None

    match1 = re.search(r'\[([^\]]+)\]', response)
    if match1:
        try:
            values = [float(x.strip()) for x in match1.group(1).split(',')]
        except ValueError:
            pass

    if not values:
        match2 = re.search(r'p\[([^\]]+)\]', response)
        if match2:
            try:
                values = [float(x.strip()) for x in match2.group(1).split(',')]
            except ValueError:
                pass

    if not values:
        numbers = re.findall(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', response)
        if len(numbers) >= 6:
            values = [float(x) for x in numbers[:6]]

    return values[:6] if values and len(values) >= 6 else None


def try_connection(ip: str, ports: List[int] = [30002, 30003, 30001]) -> Tuple[Optional[socket.socket], Optional[int], List[str]]:
    messages: List[str] = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((ip, port))
            messages.append(f"\u2713 Verbindung erfolgreich auf Port {port} ({PORTS.get(port, 'Unknown')})")
            return sock, port, messages
        except Exception:
            messages.append(f"\u2717 Port {port} fehlgeschlagen")
            continue
    return None, None, messages


class URRobotError(Exception):
    """Custom exception for UR robot errors"""
    pass


def is_valid_position(values: List[float]) -> bool:
    """Validate TCP values for realistic ranges"""
    x_mm, y_mm, z_mm = [v * 1000 for v in values[:3]]
    rx_deg, ry_deg, rz_deg = [math.degrees(v) for v in values[3:]]

    if not all(-2000 <= v <= 2000 for v in (x_mm, y_mm, z_mm)):
        return False
    if not all(-360 <= v <= 360 for v in (rx_deg, ry_deg, rz_deg)):
        return False
    return True


def get_tcp_position(ip: str, ports: List[int] = [30002, 30003, 30001], retries: int = 3) -> Tuple[Optional[List[float]], str]:
    """Retrieve TCP position with retry and error handling"""
    log_lines: List[str] = []
    for attempt in range(1, retries + 1):
        log_lines.append(f"Verbindungsversuch {attempt}/{retries}")
        sock, port, conn_msgs = try_connection(ip, ports)
        log_lines.extend(conn_msgs)
        if not sock:
            log_lines.append("Keine Verbindung zum Roboter hergestellt")
            continue
        try:
            cmd = "get_actual_tcp_pose()\n"
            sock.send(cmd.encode('utf-8'))
            response = receive_tcp_data(sock)
            debug_print(f"Empfangen: {response[:100] if response else 'None'}")
            if not response:
                raise URRobotError("Keine Antwort erhalten")

            if any(keyword in response.lower() for keyword in ["error", "protective", "safety"]):
                raise URRobotError(f"UR-Fehler: {response.strip()[:100]}")

            values = parse_tcp_position(response)
            debug_print(f"Geparste Werte: {values}")
            if not values:
                raise URRobotError("TCP-Position konnte nicht geparst werden")

            if not is_valid_position(values):
                raise URRobotError("TCP-Werte außerhalb des zulässigen Bereichs")

            # convert to mm and deg
            x, y, z = [v * 1000 for v in values[:3]]
            rx, ry, rz = [math.degrees(v) for v in values[3:]]
            position = [x, y, z, rx, ry, rz]
            return position, "\n".join(log_lines)

        except (socket.error, URRobotError) as exc:
            logger.error(f"Fehler beim Abrufen der TCP-Position: {exc}")
            log_lines.append(f"Fehler beim Abrufen der TCP-Position: {exc}")
        finally:
            sock.close()
        time.sleep(1)
    log_lines.append("TCP-Pose konnte nicht ermittelt werden")
    return None, "\n".join(log_lines)


def main():
    ip = input("Geben Sie die IP-Adresse des UR-Roboters ein: ")
    port_input = input("Port eingeben (Enter für automatische Suche): ").strip()
    ports = [int(port_input)] if port_input else [30002, 30003, 30001]
    tcp_pos, log_msg = get_tcp_position(ip, ports)
    if tcp_pos:
        print("TCP-Position (mm, Grad):")
        print(f"X: {tcp_pos[0]:.3f}, Y: {tcp_pos[1]:.3f}, Z: {tcp_pos[2]:.3f}")
        print(f"RX: {tcp_pos[3]:.3f}, RY: {tcp_pos[4]:.3f}, RZ: {tcp_pos[5]:.3f}")
    else:
        print(log_msg)


if __name__ == "__main__":
    main()