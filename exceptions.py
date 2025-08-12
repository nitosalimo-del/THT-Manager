"""
Benutzerdefinierte Exceptions für den THT-Produktmanager
"""

class ProduktManagerError(Exception):
    """Basis-Exception für alle Produktmanager-Fehler"""
    pass

class DatabaseError(ProduktManagerError):
    """Exception für Datenbankfehler"""
    pass

class CommunicationError(ProduktManagerError):
    """Exception für Kommunikationsfehler (LIMA/Robot)"""
    pass

class ValidationError(ProduktManagerError):
    """Exception für Validierungsfehler"""
    pass

class ConfigurationError(ProduktManagerError):
    """Exception für Konfigurationsfehler"""
    pass

class AuthenticationError(ProduktManagerError):
    """Exception für Authentifizierungsfehler"""
    pass