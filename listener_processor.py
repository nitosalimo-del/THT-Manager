import re
import socket
import logging
from typing import Optional, List, Callable

from database_manager import DatabaseManager
from config import Config

# Unterstützt Produktnummern im Format "WU123" oder "WUBRE123".
PRODUCT_RE = re.compile(r"\b(?:WU|WUBRE)\d+\b")
# Rückwärtskompatibler Alias
WU_RE = PRODUCT_RE


def _extract_wu(payload: str) -> Optional[str]:
    """Extrahiert eine Produktnummer (WU/WUBRE) aus dem Payload."""
    m = WU_RE.search(payload or "")
    return m.group(0) if m else None


def _get_product_row_by_wu(db: DatabaseManager, wu: str) -> Optional[dict]:
    """Holt eine Produktzeile anhand der WU-Nummer."""
    return db.get_by_wu(wu)


def _format_row_as_underscore_string(row: dict, fields: List[str] | None = None) -> str:
    """Formatiert eine Datenbankzeile als "KEY:WERT"-Paare."""
    if not row:
        return ""

    field_order = fields if fields is not None else Config.get_all_fields()
    parts: List[str] = []
    for field in field_order:
        code = Config.get_field_code(field)
        val = str(row.get(field, ""))
        parts.append(f"{code}:{val}")
    return "_".join(parts)


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


def handle_listener_payload(payload: str, db: DatabaseManager, send_ip: str, send_port: int,
                            logger: logging.Logger,
                            log_event: Optional[Callable[[str, str, str], None]] = None) -> None:
    """Verarbeitet eine Listener-Nachricht: WU extrahieren, DB-Lookup, Antwort senden.

    Args:
        payload: Empfangener Nachrichteninhalt.
        db: Datenbankmanager für Produktinformationen.
        send_ip: Ziel-IP für die Antwortnachricht.
        send_port: Ziel-Port für die Antwortnachricht.
        logger: Logger-Instanz für Statusmeldungen.
        log_event: Optionaler Callback zum Protokollieren gesendeter Nachrichten.
    """
    wu = _extract_wu(payload)
    if not wu:
        logger.info(f"Keine WU-Nummer erkannt in: {payload}")
        return

    row = _get_product_row_by_wu(db, wu)
    message = (
        _format_row_as_underscore_string(row, Config.get_all_fields())
        if row
        else "NichtVorhanden"
    )

    # Gesendete Nachricht im Listener-Fenster anzeigen
    if log_event:
        try:
            log_event("MESSAGE_SENT", message, send_ip)
        except Exception:
            pass

    ok = _send_to_cobot(send_ip, send_port, message)
    if not ok:
        logger.warning("Keine OK-Antwort vom Cobot erhalten")
