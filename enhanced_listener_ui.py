"""
Erweiterte UI-Komponenten für Listener-Mode mit Nachrichtenverfolgung
"""
import customtkinter as ctk
import tkinter as tk
from typing import Dict, Any, List, Optional
import time
from datetime import datetime


class ListenerLogWindow(ctk.CTkToplevel):
    """Separates Fenster für Listener-Logs mit erweiterter Anzeige"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        
        self.title("Listener-Mode - Nachrichtenverfolgung")
        self.geometry("900x600")
        self.resizable(True, True)
        
        # Fenster konfigurieren - NICHT grab_set() verwenden
        self.transient(parent)
        # self.grab_set()  # ENTFERNT - verhindert Interaktion mit Hauptfenster

        # Fensterzerstörung behandeln
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # UI erstellen
        self.create_widgets()

        # Automatisch scrollen
        self.auto_scroll = True

        # Update-Timer starten
        self.update_timer_running = True
        self.after(100, self.update_display)

    def on_window_close(self):
        """Wird aufgerufen wenn Fenster geschlossen wird"""
        self.update_timer_running = False  # Timer stoppen
        self.stop_listener()

    def stop_listener(self):
        """Stoppt den Listener und schließt das Fenster"""
        self.update_timer_running = False  # Timer stoppen
        if hasattr(self.parent_app, '_stop_listener_mode'):
            self.parent_app._stop_listener_mode()
        else:
            self.destroy()
    
    def create_widgets(self):
        """Erstellt die UI-Elemente"""
        # Header mit Status-Info
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.pack(fill="x", padx=10, pady=5)
        
        # Status-Label
        self.status_label = ctk.CTkLabel(
            self.header_frame,
            text="🔊 Listener-Modus aktiv",
            font=("Arial", 16, "bold")
        )
        self.status_label.pack(side="left", padx=10, pady=10)
        
        # Laufzeit-Label
        self.runtime_label = ctk.CTkLabel(
            self.header_frame,
            text="Laufzeit: 00:00:00"
        )
        self.runtime_label.pack(side="right", padx=10, pady=10)
        
        # Port-Info
        if hasattr(self.parent_app, 'listener_port_entry'):
            port = self.parent_app.listener_port_entry.get()
            self.port_label = ctk.CTkLabel(
                self.header_frame,
                text=f"Port: {port}"
            )
            self.port_label.pack(side="right", padx=10, pady=10)
        
        # Steuerungsbuttons
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.pack(fill="x", padx=10, pady=5)
        
        # Auto-Scroll Toggle
        self.auto_scroll_var = ctk.BooleanVar(value=True)
        self.auto_scroll_checkbox = ctk.CTkCheckBox(
            self.control_frame,
            text="Automatisch scrollen",
            variable=self.auto_scroll_var,
            command=self.toggle_auto_scroll
        )
        self.auto_scroll_checkbox.pack(side="left", padx=10, pady=5)
        
        # Clear-Button
        self.clear_btn = ctk.CTkButton(
            self.control_frame,
            text="Log löschen",
            command=self.clear_log,
            width=100
        )
        self.clear_btn.pack(side="left", padx=10, pady=5)
        
        # Export-Button
        self.export_btn = ctk.CTkButton(
            self.control_frame,
            text="Exportieren",
            command=self.export_log,
            width=100
        )
        self.export_btn.pack(side="left", padx=10, pady=5)
        
        # Statistik-Label
        self.stats_label = ctk.CTkLabel(
            self.control_frame,
            text="Nachrichten: 0"
        )
        self.stats_label.pack(side="right", padx=10, pady=5)
        
        # Log-Textfeld mit Scrollbar
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Textfeld für Logs
        self.log_text = ctk.CTkTextbox(
            self.log_frame,
            font=("Courier", 10),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Stop-Button
        self.stop_btn = ctk.CTkButton(
            self,
            text="Listener stoppen",
            command=self.stop_listener,
            fg_color="red",
            hover_color="darkred",
            height=40
        )
        self.stop_btn.pack(pady=10)
        
        # Fenster-Schließen behandeln
        self.protocol("WM_DELETE_WINDOW", self.stop_listener)
    
    def toggle_auto_scroll(self):
        """Schaltet Auto-Scroll um"""
        self.auto_scroll = self.auto_scroll_var.get()
    
    def clear_log(self):
        """Löscht das Log"""
        self.log_text.delete("1.0", "end")
        # Log im Listener-Mode löschen
        if hasattr(self.parent_app, 'listener_mode') and self.parent_app.listener_mode:
            self.parent_app.listener_mode.clear_message_log()
    
    def export_log(self):
        """Exportiert das Log in eine Datei"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"listener_log_{timestamp}.txt"
            
            content = self.log_text.get("1.0", "end")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Listener Log Export - {datetime.now()}\n")
                f.write("=" * 50 + "\n\n")
                f.write(content)
            
            # Erfolg-Message
            success_msg = ctk.CTkInputDialog(
                text=f"Log erfolgreich exportiert nach:\n{filename}",
                title="Export erfolgreich"
            )
            
        except Exception as e:
            # Fehler-Message
            error_msg = ctk.CTkInputDialog(
                text=f"Fehler beim Exportieren:\n{e}",
                title="Export fehlgeschlagen"
            )
    
    def add_log_entry(self, event: Dict[str, Any]):
        """Fügt einen Log-Eintrag hinzu - Thread-sicher"""
        try:
            if not self.winfo_exists():
                return

            color_map = {
                "MESSAGE_RECEIVED": "lightblue",
                "MESSAGE_SENT": "lightgreen",
                "RESPONSE_SENT": "lightcyan",
                "RESPONSE_RECEIVED": "lightyellow",
                "LISTENER_STARTED": "lightgray",
                "LISTENER_STOPPED": "lightgray",
                "CLIENT_ERROR": "lightcoral",
                "SEND_ERROR": "lightcoral",
                "SYSTEM": "lightgray"
            }

            icon_map = {
                "MESSAGE_RECEIVED": "⬇️",
                "MESSAGE_SENT": "⬆️",
                "RESPONSE_SENT": "↗️",
                "RESPONSE_RECEIVED": "↙️",
                "LISTENER_STARTED": "🟢",
                "LISTENER_STOPPED": "🔴",
                "CLIENT_ERROR": "❌",
                "SEND_ERROR": "❌",
                "SYSTEM": "ℹ️"
            }

            timestamp = event.get('timestamp', '')
            event_type = event.get('type', 'UNKNOWN')
            message = event.get('message', '')
            source = event.get('source', '')

            icon = icon_map.get(event_type, "📝")

            log_line = f"{timestamp} {icon} [{event_type}] {source}: {message}\n"

            self.log_text.insert("end", log_line)

            if self.auto_scroll:
                self.log_text.see("end")

        except Exception as e:
            print(f"Fehler beim Hinzufügen des Log-Eintrags: {e}")
    
    def update_display(self):
        """Aktualisiert die Anzeige periodisch"""
        try:
            # Prüfen ob Timer noch laufen soll
            if not self.update_timer_running or not self.winfo_exists():
                return

            # Laufzeit aktualisieren
            if hasattr(self.parent_app, 'listener_start_time') and self.parent_app.listener_start_time:
                elapsed = int(time.time() - self.parent_app.listener_start_time)
                hours = elapsed // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60

                time_str = f"Laufzeit: {hours:02d}:{minutes:02d}:{seconds:02d}"
                self.runtime_label.configure(text=time_str)

            # Statistik aktualisieren
            if hasattr(self.parent_app, 'listener_mode') and self.parent_app.listener_mode:
                log_count = len(self.parent_app.listener_mode.get_message_log())
                self.stats_label.configure(text=f"Nachrichten: {log_count}")

            # Nächstes Update planen - nur wenn Timer noch läuft
            if self.update_timer_running:
                self.after(1000, self.update_display)

        except Exception as e:
            print(f"Fehler beim Aktualisieren der Anzeige: {e}")
            self.update_timer_running = False


class MessageDetailsDialog(ctk.CTkToplevel):
    """Dialog für detaillierte Nachrichtenansicht"""
    
    def __init__(self, parent, message_data: Dict[str, Any]):
        super().__init__(parent)
        self.message_data = message_data
        
        self.title("Nachrichten-Details")
        self.geometry("600x400")
        self.resizable(False, False)
        self.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        """Erstellt die Detail-Widgets"""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        title = ctk.CTkLabel(
            header_frame,
            text=f"Nachricht: {self.message_data.get('type', 'Unbekannt')}",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=10)
        
        # Details-Frame
        details_frame = ctk.CTkScrollableFrame(self)
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Alle Daten anzeigen
        for key, value in self.message_data.items():
            row_frame = ctk.CTkFrame(details_frame)
            row_frame.pack(fill="x", pady=2)
            
            key_label = ctk.CTkLabel(
                row_frame,
                text=f"{key}:",
                font=("Arial", 12, "bold"),
                width=100,
                anchor="w"
            )
            key_label.pack(side="left", padx=5, pady=5)
            
            value_text = ctk.CTkTextbox(
                row_frame,
                height=60,
                font=("Courier", 10)
            )
            value_text.pack(side="right", fill="x", expand=True, padx=5, pady=5)
            value_text.insert("1.0", str(value))
            value_text.configure(state="disabled")
        
        # Schließen-Button
        close_btn = ctk.CTkButton(
            self,
            text="Schließen",
            command=self.destroy
        )
        close_btn.pack(pady=10)