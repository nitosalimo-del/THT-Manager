"""
Validierungslogik für den THT-Produktmanager
"""
import socket
import re
from typing import Any, Optional

from exceptions import ValidationError
from config import Config

class Validator:
    """Zentrale Validierungsklasse"""
    
    @staticmethod
    def validate_ip(ip: str) -> bool:
        """Validiert IP-Adresse"""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False
    
    @staticmethod
    def validate_port(port: Any) -> bool:
        """Validiert Port-Nummer"""
        try:
            port_int = int(port)
            return 1 <= port_int <= 65535
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_laufnummer(nummer: str) -> bool:
        """Validiert Laufende Nummer"""
        if not nummer or not isinstance(nummer, str):
            return False
        return nummer.isdigit() and int(nummer) > 0
    
    @staticmethod
    def validate_produktnummer(nummer: str) -> bool:
        """Validiert Produktnummer Format"""
        if not nummer:
            return False
        # Beispiel-Pattern: WU1234567
        pattern = r'^WU\d{7,}$'
        return bool(re.match(pattern, nummer))
    
    @staticmethod
    def validate_required_field(value: str, field_name: str) -> None:
        """Validiert Pflichtfelder und wirft Exception bei Fehler"""
        if not value or not value.strip():
            raise ValidationError(f"Feld '{field_name}' ist erforderlich")
    
    @staticmethod
    def validate_numeric_field(value: str, field_name: str) -> float:
        """Validiert numerische Felder"""
        try:
            return float(value) if value else 0.0
        except ValueError:
            raise ValidationError(f"Feld '{field_name}' muss eine Zahl sein")

    @staticmethod
    def validate_af_field(field: str) -> bool:
        """Validiert, ob ein AF-Feld zulässig ist"""
        return isinstance(field, str) and field in Config.AF_FIELDS
    
    @staticmethod
    def validate_password(password: str, expected: str) -> bool:
        """Validiert Passwort"""
        return password == expected
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Bereinigt String-Eingaben"""
        if not value:
            return ""
        return value.strip()
    
    @classmethod
    def validate_lima_config(cls, config: dict) -> None:
        """Validiert LIMA-Konfiguration"""
        required_keys = ['ip', 'port', 'listener_port', 'send_ip', 'send_port']
        
        for key in required_keys:
            if key not in config:
                raise ValidationError(f"LIMA-Konfiguration fehlt: {key}")
        
        if not cls.validate_ip(config['ip']):
            raise ValidationError("Ungültige LIMA IP-Adresse")
        
        if not cls.validate_ip(config['send_ip']):
            raise ValidationError("Ungültige Send IP-Adresse")
        
        for port_key in ['port', 'listener_port', 'send_port']:
            if not cls.validate_port(config[port_key]):
                raise ValidationError(f"Ungültiger Port: {port_key}")
    
    @staticmethod
    def extract_wu_nummer(text: str) -> Optional[str]:
        """Extrahiert WU-Nummer aus Text"""
        if not text:
            return None
        match = re.search(r'WU\d{7,}', text)
        return match.group(0) if match else None
