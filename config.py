"""
Zentralisierte Konfiguration für den THT-Produktmanager
"""
from typing import Dict, Any
import os
import re

class Config:
    # Datenbankeinstellungen
    DB_FILE = "produktkatalog.db"
    
    # Admin-Einstellungen
    ADMIN_PASSWORD = "admin123"
    
    # Dateipfade
    LIMA_CONFIG_FILE = "lima_config.json"
    LOG_FILE = "produktmanager.log"
    
    # UI-Einstellungen
    WINDOW_SIZE = (1400, 800)
    SIDEBAR_WIDTH = 200
    
    # Standard LIMA-Konfiguration
    DEFAULT_LIMA_CONFIG = {
        "ip": "10.3.218.3",
        "port": 33020,
        "listener_port": 34000,
        "send_ip": "127.0.0.1",
        "send_port": 3401
    }
    
    # Datenbankfelder
    BASIC_FIELDS = [
        "Laufende Nummer", "Produktnummer", "Kunde", "Notizen"
    ]
    
    DIMENSION_FIELDS = [
        "Frame Width (mm)", "Frame Height (mm)"
    ]
    
    PCB_FIELDS = [
        "PCB_0 Top", "PCB_1 Back", "PCB_2 Right", "PCB_3 Front", "PCB_4 Left"
    ]
    
    AF_FIELDS = [
        "AF Breite", "AF Höhe", "AF Tiefe"
    ]
    
    EXTRA_FIELDS = [
        "AI angelegt", "AI Zeitstempel", "Cobot angelegt", "Cobot Zeitstempel"
    ]
    
    POSITION_FIELDS = [
        "PosPCB_0", "PosPCB_1", "PosPCB_2", "PosPCB_3", "PosPCB_4"
    ]

    # Feldbezeichnungen für die Kommunikation
    FIELD_CODES: Dict[str, str] = {
        "Laufende Nummer": "LaufendeNummer",
        "Produktnummer": "ProduktNr",
        "Kunde": "Kunde",
        "Notizen": "Notizen",
        "Frame Width (mm)": "FrameWidth",
        "Frame Height (mm)": "FrameHeight",
        "PCB_0 Top": "PCB0TOP",
        "PCB_1 Back": "PCB1BACK",
        "PCB_2 Right": "PCB2RIGHT",
        "PCB_3 Front": "PCB3FRONT",
        "PCB_4 Left": "PCB4LEFT",
        "AF Breite": "AFBreite",
        "AF Höhe": "AFHoehe",
        "AF Tiefe": "AFTiefe",
        "AI angelegt": "AIangelegt",
        "AI Zeitstempel": "AIZeitstempel",
        "Cobot angelegt": "CobotAngelegt",
        "Cobot Zeitstempel": "CobotZeitstempel",
        "PosPCB_0": "POSPCB0",
        "PosPCB_1": "POSPCB1",
        "PosPCB_2": "POSPCB2",
        "PosPCB_3": "POSPCB3",
        "PosPCB_4": "POSPCB4",
    }
    
    @classmethod
    def get_all_fields(cls) -> list:
        """Gibt alle Felder in der korrekten Reihenfolge zurück"""
        return (cls.BASIC_FIELDS + cls.DIMENSION_FIELDS +
                cls.PCB_FIELDS + cls.AF_FIELDS + cls.EXTRA_FIELDS +
                cls.POSITION_FIELDS)

    @classmethod
    def get_field_code(cls, field: str) -> str:
        """Liefert die Kurzbezeichnung eines Felds.

        Falls keine explizite Abkürzung vorhanden ist, wird eine generische
        Variante (Großbuchstaben ohne Sonderzeichen) zurückgegeben.
        """
        return cls.FIELD_CODES.get(field, re.sub(r"\W+", "", field).upper())
    
    # LIMA-Kommandos
    LIMA_COMMANDS = {
        "autofocus": '<LIMA CMD="Project_SetNode" DIR="Request" PATH="Module Application.Smart Camera.Optic Control.Auto Focus" VALUE="1" />',
        "get_focus": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Optic Control.Focus Position [mm]" />',
        "trigger": "<T/>",
        "get_code": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Module Spreadsheet.Exports.C1" />',
        "get_tcp_pose": 'get_actual_tcp_pose()',
        "af_width": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Width" />',
        "af_height": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Height" />',
        "af_depth": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Depth" />',
        "af_origin_x": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Origin.X" />',
        "af_origin_y": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Origin.Y" />',
        "af_origin_z": '<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Smart Camera.Auto Focus Box.Origin.Z" />'
    }
    
    # Timeout-Einstellungen
    SOCKET_TIMEOUT = 3.0
    LISTENER_TIMEOUT = 1.0
    
    # Logging-Konfiguration
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = 'INFO'
