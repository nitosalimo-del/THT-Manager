import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

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
