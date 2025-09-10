import sys
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).resolve().parents[1]))

import listener_processor
from listener_processor import _format_row_as_underscore_string


def test_format_row_with_codes():
    row = {
        "Laufende Nummer": 1,
        "Produktnummer": "WU123",
        "Kunde": "ACME",
    }
    fields = ["Laufende Nummer", "Produktnummer", "Kunde"]
    result = _format_row_as_underscore_string(row, fields)
    assert result == "LaufendeNummer:1_ProduktNr:WU123_Kunde:ACME"


def test_format_row_none():
    assert _format_row_as_underscore_string(None) == ""


def test_extract_wubre_number():
    payload = "foo WUBRE1234 bar"
    from listener_processor import _extract_wu

    assert _extract_wu(payload) == "WUBRE1234"


def test_extract_wu_lowercase_with_dash():
    payload = "foo wubre-1234 bar"
    from listener_processor import _extract_wu

    assert _extract_wu(payload) == "wubre-1234"


def test_extract_wu_with_trailing_letters():
    payload = (
        "13:47:07.405 \u2b07\ufe0f [MESSAGE_RECEIVED] 10.3.218.3: "
        "C:0F:6P:WU0000003CU:KundeBN:Arbeitsplatz 3"
    )
    from listener_processor import _extract_wu

    assert _extract_wu(payload) == "WU0000003CU"


def test_handle_listener_payload_appends_end(monkeypatch):
    class DummyDB:
        def get_by_wu(self, wu):
            return {"Laufende Nummer": 1, "Produktnummer": wu, "Kunde": "ACME"}

    sent: dict = {}

    def fake_send(ip: str, port: int, message: str, read_ok: bool = True, timeout: float = 5.0) -> bool:
        sent["msg"] = message
        return True

    monkeypatch.setattr(listener_processor, "_send_to_cobot", fake_send)

    log_messages: list = []

    def log_event(event: str, message: str, ip: str) -> None:
        log_messages.append(message)

    logger = logging.getLogger("test")

    listener_processor.handle_listener_payload(
        "WU123", DummyDB(), "127.0.0.1", 1234, logger, log_event
    )

    assert sent["msg"].endswith("END")
    assert log_messages[0].endswith("END")
