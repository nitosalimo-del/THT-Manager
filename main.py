"""
THT-Produktmanager Version 2.0 (Optimiert)
Hauptdatei mit verbesserter Architektur
"""
import customtkinter as ctk
import tkinter as tk
import logging
import json
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

# Import der optimierten Module
from config import Config
from exceptions import *
from validation import Validator
from database_manager import DatabaseManager
from communication_manager import LimaClient, RobotCommunicator, ListenerMode
from ui_manager import FormManager, SidebarManager, StatusManager, MessageHandler
from thread_manager import ThreadManager

# Zusätzliche Imports für die Hauptdatei
try:
    from enhanced_listener_ui import ListenerLogWindow
except ImportError as e:
    print(f"Warnung: enhanced_listener_ui konnte nicht importiert werden: {e}")
    ListenerLogWindow = None

# Logging konfigurieren
def setup_logging():
    """Konfiguriert das Logging-System"""
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(f'logs/{Config.LOG_FILE}'),
            logging.StreamHandler()
        ]
    )
    
    # Weniger Logging für externe Bibliotheken
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

# Hauptanwendungsklasse
class ProduktManagerApp(ctk.CTk):
    """Hauptanwendung für den THT-Produktmanager"""
    
    def __init__(self):
        super().__init__()
        
        # Logging initialisieren
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("THT-Produktmanager wird gestartet...")
        
        # Core-Komponenten initialisieren
        self.db_manager = DatabaseManager()
        self.thread_manager = ThreadManager()
        self.message_handler = MessageHandler()
        
        # UI-Konfiguration
        self._setup_ui_theme()
        self._setup_main_window()
        
        # Anwendungsstatus
        self.admin_mode = False
        self.selected_index: Optional[int] = None
        self.selected_product: Optional[Dict[str, Any]] = None
        self.products: List[Any] = []
        
        # LIMA/Robot-Konfiguration
        self.lima_config = self._load_lima_config()
        self.lima_client: Optional[LimaClient] = None
        self.robot_communicator: Optional[RobotCommunicator] = None
        
        # Listener Mode
        self.listener_mode: Optional[ListenerMode] = None
        self.listener_popup: Optional[ctk.CTkToplevel] = None
        self.listener_log_window: Optional[ctk.CTkToplevel] = None
        self.listener_start_time: Optional[float] = None
        
        # UI-Manager initialisieren
        self._setup_ui_managers()
        
        # Daten laden
        self._load_initial_data()

        # Verbindungen testen
        # Verzögerung einbauen, damit die GUI zuerst erscheint
        self.after(100, self._test_connections)
        
        self.logger.info("THT-Produktmanager erfolgreich gestartet")
    
    def _setup_ui_theme(self):
        """Konfiguriert UI-Theme"""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
    
    def _setup_main_window(self):
        """Konfiguriert Hauptfenster"""
        self.title("THT-Produktmanager Version 2.0 (Optimiert)")
        
        # Fenster zentrieren
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = Config.WINDOW_SIZE
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Cleanup beim Schließen
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_ui_managers(self):
        """Initialisiert UI-Manager"""
        # Sidebar
        self.sidebar_manager = SidebarManager(self)
        self._connect_sidebar_events()
        
        # Hauptformular
        self.form_manager = FormManager(self, Config.get_all_fields())
        self._connect_form_events()
        
        # Status-Panel
        self.status_manager = StatusManager(self)
        self.status_panel = self.status_manager.create_status_panel(self)
        
        # Steuerungsbuttons erstellen
        self._create_control_buttons()
        
        # LIMA-Konfigurationspanel
        self._create_lima_config_panel()
    
    def _connect_sidebar_events(self):
        """Verbindet Sidebar-Events"""
        sidebar_widgets = self.sidebar_manager.widgets
        
        # Admin-Login
        sidebar_widgets["login_btn"].configure(command=self._admin_login)
        sidebar_widgets["logout_btn"].configure(command=self._admin_logout)
        sidebar_widgets["new_btn"].configure(command=self._new_product)
        sidebar_widgets["delete_btn"].configure(command=self._delete_product)
        
        # Listener-Buttons
        sidebar_widgets["listener_start_btn"].configure(command=self._start_listener_mode)
        sidebar_widgets["listener_stop_btn"].configure(command=self._stop_listener_mode)
    
    def _connect_form_events(self):
        """Verbindet Formular-Events"""
        form_widgets = self.form_manager.widgets
        
        # Button-Events für verschiedene Funktionen
        if "af_origin_button" in form_widgets:
            form_widgets["af_origin_button"].configure(command=self._get_af_origin_xyz)
        
        if "af_all_button" in form_widgets:
            form_widgets["af_all_button"].configure(command=self._get_all_af_values)
        
        # PCB-Buttons
        for field in Config.PCB_FIELDS:
            btn_key = f"{field}_button"
            if btn_key in form_widgets:
                form_widgets[btn_key].configure(
                    command=lambda f=field: self._autofocus_and_get_focus_value(f)
                )
        
        # AF-Buttons
        for field in Config.AF_FIELDS:
            btn_key = f"{field}_button"
            if btn_key in form_widgets:
                form_widgets[btn_key].configure(
                    command=lambda f=field: self._get_af_value(f)
                )
        
        # Position-Buttons
        for field in Config.POSITION_FIELDS:
            btn_key = f"{field}_button"
            if btn_key in form_widgets:
                form_widgets[btn_key].configure(
                    command=lambda f=field: self._handle_position_request(f)
                )
    
    def _create_control_buttons(self):
        """Erstellt Steuerungsbuttons"""
        content_frame = self.form_manager.scrollable_frame
        button_row = len(Config.get_all_fields()) + 10  # Nach allen Formularfeldern
        
        # Speichern-Button
        self.save_btn = ctk.CTkButton(
            content_frame, 
            text="Speichern", 
            command=self._save_product,
            state="disabled"
        )
        self.save_btn.grid(row=button_row, column=1, pady=10)
        
        # Autofokus-Button
        self.autofocus_btn = ctk.CTkButton(
            content_frame,
            text="Autofokus starten",
            command=self._start_autofocus
        )
        self.autofocus_btn.grid(row=button_row, column=0, padx=10)
        
        # Trigger-Button
        self.trigger_btn = ctk.CTkButton(
            content_frame,
            text="Trigger auslösen", 
            command=self._send_trigger
        )
        self.trigger_btn.grid(row=button_row, column=2, padx=10)
        
        # LIMA-Config-Button
        self.config_btn = ctk.CTkButton(
            content_frame,
            text="LIMA-Einstellungen",
            command=self._toggle_lima_panel
        )
        self.config_btn.grid(row=button_row, column=3, padx=10)
        
        # Produktnummer-Abrufen-Button
        if "Produktnummer" in self.form_manager.entries:
            get_info_btn = ctk.CTkButton(
                content_frame,
                text="Abrufen",
                width=80,
                height=26,
                font=("Arial", 10),
                command=self._get_lima_info
            )
            # Position neben Produktnummer-Feld finden
            for i, field in enumerate(Config.BASIC_FIELDS):
                if field == "Produktnummer":
                    get_info_btn.grid(row=i + 2, column=2, padx=10)  # +2 wegen Header
                    break
    
    def _create_lima_config_panel(self):
        """Erstellt LIMA-Konfigurationspanel"""
        content_frame = self.form_manager.scrollable_frame
        config_row = len(Config.get_all_fields()) + 12
        
        self.lima_panel = ctk.CTkFrame(content_frame)
        self.lima_panel.grid(row=config_row, column=0, columnspan=4, sticky="w", padx=5, pady=10)
        self.lima_panel.grid_remove()  # Initial versteckt
        
        # IP-Eingabe
        self.ip_entry = ctk.CTkEntry(self.lima_panel, width=200)
        self.ip_entry.insert(0, self.lima_config.get("ip", Config.DEFAULT_LIMA_CONFIG["ip"]))
        self.ip_entry.grid(row=0, column=0, pady=2, padx=5)
        
        ip_label = ctk.CTkLabel(self.lima_panel, text="LIMA IP-Adresse")
        ip_label.grid(row=1, column=0, padx=5)
        
        # Port-Eingabe
        self.port_entry = ctk.CTkEntry(self.lima_panel, width=100)
        self.port_entry.insert(0, str(self.lima_config.get("port", Config.DEFAULT_LIMA_CONFIG["port"])))
        self.port_entry.grid(row=0, column=1, pady=2, padx=5)
        
        port_label = ctk.CTkLabel(self.lima_panel, text="LIMA Port")
        port_label.grid(row=1, column=1, padx=5)
        
        # Listener-Port
        self.listener_port_entry = ctk.CTkEntry(self.lima_panel, width=100)
        self.listener_port_entry.insert(0, str(self.lima_config.get("listener_port", Config.DEFAULT_LIMA_CONFIG["listener_port"])))
        self.listener_port_entry.grid(row=0, column=2, pady=2, padx=5)
        
        listener_label = ctk.CTkLabel(self.lima_panel, text="Listener Port")
        listener_label.grid(row=1, column=2, padx=5)
        
        # Send-IP
        self.send_ip_entry = ctk.CTkEntry(self.lima_panel, width=200)
        self.send_ip_entry.insert(0, self.lima_config.get("send_ip", Config.DEFAULT_LIMA_CONFIG["send_ip"]))
        self.send_ip_entry.grid(row=2, column=0, pady=2, padx=5)
        
        send_ip_label = ctk.CTkLabel(self.lima_panel, text="Cobot IP (Send)")
        send_ip_label.grid(row=3, column=0, padx=5)
        
        # Send-Port
        self.send_port_entry = ctk.CTkEntry(self.lima_panel, width=100)
        self.send_port_entry.insert(0, str(self.lima_config.get("send_port", Config.DEFAULT_LIMA_CONFIG["send_port"])))
        self.send_port_entry.grid(row=2, column=1, pady=2, padx=5)
        
        send_port_label = ctk.CTkLabel(self.lima_panel, text="Cobot Port (Send)")
        send_port_label.grid(row=3, column=1, padx=5)
        
        # Buttons
        test_btn = ctk.CTkButton(self.lima_panel, text="Verbindung testen", command=self._test_lima_connection)
        test_btn.grid(row=4, column=0, padx=5, pady=10)
        
        save_config_btn = ctk.CTkButton(self.lima_panel, text="Einstellungen speichern", command=self._save_lima_config)
        save_config_btn.grid(row=4, column=1, padx=5, pady=10)
        
        # Status-Label für LIMA-Panel
        self.lima_status_label = ctk.CTkLabel(self.lima_panel, text="Status: ❔ Unbekannt")
        self.lima_status_label.grid(row=4, column=2, columnspan=2, sticky="w", padx=5)
    
    # === Datenmanagement ===
    
    def _load_initial_data(self):
        """Lädt initiale Daten"""
        try:
            self._populate_sidebar()
        except DatabaseError as e:
            self.message_handler.show_error("Datenbankfehler", str(e))
    
    def _populate_sidebar(self):
        """Füllt die Seitenleiste mit Produkten"""
        try:
            self.products = self.db_manager.fetch_all_products()
            self.sidebar_manager.populate_products(self.products, self._load_product)
        except Exception as e:
            self.logger.error(f"Fehler beim Laden der Produkte: {e}")
            raise DatabaseError(f"Produkte konnten nicht geladen werden: {e}")
    
    def _load_product(self, index: int):
        """Lädt ein Produkt in das Formular"""
        try:
            if 0 <= index < len(self.products):
                self.selected_index = index
                self.selected_product = self.products[index]
                
                # Formulardaten setzen
                product_data = dict(self.selected_product)
                self.form_manager.set_form_data(product_data)
                
                # AF Ursprung spezielle Behandlung
                if "AF Ursprung" in product_data and product_data["AF Ursprung"]:
                    self._set_af_origin_data(product_data["AF Ursprung"])
                
                # Formular entsperren wenn Admin
                if self.admin_mode:
                    self.form_manager.enable_form(True)
                else:
                    self.form_manager.enable_form(False)
                
                self.logger.info(f"Produkt {self.selected_product['Laufende Nummer']} geladen")
        
        except Exception as e:
            self.logger.error(f"Fehler beim Laden des Produkts: {e}")
            self.message_handler.show_error("Fehler", f"Produkt konnte nicht geladen werden: {e}")
    
    def _set_af_origin_data(self, af_origin_str: str):
        """Setzt AF-Ursprung XYZ-Daten"""
        if "af_origin_coords" in self.form_manager.widgets:
            coords = self.form_manager.widgets["af_origin_coords"]
            try:
                x, y, z = af_origin_str.split(",")
                coords["X"].configure(state="normal")
                coords["Y"].configure(state="normal") 
                coords["Z"].configure(state="normal")
                
                coords["X"].delete(0, 'end')
                coords["Y"].delete(0, 'end')
                coords["Z"].delete(0, 'end')
                
                coords["X"].insert(0, x.strip())
                coords["Y"].insert(0, y.strip())
                coords["Z"].insert(0, z.strip())
                
                if not self.admin_mode:
                    coords["X"].configure(state="disabled")
                    coords["Y"].configure(state="disabled")
                    coords["Z"].configure(state="disabled")
            except ValueError:
                self.logger.warning(f"Ungültiges AF-Ursprung-Format: {af_origin_str}")
    
    # === Admin-Funktionen ===
    
    def _admin_login(self):
        """Admin-Login"""
        try:
            password = self.message_handler.get_input("Admin Login", "Passwort eingeben:")
            
            if not password:
                return
            
            if not Validator.validate_password(password, Config.ADMIN_PASSWORD):
                raise AuthenticationError("Falsches Passwort")
            
            self.admin_mode = True
            self.sidebar_manager.set_admin_mode(True)
            self.form_manager.enable_form(True)
            self.save_btn.configure(state="normal")
            
            self.message_handler.show_info("Erfolg", "Admin-Modus aktiviert")
            self.logger.info("Admin-Modus aktiviert")
        
        except AuthenticationError as e:
            self.message_handler.show_error("Authentifizierung fehlgeschlagen", str(e))
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler beim Login: {e}")
            self.message_handler.show_error("Fehler", "Login fehlgeschlagen")
    
    def _admin_logout(self):
        """Admin-Logout"""
        self.admin_mode = False
        self.sidebar_manager.set_admin_mode(False)
        self.form_manager.enable_form(False)
        self.save_btn.configure(state="disabled")
        
        self.message_handler.show_info("Logout", "Admin-Modus deaktiviert")
        self.logger.info("Admin-Modus deaktiviert")
    
    def _new_product(self):
        """Neues Produkt erstellen"""
        if not self.admin_mode:
            self.message_handler.show_warning("Nicht erlaubt", "Bitte zuerst als Admin einloggen")
            return
        
        self.selected_index = None
        self.selected_product = None
        self.form_manager.clear_form()
        self.form_manager.enable_form(True)
        self.save_btn.configure(state="normal")
        
        self.logger.info("Neues Produkt wird erstellt")
    
    def _save_product(self):
        """Speichert das aktuelle Produkt"""
        if not self.admin_mode:
            self.message_handler.show_warning("Nicht erlaubt", "Nur Admins dürfen speichern")
            return
        
        try:
            # Formulardaten holen
            form_data = self.form_manager.get_form_data()
            
            # Validierung
            Validator.validate_required_field(form_data["Laufende Nummer"], "Laufende Nummer")
            
            if not Validator.validate_laufnummer(form_data["Laufende Nummer"]):
                raise ValidationError("Ungültige Laufende Nummer")
            
            laufnummer = int(form_data["Laufende Nummer"])
            
            # Zeitstempel für AI/Cobot setzen (falls implementiert)
            # Hier würden die Checkbox-Zustände abgefragt werden
            
            if self.selected_product:
                # Update
                self.db_manager.update_product(laufnummer, form_data)
                self.message_handler.show_info("Gespeichert", "Produkt wurde aktualisiert")
            else:
                # Insert
                self.db_manager.insert_product(form_data)
                self.message_handler.show_info("Gespeichert", "Neues Produkt wurde erstellt")
            
            # Sidebar aktualisieren
            self._populate_sidebar()
            
            # Formular zurücksetzen
            self._new_product()
        
        except ValidationError as e:
            self.message_handler.show_error("Validierungsfehler", str(e))
        except DatabaseError as e:
            self.message_handler.show_error("Datenbankfehler", str(e))
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler beim Speichern: {e}")
            self.message_handler.show_error("Fehler", "Speichern fehlgeschlagen")
    
    def _delete_product(self):
        """Löscht das aktuelle Produkt"""
        if not self.admin_mode:
            self.message_handler.show_warning("Nicht erlaubt", "Nur Admins dürfen löschen")
            return
        
        if not self.selected_product:
            self.message_handler.show_warning("Hinweis", "Kein Produkt ausgewählt")
            return
        
        if not self.message_handler.ask_yes_no("Löschen bestätigen", "Möchten Sie dieses Produkt wirklich löschen?"):
            return
        
        try:
            laufnummer = self.selected_product["Laufende Nummer"]
            self.db_manager.delete_product(laufnummer)
            
            # UI zurücksetzen
            self.selected_index = None
            self.selected_product = None
            self.form_manager.clear_form()
            self.save_btn.configure(state="disabled")
            
            # Sidebar aktualisieren
            self._populate_sidebar()
            
            self.message_handler.show_info("Gelöscht", "Produkt wurde gelöscht")
        
        except DatabaseError as e:
            self.message_handler.show_error("Datenbankfehler", str(e))
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler beim Löschen: {e}")
            self.message_handler.show_error("Fehler", "Löschen fehlgeschlagen")
    
    # === LIMA/Robot-Kommunikation ===
    
    def _load_lima_config(self) -> Dict[str, Any]:
        """Lädt LIMA-Konfiguration"""
        if os.path.exists(Config.LIMA_CONFIG_FILE):
            try:
                with open(Config.LIMA_CONFIG_FILE, "r") as f:
                    config = json.load(f)
                self.logger.info("LIMA-Konfiguration geladen")
                return config
            except Exception as e:
                self.logger.warning(f"Fehler beim Laden der LIMA-Konfiguration: {e}")
        
        return Config.DEFAULT_LIMA_CONFIG.copy()
    
    def _save_lima_config(self):
        """Speichert LIMA-Konfiguration"""
        try:
            config = {
                "ip": self.ip_entry.get(),
                "port": int(self.port_entry.get()),
                "listener_port": int(self.listener_port_entry.get()),
                "send_ip": self.send_ip_entry.get(),
                "send_port": int(self.send_port_entry.get())
            }
            
            # Validierung
            Validator.validate_lima_config(config)
            
            with open(Config.LIMA_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            
            self.lima_config = config
            self.message_handler.show_info("Gespeichert", "LIMA-Konfiguration wurde gespeichert")
            
            # Verbindung neu testen
            self._update_lima_clients()
            self._test_lima_connection()
        
        except ValidationError as e:
            self.message_handler.show_error("Validierungsfehler", str(e))
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der LIMA-Konfiguration: {e}")
            self.message_handler.show_error("Fehler", "Konfiguration konnte nicht gespeichert werden")
    
    def _update_lima_clients(self):
        """Aktualisiert LIMA-Clients mit neuer Konfiguration"""
        try:
            ip = self.ip_entry.get()
            port = int(self.port_entry.get())
            
            self.lima_client = LimaClient(ip, port)
            self.robot_communicator = RobotCommunicator(self.lima_client)
            
        except Exception as e:
            self.logger.error(f"Fehler beim Aktualisieren der LIMA-Clients: {e}")
            self.lima_client = None
            self.robot_communicator = None
    
    def _test_connections(self):
        """Testet alle Verbindungen beim Start"""
        self._update_lima_clients()
        self._test_lima_connection()
    
    def _test_lima_connection(self):
        """Testet LIMA-Verbindung"""
        if not self.lima_client:
            self._update_lima_clients()
        
        if self.lima_client:
            try:
                connected = self.lima_client.test_connection()
                self.status_manager.update_lima_status(connected)
                
                if hasattr(self, 'lima_status_label'):
                    if connected:
                        self.lima_status_label.configure(text="Status: 🟢 Verbunden", text_color="green")
                    else:
                        self.lima_status_label.configure(text="Status: 🔴 Getrennt", text_color="red")
                
                if connected:
                    self.message_handler.show_info("Verbindung erfolgreich", "LIMA-Verbindung hergestellt")
                else:
                    self.message_handler.show_warning("Verbindung fehlgeschlagen", "LIMA nicht erreichbar")
            
            except CommunicationError as e:
                self.message_handler.show_error("Verbindungsfehler", str(e))
                self.status_manager.update_lima_status(False)
    
    def _toggle_lima_panel(self):
        """Zeigt/Versteckt LIMA-Konfigurationspanel"""
        if self.lima_panel.winfo_ismapped():
            self.lima_panel.grid_remove()
        else:
            self.lima_panel.grid()
    
    # === Robot-Funktionen ===
    
    def _start_autofocus(self):
        """Startet Autofokus"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        try:
            success = self.robot_communicator.start_autofocus()
            if success:
                self.message_handler.show_info("Autofokus", "Autofokus wurde gestartet")
            else:
                self.message_handler.show_error("Fehler", "Autofokus konnte nicht gestartet werden")
        
        except CommunicationError as e:
            self.message_handler.show_error("Kommunikationsfehler", str(e))
    
    def _send_trigger(self):
        """Sendet Trigger-Signal"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        try:
            success = self.robot_communicator.send_trigger()
            if success:
                self.message_handler.show_info("Trigger", "Trigger wurde gesendet")
            else:
                self.message_handler.show_error("Fehler", "Trigger konnte nicht gesendet werden")
        
        except CommunicationError as e:
            self.message_handler.show_error("Kommunikationsfehler", str(e))
    
    def _autofocus_and_get_focus_value(self, field: str):
        """Startet Autofokus und holt anschließend den Fokuswert"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        def task():
            try:
                # Autofokus starten
                af_success = self.robot_communicator.start_autofocus()
                if not af_success:
                    self.after(0, lambda: self.message_handler.show_error("Fehler", "Autofokus fehlgeschlagen"))
                    return
                
                # Kurz warten
                time.sleep(1.0)
                
                # Fokuswert abrufen
                value = self.robot_communicator.get_focus_value()
                if value:
                    self.after(0, lambda: self._update_form_field(field, value))
                else:
                    self.after(0, lambda: self.message_handler.show_error("Fehler", "Fokuswert konnte nicht abgerufen werden"))
            
            except CommunicationError as e:
                self.after(0, lambda: self.message_handler.show_error("Kommunikationsfehler", str(e)))
        
        # In separatem Thread ausführen
        self.thread_manager.start_thread(task, name="AutofocusAndGet")
    
    def _get_af_value(self, field: str):
        """Holt AF-Wert"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        try:
            value = self.robot_communicator.get_af_value(field)
            if value:
                self._update_form_field(field, value)
            else:
                self.message_handler.show_error("Fehler", f"{field} konnte nicht abgerufen werden")
        
        except CommunicationError as e:
            self.message_handler.show_error("Kommunikationsfehler", str(e))
        except ValueError as e:
            self.message_handler.show_error("Fehler", str(e))
    
    def _get_af_origin_xyz(self):
        """Holt AF-Ursprung XYZ-Koordinaten"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        try:
            xyz_coords = self.robot_communicator.get_af_origin_xyz()
            if xyz_coords:
                # XYZ-Koordinaten in die entsprechenden Felder setzen
                if "af_origin_coords" in self.form_manager.widgets:
                    coords = self.form_manager.widgets["af_origin_coords"]
                    x, y, z = xyz_coords
                    
                    # Felder aktivieren zum Setzen
                    coords["X"].configure(state="normal")
                    coords["Y"].configure(state="normal")
                    coords["Z"].configure(state="normal")
                    
                    # Werte setzen
                    coords["X"].delete(0, 'end')
                    coords["Y"].delete(0, 'end')
                    coords["Z"].delete(0, 'end')
                    
                    coords["X"].insert(0, str(x))
                    coords["Y"].insert(0, str(y))
                    coords["Z"].insert(0, str(z))
                    
                    # AF Ursprung Hauptfeld auch setzen
                    af_origin_str = f"{x},{y},{z}"
                    self._update_form_field("AF Ursprung", af_origin_str)
                    
                    # Felder wieder deaktivieren wenn nicht Admin
                    if not self.admin_mode:
                        coords["X"].configure(state="disabled")
                        coords["Y"].configure(state="disabled")
                        coords["Z"].configure(state="disabled")
                    
                    self.logger.info(f"AF-Ursprung XYZ abgerufen: {xyz_coords}")
            else:
                self.message_handler.show_error("Fehler", "AF-Ursprung XYZ konnten nicht abgerufen werden")
        
        except CommunicationError as e:
            self.message_handler.show_error("Kommunikationsfehler", str(e))
    
    def _get_all_af_values(self):
        """Holt alle AF-Werte auf einmal"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        def task():
            try:
                # Alle AF-Felder durchgehen
                for field in Config.AF_FIELDS:
                    value = self.robot_communicator.get_af_value(field)
                    if value:
                        self.after(0, lambda f=field, v=value: self._update_form_field(f, v))
                    time.sleep(0.1)  # Kurze Pause zwischen Anfragen
                
                self.after(0, lambda: self.message_handler.show_info("Erfolg", "Alle AF-Werte wurden abgerufen"))
            
            except CommunicationError as e:
                self.after(0, lambda: self.message_handler.show_error("Kommunikationsfehler", str(e)))
        
        self.thread_manager.start_thread(task, name="GetAllAFValues")
    
    def _handle_position_request(self, field: str):
        """Behandelt Positionsanfragen"""
        if not self.robot_communicator:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        try:
            position = self.robot_communicator.get_current_position()
            if position:
                # Position je nach Feld-Typ verarbeiten
                if "X" in field:
                    self._update_form_field(field, str(position[0]))
                elif "Y" in field:
                    self._update_form_field(field, str(position[1]))
                elif "Z" in field:
                    self._update_form_field(field, str(position[2]))
                else:
                    # Vollständige Position als String
                    pos_str = f"{position[0]},{position[1]},{position[2]}"
                    self._update_form_field(field, pos_str)
            else:
                self.message_handler.show_error("Fehler", f"Position für {field} konnte nicht abgerufen werden")
        
        except CommunicationError as e:
            self.message_handler.show_error("Kommunikationsfehler", str(e))
    
    def _get_lima_info(self):
        """Holt Produktinformationen von LIMA"""
        if not self.lima_client:
            self.message_handler.show_error("Fehler", "LIMA-Verbindung nicht verfügbar")
            return
        
        # Produktnummer aus Formular holen
        product_number = self.form_manager.get_field_value("Produktnummer")
        if not product_number:
            self.message_handler.show_warning("Hinweis", "Bitte zuerst Produktnummer eingeben")
            return
        
        def task():
            try:
                product_info = self.lima_client.get_product_info(product_number)
                if product_info:
                    # Produktinformationen in Formular setzen
                    self.after(0, lambda: self._set_lima_product_info(product_info))
                else:
                    self.after(0, lambda: self.message_handler.show_warning("Nicht gefunden", 
                                                                          f"Keine Informationen für Produktnummer {product_number} gefunden"))
            
            except CommunicationError as e:
                self.after(0, lambda: self.message_handler.show_error("Kommunikationsfehler", str(e)))
        
        self.thread_manager.start_thread(task, name="GetLimaInfo")
    
    def _set_lima_product_info(self, product_info: Dict[str, Any]):
        """Setzt Produktinformationen aus LIMA in das Formular"""
        try:
            for field, value in product_info.items():
                if field in self.form_manager.entries:
                    self._update_form_field(field, str(value))
            
            self.message_handler.show_info("Erfolg", "Produktinformationen von LIMA erhalten")
        
        except Exception as e:
            self.logger.error(f"Fehler beim Setzen der LIMA-Produktinfos: {e}")
            self.message_handler.show_error("Fehler", "Produktinformationen konnten nicht gesetzt werden")
    
    def _update_form_field(self, field: str, value: str):
        """Aktualisiert ein Formularfeld"""
        try:
            if field in self.form_manager.entries:
                entry = self.form_manager.entries[field]
                
                # Feld aktivieren zum Setzen
                if hasattr(entry, 'configure'):
                    entry.configure(state="normal")
                
                # Wert setzen
                if hasattr(entry, 'delete') and hasattr(entry, 'insert'):
                    entry.delete(0, 'end')
                    entry.insert(0, value)
                elif hasattr(entry, 'set'):
                    entry.set(value)
                
                # Feld wieder deaktivieren wenn nicht Admin
                if not self.admin_mode and hasattr(entry, 'configure'):
                    entry.configure(state="disabled")
                
                self.logger.debug(f"Feld {field} auf {value} gesetzt")
        
        except Exception as e:
            self.logger.error(f"Fehler beim Aktualisieren des Feldes {field}: {e}")
    
    # === Listener Mode ===
    
    def _start_listener_mode(self):
        """Startet den erweiterten Listener-Modus mit Nachrichtenverfolgung"""
        if self.listener_mode and self.listener_mode.is_running():
            self.message_handler.show_warning("Hinweis", "Listener-Modus läuft bereits")
            return

        try:
            # Listener-Konfiguration
            listen_port = int(self.listener_port_entry.get())
            send_ip = self.send_ip_entry.get()
            send_port = int(self.send_port_entry.get())

            # Listener-Modus starten mit BEIDEN Callbacks
            self.listener_mode = ListenerMode(listen_port, send_ip, send_port)
            success = self.listener_mode.start(
                self._handle_listener_message,
                self._on_listener_log_event  # Log-Callback hinzufügen
            )

            if success:
                self.listener_start_time = time.time()
                self._show_listener_log_window()  # Korrigierter Methodenname

                self.sidebar_manager.set_listener_active(True)
                self.message_handler.show_info("Listener gestartet", f"Lauscht auf Port {listen_port}")
                self.logger.info(f"Listener-Modus gestartet auf Port {listen_port}")
            else:
                self.message_handler.show_error("Fehler", "Listener-Modus konnte nicht gestartet werden")

        except Exception as e:
            self.logger.error(f"Fehler beim Starten des Listener-Modus: {e}")
            self.message_handler.show_error("Fehler", f"Listener-Modus fehlgeschlagen: {e}")

    def _show_listener_log_window(self):
        """Zeigt das erweiterte Listener-Log-Fenster"""
        try:
            # Altes Fenster schließen falls vorhanden
            if hasattr(self, 'listener_log_window') and self.listener_log_window:
                try:
                    if self.listener_log_window.winfo_exists():
                        self.listener_log_window.destroy()
                except:
                    pass

            # Import prüfen
            if ListenerLogWindow is None:
                self.logger.error("ListenerLogWindow nicht verfügbar - verwende Fallback")
                self._show_listener_popup()  # Fallback zur alten Popup-Methode
                return

            # Neues Log-Fenster erstellen
            self.listener_log_window = ListenerLogWindow(self)
            self.listener_popup = self.listener_log_window  # Kompatibilität

        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen des Listener-Fensters: {e}")
            # Fallback zur alten Methode
            self._show_listener_popup()

    def _on_listener_log_event(self, event: Dict[str, Any]):
        """Callback für Listener-Log-Events - Thread-sicher"""
        try:
            # Event an Log-Fenster weiterleiten - Thread-sicher
            if hasattr(self, 'listener_log_window') and self.listener_log_window:
                try:
                    if self.listener_log_window.winfo_exists():
                        # Verwende after() für Thread-sichere UI-Updates
                        self.listener_log_window.after(0,
                            lambda: self.listener_log_window.add_log_entry(event))
                except tk.TclError:
                    # Fenster wurde bereits zerstört
                    pass

            # Optional: Events auch in normales Log schreiben
            event_type = event.get('type', '')
            message = event.get('message', '')
            source = event.get('source', '')

            if event_type in ['MESSAGE_RECEIVED', 'MESSAGE_SENT']:
                self.logger.info(f"Listener [{event_type}] von {source}: {message}")

        except Exception as e:
            self.logger.error(f"Fehler im Listener-Log-Event: {e}")

    def _stop_listener_mode(self):
        """Stoppt den Listener-Modus"""
        if self.listener_mode:
            self.listener_mode.stop()
            self.listener_mode = None

        # Log-Fenster schließen
        if hasattr(self, 'listener_log_window') and self.listener_log_window:
            try:
                if self.listener_log_window.winfo_exists():
                    self.listener_log_window.destroy()
            except:
                pass
            self.listener_log_window = None
            self.listener_popup = None
        elif self.listener_popup:
            self.listener_popup.destroy()
            self.listener_popup = None

        self.listener_start_time = None
        self.sidebar_manager.set_listener_active(False)

        self.message_handler.show_info("Listener gestoppt", "Listener-Modus wurde beendet")
        self.logger.info("Listener-Modus gestoppt")
    
    def _show_listener_popup(self):
        """Zeigt Listener-Status-Popup"""
        if self.listener_popup:
            self.listener_popup.destroy()
        
        self.listener_popup = ctk.CTkToplevel(self)
        self.listener_popup.title("Listener-Modus aktiv")
        self.listener_popup.geometry("400x200")
        self.listener_popup.resizable(False, False)

        # Popup zentrieren
        self.listener_popup.transient(self)

        # Content
        status_label = ctk.CTkLabel(
            self.listener_popup,
            text="🔊 Listener-Modus aktiv",
            font=("Arial", 16, "bold")
        )
        status_label.pack(pady=20)

        port_label = ctk.CTkLabel(
            self.listener_popup,
            text=f"Port: {self.listener_port_entry.get()}"
        )
        port_label.pack(pady=5)
        
        # Stop-Button
        stop_btn = ctk.CTkButton(
            self.listener_popup,
            text="Listener stoppen",
            command=self._stop_listener_mode,
            fg_color="red",
            hover_color="darkred"
        )
        stop_btn.pack(pady=20)
        
        # Popup-Schließen behandeln
        self.listener_popup.protocol("WM_DELETE_WINDOW", self._stop_listener_mode)
    
    
    def _handle_listener_message(self, message: str, sender_ip: str):
        """Behandelt empfangene Listener-Nachrichten"""
        try:
            self.logger.info(f"Listener-Nachricht von {sender_ip}: {message}")
            
            # Nachricht verarbeiten (je nach Protokoll)
            # Hier würde die spezifische Nachrichtenverarbeitung stattfinden
            
            # Beispiel: Produktnummer aus Nachricht extrahieren und laden
            if message.startswith("LOAD_PRODUCT:"):
                product_number = message.split(":", 1)[1].strip()
                self.after(0, lambda: self._load_product_by_number(product_number))
            
            elif message.startswith("GET_AF_VALUES"):
                self.after(0, lambda: self._get_all_af_values())
            
            elif message.startswith("TRIGGER"):
                self.after(0, lambda: self._send_trigger())
            
            else:
                self.logger.warning(f"Unbekannte Listener-Nachricht: {message}")
        
        except Exception as e:
            self.logger.error(f"Fehler beim Verarbeiten der Listener-Nachricht: {e}")
    
    def _load_product_by_number(self, product_number: str):
        """Lädt Produkt anhand der Produktnummer"""
        try:
            # Produkt in der Liste suchen
            for i, product in enumerate(self.products):
                if str(product.get("Produktnummer", "")) == product_number:
                    self._load_product(i)
                    self.message_handler.show_info("Produkt geladen", f"Produktnummer {product_number} wurde geladen")
                    return
            
            self.message_handler.show_warning("Nicht gefunden", f"Produktnummer {product_number} nicht gefunden")
        
        except Exception as e:
            self.logger.error(f"Fehler beim Laden des Produkts {product_number}: {e}")
            self.message_handler.show_error("Fehler", f"Produkt {product_number} konnte nicht geladen werden")
    
    # === Cleanup und Exit ===
    
    def _on_closing(self):
        """Wird beim Schließen der Anwendung aufgerufen"""
        try:
            self.logger.info("Anwendung wird beendet...")
            
            # Listener-Modus stoppen
            if self.listener_mode:
                self._stop_listener_mode()
            
            # Threads beenden
            self.thread_manager.shutdown()
            
            # Datenbankverbindung schließen
            if hasattr(self.db_manager, 'close'):
                self.db_manager.close()
            
            # LIMA-Verbindung schließen
            if self.lima_client:
                self.lima_client.close()
            
            self.logger.info("Cleanup abgeschlossen")
            
        except Exception as e:
            self.logger.error(f"Fehler beim Cleanup: {e}")
        
        finally:
            self.destroy()


# === Hauptfunktion ===

def main():
    """Hauptfunktion zum Starten der Anwendung"""
    try:
        app = ProduktManagerApp()
        app.mainloop()
    
    except Exception as e:
        print(f"Kritischer Fehler beim Starten der Anwendung: {e}")
        logging.error(f"Kritischer Fehler beim Starten: {e}")
    
    finally:
        # Sicherstellen, dass alle Threads beendet werden
        import threading
        for thread in threading.enumerate():
            if thread != threading.current_thread():
                try:
                    if hasattr(thread, 'join') and thread.is_alive():
                        thread.join(timeout=1.0)
                except Exception:
                    pass


if __name__ == "__main__":
    main()
