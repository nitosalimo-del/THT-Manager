"""
Communication Manager - Verbesserte Version mit korrektem LIMA-Protokoll
"""
import socket
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable, Tuple, List
import json
import xml.etree.ElementTree as ET
from datetime import datetime

from exceptions import CommunicationError, ValidationError
from validation import Validator
from config import Config


class LimaClient:
    """Client für LIMA-Kommunikation mit korrektem XML-Protokoll"""
    
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
        """Sendet LIMA-Kommando und wartet auf Antwort"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))

                # LIMA-Kommando mit Newline senden
                full_command = command + "\n"
                sock.send(full_command.encode("utf-8"))

                # Antwort empfangen (bis zu 4KB)
                response = sock.recv(4096).decode("utf-8").strip()
                self.logger.debug(
                    "LIMA Kommando: %s -> Antwort: %s", command, response
                )

                return response

        except socket.timeout:
            raise CommunicationError(
                f"Timeout beim Senden des Kommandos: {command}"
            )
        except socket.error as e:
            raise CommunicationError(
                f"Socket-Fehler bei Kommando {command}: {e}"
            )
        except Exception as e:
            raise CommunicationError(
                f"Unerwarteter Fehler bei Kommando {command}: {e}"
            )
    
    def parse_lima_response(self, response: str) -> Dict[str, str]:
        """Parst LIMA XML-Response"""
        try:
            # XML parsen
            root = ET.fromstring(response)
            
            # Alle Attribute des LIMA-Tags extrahieren
            attributes = dict(root.attrib)
            
            # Text-Inhalt falls vorhanden
            if root.text:
                attributes['TEXT'] = root.text.strip()
            
            return attributes
        
        except ET.ParseError as e:
            # Logge die komplette fehlerhafte XML-Antwort zur Analyse
            self.logger.error(f"XML-Parse-Fehler: {e} - Antwort: {response}")
            return {}
        except Exception as e:
            self.logger.error(f"Fehler beim Parsen der LIMA-Response: {e}")
            return {}
    
    def get_product_info(self, product_number: str) -> Optional[Dict[str, Any]]:
        """Holt Produktinformationen von LIMA"""
        try:
            # Beispiel-Kommando für Produktinfo (anzupassen je nach LIMA-Setup)
            command = f'<LIMA CMD="Project_GetNode" DIR="Request" PATH="Module Application.Product.{product_number}" />'
            response = self.send_command(command)
            
            if response:
                parsed = self.parse_lima_response(response)
                if parsed.get('DIR') == 'ReplyOk' and 'VALUE' in parsed:
                    # JSON-Daten aus VALUE extrahieren falls vorhanden
                    try:
                        return json.loads(parsed['VALUE'])
                    except json.JSONDecodeError:
                        # Falls kein JSON, als String-Wert zurückgeben
                        return {'info': parsed['VALUE']}
            
            return None
        
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Produktinfo: {e}")
            return None
    
    def close(self):
        """Schließt die Verbindung"""
        pass


class RobotCommunicator:
    """Verbesserte Robot-Kommunikation mit korrekten LIMA-Kommandos"""
    
    def __init__(self, lima_client: LimaClient):
        self.lima_client = lima_client
        self.logger = logging.getLogger(__name__)
    
    def start_autofocus(self) -> bool:
        """Startet den Autofokus mit korrektem LIMA-Kommando"""
        try:
            # Autofokus auf "Once" setzen (Wert 1)
            command = Config.LIMA_COMMANDS["autofocus"]
            response = self.lima_client.send_command(command)
            
            if response:
                parsed = self.lima_client.parse_lima_response(response)
                return parsed.get('DIR') == 'ReplyOk'
            
            return False
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Starten des Autofokus: {e}")
    
    def send_trigger(self) -> bool:
        """Sendet Trigger-Signal"""
        try:
            response = self.lima_client.send_command("<T/>")
            return response == "<TOk/>"
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Senden des Triggers: {e}")
    
    def get_focus_value(self) -> Optional[str]:
        """Holt aktuellen Fokuswert"""
        try:
            command = Config.LIMA_COMMANDS["get_focus"]
            response = self.lima_client.send_command(command)
            
            if response:
                parsed = self.lima_client.parse_lima_response(response)
                if parsed.get('DIR') == 'ReplyOk' and 'VALUE' in parsed:
                    return parsed['VALUE']
            
            return None
        
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen des Fokuswerts: {e}")
    
    def get_af_value(self, field: str) -> Optional[str]:
        """Holt spezifischen AF-Wert mit korrekten LIMA-Kommandos"""
        try:
            # Feld validieren
            if not Validator.validate_af_field(field):
                raise ValueError(f"Ungültiges AF-Feld: {field}")
            
            # Mapping von Feldnamen zu LIMA-Kommandos
            command_mapping = {
                "AF Breite": Config.LIMA_COMMANDS["af_width"],
                "AF Höhe": Config.LIMA_COMMANDS["af_height"], 
                "AF Tiefe": Config.LIMA_COMMANDS["af_depth"]
            }
            
            command = command_mapping.get(field)
            if not command:
                raise ValueError(f"Kein LIMA-Kommando für Feld: {field}")
            
            response = self.lima_client.send_command(command)
            
            if response:
                parsed = self.lima_client.parse_lima_response(response)
                if parsed.get('DIR') == 'ReplyOk' and 'VALUE' in parsed:
                    return parsed['VALUE']
                elif parsed.get('DIR') == 'ReplyError':
                    error_msg = parsed.get('INFO', 'Unbekannter LIMA-Fehler')
                    self.logger.error(f"LIMA-Fehler für {field}: {error_msg}")
                    raise CommunicationError(f"LIMA-Fehler: {error_msg}")
            
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
            # X, Y, Z einzeln abrufen
            x_cmd = Config.LIMA_COMMANDS["af_origin_x"]
            y_cmd = Config.LIMA_COMMANDS["af_origin_y"]
            z_cmd = Config.LIMA_COMMANDS["af_origin_z"]
            
            x_response = self.lima_client.send_command(x_cmd)
            y_response = self.lima_client.send_command(y_cmd)
            z_response = self.lima_client.send_command(z_cmd)
            
            x_parsed = self.lima_client.parse_lima_response(x_response) if x_response else {}
            y_parsed = self.lima_client.parse_lima_response(y_response) if y_response else {}
            z_parsed = self.lima_client.parse_lima_response(z_response) if z_response else {}
            
            # Werte extrahieren
            x_val = x_parsed.get('VALUE')
            y_val = y_parsed.get('VALUE')
            z_val = z_parsed.get('VALUE')
            
            if all([x_val, y_val, z_val]):
                return (float(x_val), float(y_val), float(z_val))
            
            return None
        
        except ValueError as e:
            raise CommunicationError(f"Ungültiges XYZ-Format: {e}")
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen der AF-Ursprung XYZ: {e}")
    
    def get_current_position(self) -> Optional[Tuple[float, float, float]]:
        """Holt aktuelle TCP-Position vom Robot"""
        try:
            command = Config.LIMA_COMMANDS["get_tcp_pose"]
            response = self.lima_client.send_command(command)
            
            if response:
                parsed = self.lima_client.parse_lima_response(response)
                if parsed.get('DIR') == 'ReplyOk' and 'VALUE' in parsed:
                    # TCP Pose Format: "X,Y,Z,RX,RY,RZ" - nur X,Y,Z nehmen
                    pose_str = parsed['VALUE']
                    pose_values = pose_str.split(',')
                    if len(pose_values) >= 3:
                        x, y, z = map(float, pose_values[:3])
                        return (x, y, z)
            
            return None
        
        except ValueError as e:
            raise CommunicationError(f"Ungültiges Positionsformat: {e}")
        except CommunicationError:
            raise
        except Exception as e:
            raise CommunicationError(f"Fehler beim Abrufen der Position: {e}")


class ListenerMode:
    """Erweiterte Listener-Klasse mit Nachrichtenverfolgung"""

    def __init__(
        self,
        send_ip: str,
        send_port: int,
        *,
        camera_ip: Optional[str] = None,
        camera_port: int = 34000,
    ):
        # Lokaler Listener-Port ist fest auf 34000 gesetzt
        self.listen_port = 34000
        self.send_ip = send_ip
        self.send_port = send_port
        self.camera_ip = camera_ip
        self.camera_port = camera_port

        self.server_socket: Optional[socket.socket] = None
        self.listener_thread: Optional[threading.Thread] = None
        self.client_thread: Optional[threading.Thread] = None
        self.client_socket: Optional[socket.socket] = None
        self.running = False

        # Handler für eingehende Nachrichten und optionale Log-Events
        self.message_handler: Optional[Callable[[str, str], None]] = None
        self.log_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Internes Nachrichten-Log
        self.message_log: List[Dict[str, Any]] = []

        self.logger = logging.getLogger(__name__)

    def start(
        self,
        message_handler: Callable[[str, str], None],
        log_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> bool:
        """Startet den Listener"""
        if self.running:
            return False

        try:
            self.message_handler = message_handler
            self.log_callback = log_callback
            
            # Server-Socket erstellen
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("", self.listen_port))
            self.server_socket.listen(5)

            # Listener-Thread starten
            self.running = True
            self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
            self.listener_thread.start()

            # Optional Kamera-Client starten
            if self.camera_ip:
                self.client_thread = threading.Thread(target=self._client_loop, daemon=True)
                self.client_thread.start()

            self.logger.info(f"Listener gestartet auf Port {self.listen_port}")
            self._log_event(
                "LISTENER_STARTED",
                f"Listener auf Port {self.listen_port} gestartet",
                "SYSTEM",
            )
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

        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0)

        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=2.0)

        self.listener_thread = None
        self.client_thread = None

        self.logger.info("Listener gestoppt")
        self._log_event("LISTENER_STOPPED", "Listener gestoppt", "SYSTEM")
    
    def is_running(self) -> bool:
        """Prüft ob Listener läuft"""
        return bool(self.running and self.listener_thread and self.listener_thread.is_alive())

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
                continue  # Timeout ist normal
            except Exception as e:
                if self.running:  # Nur loggen wenn wir noch laufen sollten
                    self.logger.error(f"Fehler im Listener-Loop: {e}")
                    self._log_event(
                        "SERVER_ERROR", f"Listener-Loop-Fehler: {e}", "SYSTEM"
                    )
                break

    def _client_loop(self):
        """Verbindet sich als TCP-Client mit der Kamera und empfängt Nachrichten"""
        backoff = 1
        while self.running and self.camera_ip:
            try:
                self.client_socket = socket.create_connection(
                    (self.camera_ip, self.camera_port), timeout=5
                )
                sock = self.client_socket
                sock.settimeout(1.0)
                self.logger.info(
                    f"Kamera verbunden: {self.camera_ip}:{self.camera_port}"
                )
                self._log_event(
                    "CLIENT_CONNECTED",
                    f"Kamera verbunden: {self.camera_ip}:{self.camera_port}",
                    self.camera_ip,
                )
                backoff = 1
                buffer = ""

                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            raise ConnectionError("Verbindung zur Kamera getrennt")
                        buffer += data.decode("utf-8", errors="ignore")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if line:
                                self._log_event(
                                    "MESSAGE_RECEIVED", line, self.camera_ip
                                )
                                if self.message_handler:
                                    self.message_handler(line, self.camera_ip)
                    except socket.timeout:
                        continue

            except Exception as e:
                if self.running:
                    self.logger.warning(
                        f"Kamera-Client-Verbindung fehlgeschlagen: {e}"
                    )
                    self._log_event(
                        "CLIENT_ERROR",
                        f"Kamera-Verbindung: {e}",
                        self.camera_ip or "",
                    )
                if not self.running:
                    break
                time.sleep(backoff)
                backoff = min(backoff * 2, 10)
            finally:
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except Exception:
                        pass
                self.client_socket = None
    
    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Behandelt einzelne Client-Verbindung"""
        try:
            sender_ip = address[0]
            self.logger.info(f"Client verbunden: {sender_ip}")
            self._log_event("CLIENT_CONNECTED", f"Verbunden mit {sender_ip}", sender_ip)

            # Nachricht empfangen
            data = client_socket.recv(4096).decode("utf-8", errors="ignore").strip()
            self._log_event("MESSAGE_RECEIVED", data, sender_ip)

            if data and self.message_handler:
                self.message_handler(data, sender_ip)

                # Bestätigung senden
                response = "MESSAGE_RECEIVED"
                client_socket.send(response.encode("utf-8"))
        
        except Exception as e:
            self.logger.error(f"Fehler beim Behandeln des Clients {address}: {e}")
            self._log_event(
                "SERVER_ERROR", f"Client-Handler-Fehler: {e}", sender_ip
            )
        
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

                # Ausgehende Nachricht loggen (einmalig)
                self._log_event("MESSAGE_SENT", message, self.send_ip)

                # Bestätigung empfangen
                response = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                return response == "MESSAGE_RECEIVED"

        except Exception as e:
            self.logger.error(f"Fehler beim Senden der Nachricht: {e}")
            self._log_event(
                "CLIENT_ERROR", f"Senden fehlgeschlagen: {e}", self.send_ip
            )
            return False
    
    def _log_event(self, event_type: str, message: str, source: str):
        """Loggt ein Event mit Timestamp"""
        event = {
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],  # Mit Millisekunden
            'type': event_type,
            'message': message,
            'source': source
        }
        
        self.message_log.append(event)
        
        # Log-Callback aufrufen falls gesetzt
        if self.log_callback:
            try:
                self.log_callback(event)
            except Exception as e:
                self.logger.error(f"Fehler im Log-Callback: {e}")
        
        # Log-Größe begrenzen (letzte 100 Einträge behalten)
        if len(self.message_log) > 100:
            self.message_log = self.message_log[-100:]
    
    def get_message_log(self) -> List[Dict[str, Any]]:
        """Gibt das aktuelle Message-Log zurück"""
        return self.message_log.copy()
    
    def clear_message_log(self):
        """Leert das Message-Log"""
        self.message_log.clear()


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
