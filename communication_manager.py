"""
Communication Manager - Korrigierte Version
Behebt den Syntaxfehler in Zeile 255
"""
import socket
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable, Tuple, List
import json

from exceptions import CommunicationError, ValidationError
from validation import Validator


class LimaClient:
    """Client für LIMA-Kommunikation"""
    
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def test_connection(self) -> bool:
        """Testet die Verbindung zu LIMA"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                result = sock.connect_ex((self.host, self.port))
                return result == 0
        
        except Exception as e:
            self.logger.error(f"Verbindungstest fehlgeschlagen: {e}")
            return False
    
    def send_command(self, command: str) -> Optional[str]:
        """Sendet Kommando an LIMA und wartet auf Antwort"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                
                # Kommando senden
                sock.send(command.encode('utf-8'))
                
                # Antwort empfangen
                response = sock.recv(4096).decode('utf-8').strip()
                self.logger.debug(f"LIMA Kommando: {command} -> Antwort: {response}")
                
                return response
        
        except socket.timeout:
            raise CommunicationError(f"Timeout beim Senden des Kommandos: {command}")
        except socket.error as e:
            raise CommunicationError(f"Socket-Fehler bei Kommando {command}: {e}")
        except Exception as e:
            raise CommunicationError(f"Unerwarteter Fehler bei Kommando {command}: {e}")
    
    def get_product_info(self, product_number: str) -> Optional[Dict[str, Any]]:
        """Holt Produktinformationen von LIMA"""
        try:
            command = f"GET_PRODUCT_INFO:{product_number}"
            response = self.send_command(command)
            
            if response and response.startswith("PRODUCT_INFO:"):
                # JSON-Daten aus Response extrahieren
                json_data = response[13:]  # "PRODUCT_INFO:" entfernen
                return json.loads(json_data)
            
            return None
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Fehler beim Parsen der Produktinfo: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Produktinfo: {e}")
            return None
    
    def close(self):
        """Schließt die Verbindung"""
        # Hier könnte persistente Verbindung geschlossen werden
        pass


class RobotCommunicator:
    """Kommunikation mit dem Robot über LIMA"""
    
    def __init__(self, lima_client: LimaClient):
        self.lima_client = lima_client
        self.logger = logging.getLogger(__name__)
    
    def start_autofocus(self) -> bool:
        """Startet den Autofokus"""
        try:
            response = self.lima_client.send_command("START_AUTOFOCUS")
            return response == "AUTOFOCUS_STARTED"
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Starten des Autofokus: {e}")
    
    def send_trigger(self) -> bool:
        """Sendet Trigger-Signal"""
        try:
            response = self.lima_client.send_command("SEND_TRIGGER")
            return response == "TRIGGER_SENT"
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Senden des Triggers: {e}")
    
    def get_focus_value(self) -> Optional[str]:
        """Holt aktuellen Fokuswert"""
        try:
            response = self.lima_client.send_command("GET_FOCUS_VALUE")
            
            if response and response.startswith("FOCUS_VALUE:"):
                return response[12:]  # "FOCUS_VALUE:" entfernen
            
            return None
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen des Fokuswerts: {e}")
    
    def get_af_value(self, field: str) -> Optional[str]:
        """Holt spezifischen AF-Wert"""
        try:
            # Feld validieren
            if not Validator.validate_af_field(field):
                raise ValueError(f"Ungültiges AF-Feld: {field}")
            
            command = f"GET_AF_VALUE:{field}"
            response = self.lima_client.send_command(command)
            
            if response and response.startswith("AF_VALUE:"):
                return response[9:]  # "AF_VALUE:" entfernen
            
            return None
        
        except CommunicationError:
            raise
        except ValueError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen des AF-Werts {field}: {e}")
    
    def get_af_origin_xyz(self) -> Optional[Tuple[float, float, float]]:
        """Holt AF-Ursprung XYZ-Koordinaten"""
        try:
            response = self.lima_client.send_command("GET_AF_ORIGIN_XYZ")
            
            if response and response.startswith("AF_ORIGIN_XYZ:"):
                coords_str = response[14:]  # "AF_ORIGIN_XYZ:" entfernen
                x, y, z = map(float, coords_str.split(","))
                return (x, y, z)
            
            return None
        
        except ValueError as e:
            raise CommunicationError(f"Ungültiges XYZ-Format: {e}")
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen der AF-Ursprung XYZ: {e}")
    
    def get_current_position(self) -> Optional[Tuple[float, float, float]]:
        """Holt aktuelle Roboter-Position"""
        try:
            response = self.lima_client.send_command("GET_CURRENT_POSITION")
            
            if response and response.startswith("CURRENT_POSITION:"):
                pos_str = response[17:]  # "CURRENT_POSITION:" entfernen
                x, y, z = map(float, pos_str.split(","))
                return (x, y, z)
            
            return None
        
        except ValueError as e:
            raise CommunicationError(f"Ungültiges Positionsformat: {e}")
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen der Position: {e}")


class ListenerMode:
    """Listener für eingehende Nachrichten von externen Systemen"""
    
    def __init__(self, listen_port: int, send_ip: str, send_port: int):
        self.listen_port = listen_port
        self.send_ip = send_ip
        self.send_port = send_port
        
        self.server_socket: Optional[socket.socket] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.running = False
        self.message_handler: Optional[Callable[[str, str], None]] = None
        
        self.logger = logging.getLogger(__name__)
    
    def start(self, message_handler: Callable[[str, str], None]) -> bool:
        """Startet den Listener"""
        if self.running:
            return False
        
        try:
            self.message_handler = message_handler
            
            # Server-Socket erstellen
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("", self.listen_port))
            self.server_socket.listen(5)
            
            # Listener-Thread starten
            self.running = True
            self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
            self.listener_thread.start()
            
            self.logger.info(f"Listener gestartet auf Port {self.listen_port}")
            return True
        
        except Exception as e:
            self.logger.error(f"Fehler beim Starten des Listeners: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stoppt den Listener"""
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0)
        
        self.listener_thread = None
        self.logger.info("Listener gestoppt")
    
    def is_running(self) -> bool:
        """Prüft ob Listener läuft"""
        return self.running and self.listener_thread and self.listener_thread.is_alive()
    
    def _listener_loop(self):
        """Haupt-Listener-Schleife"""
        while self.running and self.server_socket:
            try:
                # Auf Verbindung warten (mit Timeout)
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()
                
                # Client-Handler starten
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
            
            except socket.timeout:
                continue  # Timeout ist normal, einfach weitermachen
            except Exception as e:
                if self.running:  # Nur loggen wenn wir noch laufen sollten
                    self.logger.error(f"Fehler im Listener-Loop: {e}")
                break
    
    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Behandelt einzelne Client-Verbindung"""
        try:
            sender_ip = address[0]
            self.logger.info(f"Client verbunden: {sender_ip}")
            
            # Nachricht empfangen - HIER WAR DER FEHLER: .strip() statt .strip
            data = client_socket.recv(4096).decode("utf-8").strip()
            
            if data and self.message_handler:
                self.message_handler(data, sender_ip)
                
                # Bestätigung senden
                response = "MESSAGE_RECEIVED"
                client_socket.send(response.encode("utf-8"))
        
        except Exception as e:
            self.logger.error(f"Fehler beim Behandeln des Clients {address}: {e}")
        
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
    
    def send_message(self, message: str) -> bool:
        """Sendet Nachricht an konfigurierte Ziel-IP"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5.0)
                sock.connect((self.send_ip, self.send_port))
                sock.send(message.encode("utf-8"))
                
                # Bestätigung empfangen
                response = sock.recv(1024).decode("utf-8").strip()
                return response == "MESSAGE_RECEIVED"
        
        except Exception as e:
            self.logger.error(f"Fehler beim Senden der Nachricht: {e}")
            return False


class CobotCommunicator:
    """Direkte Kommunikation mit dem Cobot (falls erforderlich)"""
    
    def __init__(self, cobot_ip: str, cobot_port: int, timeout: float = 10.0):
        self.cobot_ip = cobot_ip
        self.cobot_port = cobot_port
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    def send_position_data(self, positions: Dict[str, Any]) -> bool:
        """Sendet Positionsdaten an den Cobot"""
        try:
            # Positionsdaten in JSON umwandeln
            data = json.dumps(positions)
            message = f"POSITION_DATA:{data}"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.cobot_ip, self.cobot_port))
                sock.send(message.encode("utf-8"))
                
                # Bestätigung empfangen
                response = sock.recv(1024).decode("utf-8").strip()
                return response == "POSITIONS_RECEIVED"
        
        except Exception as e:
            self.logger.error(f"Fehler beim Senden der Positionsdaten: {e}")
            return False
    
    def send_program_start(self, program_name: str) -> bool:
        """Startet ein Cobot-Programm"""
        try:
            message = f"START_PROGRAM:{program_name}"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.cobot_ip, self.cobot_port))
                sock.send(message.encode("utf-8"))
                
                response = sock.recv(1024).decode("utf-8").strip()
                return response == "PROGRAM_STARTED"
        
        except Exception as e:
            self.logger.error(f"Fehler beim Starten des Cobot-Programms: {e}")
            return False
    
    def get_cobot_status(self) -> Optional[str]:
        """Holt aktuellen Cobot-Status"""
        try:
            message = "GET_STATUS"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.cobot_ip, self.cobot_port))
                sock.send(message.encode("utf-8"))
                
                response = sock.recv(1024).decode("utf-8").strip()
                if response.startswith("STATUS:"):
                    return response[7:]  # "STATUS:" entfernen
                
                return None
        
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen des Cobot-Status: {e}")
            return None