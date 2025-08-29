import re
import socket
import logging
from typing import Optional, List

from database_manager import DatabaseManager

WU_RE = re.compile(r"\bWU\d+\b")


def _extract_wu(payload: str) -> Optional[str]:
    """Extrahiert eine WU-Nummer aus dem Payload."""
    m = WU_RE.search(payload or "")
    return m.group(0) if m else None


def _get_product_row_by_wu(db: DatabaseManager, wu: str) -> Optional[dict]:
    """Holt eine Produktzeile anhand der WU-Nummer."""
    return db.get_by_wu(wu)


def _format_row_as_underscore_string(row: dict, fields: List[str] | None = None) -> str:
    """Formatiert eine Datenbankzeile als Unterstrich-getrennten String."""
    if not row:
        return ""
    if fields:
        vals = [str(row.get(k, "")) for k in fields]
    else:
        vals = [str(row[k]) for k in sorted(row.keys())]
    return "_".join(vals)


def _send_to_cobot(ip: str, port: int, message: str, read_ok: bool = True, timeout: float = 5.0) -> bool:
    """Sendet eine Nachricht an den Cobot und wartet optional auf ein 'OK'."""
    with socket.create_connection((ip, port), timeout=timeout) as s:
        s.sendall((message + "\n").encode("utf-8"))
        if not read_ok:
            return True
        s.settimeout(timeout)
        try:
            resp = s.recv(4096).decode("utf-8", errors="ignore").strip()
            return resp == "OK"
        except Exception:
            return False


def handle_listener_payload(payload: str, db: DatabaseManager, send_ip: str, send_port: int, logger: logging.Logger) -> None:
    """Verarbeitet eine Listener-Nachricht: WU extrahieren, DB-Lookup, Antwort senden."""
    wu = _extract_wu(payload)
    if not wu:
        logger.info(f"Keine WU-Nummer erkannt in: {payload}")
        return

    row = _get_product_row_by_wu(db, wu)
    message = _format_row_as_underscore_string(row) if row else "NichtVorhanden"

    ok = _send_to_cobot(send_ip, send_port, message)
    if not ok:
        logger.warning("Keine OK-Antwort vom Cobot erhalten")
