"""
UI-Management für den THT-Produktmanager
"""
import customtkinter as ctk
import tkinter.messagebox as mbox
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from config import Config
from validation import Validator
from exceptions import ValidationError, AuthenticationError

logger = logging.getLogger(__name__)

class BaseUIComponent:
    """Basis-Klasse für UI-Komponenten"""
    
    def __init__(self, parent):
        self.parent = parent
        self.widgets = {}
    
    def create_widgets(self):
        """Erstellt die UI-Widgets (zu implementieren in Subklassen)"""
        raise NotImplementedError
    
    def get_widget(self, name: str):
        """Holt ein Widget nach Name"""
        return self.widgets.get(name)
    
    def set_widget_state(self, name: str, state: str):
        """Setzt den Zustand eines Widgets"""
        widget = self.get_widget(name)
        if widget and hasattr(widget, 'configure'):
            widget.configure(state=state)

class FormManager(BaseUIComponent):
    """Verwaltet Formulareingaben"""
    
    def __init__(self, parent, fields: List[str]):
        super().__init__(parent)
        self.fields = fields
        self.form_data = {}
        self.entries = {}
        self.create_form()
    
    def create_form(self):
        """Erstellt das Formular"""
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.parent, 
            label_text="Produktdaten", 
            corner_radius=10
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self._create_form_sections()
    
    def _create_form_sections(self):
        """Erstellt die verschiedenen Formular-Abschnitte"""
        row_offset = 0
        
        # Produktinformationen
        row_offset = self._create_basic_info_section(row_offset)
        
        # Produktabmessungen
        row_offset = self._create_dimensions_section(row_offset)
        
        # PCB-Felder
        row_offset = self._create_pcb_section(row_offset)
        
        # Autofokus-Felder
        row_offset = self._create_autofocus_section(row_offset)
        
        # Position-Felder
        row_offset = self._create_position_section(row_offset)
        
        return row_offset
    
    def _create_basic_info_section(self, row_offset: int) -> int:
        """Erstellt Grundinformations-Sektion"""
        header = ctk.CTkLabel(
            self.scrollable_frame, 
            text="Produktinformationen:", 
            font=("Arial", 14, "bold")
        )
        header.grid(row=row_offset, column=0, sticky="w", pady=(10, 2))
        row_offset += 1
        
        basic_fields = Config.BASIC_FIELDS
        for field in basic_fields:
            row_offset = self._create_form_field(field, row_offset)
        
        return row_offset
    
    def _create_dimensions_section(self, row_offset: int) -> int:
        """Erstellt Abmessungs-Sektion"""
        header = ctk.CTkLabel(
            self.scrollable_frame,
            text="Produktabmessungen (mm):",
            font=("Arial", 14, "bold")
        )
        header.grid(row=row_offset, column=0, sticky="w", pady=(10, 2))
        row_offset += 1
        
        for field in Config.DIMENSION_FIELDS:
            row_offset = self._create_form_field(field, row_offset)
        
        return row_offset
    
    def _create_pcb_section(self, row_offset: int) -> int:
        """Erstellt PCB-Sektion"""
        header = ctk.CTkLabel(
            self.scrollable_frame,
            text="Fokuswerte:",
            font=("Arial", 14, "bold")
        )
        header.grid(row=row_offset, column=0, sticky="w", pady=(10, 2))
        row_offset += 1
        
        for field in Config.PCB_FIELDS:
            row_offset = self._create_form_field(field, row_offset, has_button=True, 
                                               button_text="Auto + Abrufen")
        
        return row_offset
    
    def _create_autofocus_section(self, row_offset: int) -> int:
        """Erstellt Autofokus-Sektion"""
        header = ctk.CTkLabel(
            self.scrollable_frame,
            text="Autofokus-Box:",
            font=("Arial", 14, "bold")
        )
        header.grid(row=row_offset, column=0, sticky="w", pady=(15, 2))
        row_offset += 1
        
        # AF Ursprung (spezielle Behandlung für XYZ)
        row_offset = self._create_af_origin_field(row_offset)
        
        # Andere AF-Felder
        for field in Config.AF_FIELDS:
            row_offset = self._create_form_field(field, row_offset, has_button=True)
        
        return row_offset
    
    def _create_position_section(self, row_offset: int) -> int:
        """Erstellt Position-Sektion"""
        header = ctk.CTkLabel(
            self.scrollable_frame,
            text="PCB-Positionen (TCP):",
            font=("Arial", 14, "bold")
        )
        header.grid(row=row_offset, column=0, sticky="w", pady=(10, 2))
        row_offset += 1
        
        for field in Config.POSITION_FIELDS:
            row_offset = self._create_form_field(field, row_offset, has_button=True)
        
        return row_offset
    
    def _create_form_field(self, field: str, row: int, has_button: bool = False, 
                          button_text: str = "Abrufen") -> int:
        """Erstellt ein einzelnes Formularfeld"""
        label = ctk.CTkLabel(self.scrollable_frame, text=field, anchor="w")
        label.grid(row=row, column=0, sticky="w", pady=5)
        
        entry = ctk.CTkEntry(self.scrollable_frame, width=300)
        entry.grid(row=row, column=1, pady=5)
        entry.configure(state="disabled")
        
        self.entries[field] = entry
        
        if has_button:
            btn = ctk.CTkButton(
                self.scrollable_frame, 
                text=button_text, 
                width=120, 
                height=26,
                font=("Arial", 10)
            )
            btn.grid(row=row, column=2, padx=5)
            self.widgets[f"{field}_button"] = btn
        
        return row + 1
    
    def _create_af_origin_field(self, row: int) -> int:
        """Erstellt spezielle AF-Ursprung-Felder für XYZ"""
        label = ctk.CTkLabel(self.scrollable_frame, text="AF Ursprung:", anchor="w")
        label.grid(row=row, column=0, sticky="w", pady=5)
        
        # XYZ-Eingabefelder
        coords = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            coord_label = ctk.CTkLabel(self.scrollable_frame, text=f"{axis}:")
            coord_entry = ctk.CTkEntry(self.scrollable_frame, width=60)
            
            x_pos = 25 + i * 75
            coord_label.grid(row=row, column=1, sticky="w", padx=(x_pos, 5))
            coord_entry.grid(row=row, column=1, sticky="w", padx=(x_pos + 25, 5))
            coord_entry.configure(state="disabled")
            
            coords[axis] = coord_entry
        
        self.widgets["af_origin_coords"] = coords
        
        # Buttons
        btn_abrufen = ctk.CTkButton(
            self.scrollable_frame, text="Abrufen", width=80, height=26, font=("Arial", 10)
        )
        btn_abrufen.grid(row=row, column=2, padx=5)
        
        btn_alle = ctk.CTkButton(
            self.scrollable_frame, text="Alle abrufen", width=100, height=26, font=("Arial", 10)
        )
        btn_alle.grid(row=row, column=3, padx=5)
        
        self.widgets["af_origin_button"] = btn_abrufen
        self.widgets["af_all_button"] = btn_alle
        
        return row + 1
    
    def get_form_data(self) -> Dict[str, str]:
        """Holt alle Formulardaten"""
        data = {}
        for field, entry in self.entries.items():
            data[field] = entry.get().strip()
        
        # AF Ursprung kombinieren
        if "af_origin_coords" in self.widgets:
            coords = self.widgets["af_origin_coords"]
            af_origin = ",".join([coords[axis].get() for axis in ['X', 'Y', 'Z']])
            data["AF Ursprung"] = af_origin
        
        return data
    
    def set_form_data(self, data: Dict[str, Any]):
        """Setzt Formulardaten"""
        for field, entry in self.entries.items():
            value = data.get(field, "")
            entry.configure(state="normal")
            entry.delete(0, 'end')
            entry.insert(0, str(value) if value is not None else "")
    
    def enable_form(self, enabled: bool = True):
        """Aktiviert/Deaktiviert das gesamte Formular"""
        state = "normal" if enabled else "disabled"
        for entry in self.entries.values():
            entry.configure(state=state)
        
        # AF-Ursprung-Koordinaten
        if "af_origin_coords" in self.widgets:
            coords = self.widgets["af_origin_coords"]
            for coord_entry in coords.values():
                coord_entry.configure(state=state)
    
    def clear_form(self):
        """Leert das gesamte Formular"""
        for entry in self.entries.values():
            entry.configure(state="normal")
            entry.delete(0, 'end')
            entry.configure(state="disabled")
        
        # AF-Ursprung-Koordinaten
        if "af_origin_coords" in self.widgets:
            coords = self.widgets["af_origin_coords"]
            for coord_entry in coords.values():
                coord_entry.configure(state="normal")
                coord_entry.delete(0, 'end')
                coord_entry.configure(state="disabled")

class SidebarManager(BaseUIComponent):
    """Verwaltet die Seitenleiste"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.admin_mode = False
        self.product_buttons = []
        self.create_sidebar()
    
    def create_sidebar(self):
        """Erstellt die Seitenleiste"""
        self.sidebar = ctk.CTkFrame(self.parent, width=Config.SIDEBAR_WIDTH)
        self.sidebar.pack(side="right", fill="y")
        
        self.sidebar_label = ctk.CTkLabel(self.sidebar, text="Produkte")
        self.sidebar_label.pack(pady=10)
        
        self.product_listbox = ctk.CTkScrollableFrame(self.sidebar)
        self.product_listbox.pack(fill="both", expand=True)
        
        self._create_control_buttons()
    
    def _create_control_buttons(self):
        """Erstellt Steuerungsbuttons"""
        # Login Button (immer sichtbar)
        self.widgets["login_btn"] = ctk.CTkButton(
            self.sidebar, text="Admin Login"
        )
        self.widgets["login_btn"].pack(pady=5)
        
        # Admin-Buttons (initial versteckt)
        admin_buttons = [
            ("new_btn", "Neues Produkt"),
            ("delete_btn", "Produkt löschen"),
            ("logout_btn", "Logout")
        ]
        
        for btn_name, btn_text in admin_buttons:
            btn = ctk.CTkButton(self.sidebar, text=btn_text)
            btn.pack_forget()  # Initial versteckt
            self.widgets[btn_name] = btn
        
        # Listener-Buttons
        listener_buttons = [
            ("listener_start_btn", "Listener Mode starten"),
            ("listener_stop_btn", "Listener Mode stoppen")
        ]
        
        for btn_name, btn_text in listener_buttons:
            btn = ctk.CTkButton(self.sidebar, text=btn_text)
            btn.pack(pady=5)
            self.widgets[btn_name] = btn
    
    def populate_products(self, products: List[Any], click_callback: Callable):
        """Füllt die Produktliste"""
        # Alte Buttons entfernen
        for btn in self.product_buttons:
            btn.destroy()
        self.product_buttons.clear()
        
        # Neue Buttons erstellen
        for idx, product in enumerate(products):
            btn_text = f"{product['Laufende Nummer']}: {product['Produktnummer']}"
            btn = ctk.CTkButton(
                self.product_listbox, 
                text=btn_text, 
                width=180
            )
            btn.configure(command=lambda i=idx: click_callback(i))
            btn.pack(pady=2)
            self.product_buttons.append(btn)
    
    def set_admin_mode(self, admin_mode: bool):
        """Setzt Admin-Modus"""
        self.admin_mode = admin_mode
        
        if admin_mode:
            # Admin-Buttons anzeigen
            for btn_name in ["new_btn", "delete_btn", "logout_btn"]:
                self.widgets[btn_name].pack(pady=5)
            self.widgets["login_btn"].pack_forget()
        else:
            # Admin-Buttons verstecken
            for btn_name in ["new_btn", "delete_btn", "logout_btn"]:
                self.widgets[btn_name].pack_forget()
            self.widgets["login_btn"].pack(pady=5)

class StatusManager(BaseUIComponent):
    """Verwaltet Statusanzeigen"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.status_labels = {}
    
    def create_status_panel(self, parent_frame):
        """Erstellt Status-Panel"""
        status_frame = ctk.CTkFrame(parent_frame)
        status_frame.pack(pady=5, fill="x")
        
        # LIMA-Status
        self.status_labels["lima"] = ctk.CTkLabel(
            status_frame, 
            text="LIMA: ❔ Unbekannt"
        )
        self.status_labels["lima"].pack(side="left", padx=10)
        
        # Listener-Status
        self.status_labels["listener"] = ctk.CTkLabel(
            status_frame,
            text="Listener: ⭕ Gestoppt"
        )
        self.status_labels["listener"].pack(side="right", padx=10)
        
        return status_frame
    
    def update_lima_status(self, connected: bool):
        """Aktualisiert LIMA-Status"""
        if connected:
            self.status_labels["lima"].configure(
                text="LIMA: 🟢 Verbunden", 
                text_color="green"
            )
        else:
            self.status_labels["lima"].configure(
                text="LIMA: 🔴 Getrennt",
                text_color="red"
            )
    
    def update_listener_status(self, running: bool, info: str = ""):
        """Aktualisiert Listener-Status"""
        if running:
            text = f"Listener: 🟢 Aktiv {info}"
            color = "green"
        else:
            text = "Listener: ⭕ Gestoppt"
            color = "gray"
        
        self.status_labels["listener"].configure(text=text, text_color=color)

class MessageHandler:
    """Verwaltet Benutzer-Nachrichten"""
    
    @staticmethod
    def show_info(title: str, message: str):
        """Zeigt Info-Nachricht"""
        logger.info(f"{title}: {message}")
        mbox.showinfo(title, message)
    
    @staticmethod
    def show_warning(title: str, message: str):
        """Zeigt Warnung"""
        logger.warning(f"{title}: {message}")
        mbox.showwarning(title, message)
    
    @staticmethod
    def show_error(title: str, message: str):
        """Zeigt Fehler"""
        logger.error(f"{title}: {message}")
        mbox.showerror(title, message)
    
    @staticmethod
    def ask_yes_no(title: str, message: str) -> bool:
        """Fragt Ja/Nein"""
        result = mbox.askyesno(title, message)
        logger.info(f"{title}: {message} -> {result}")
        return result
    
    @staticmethod
    def get_input(title: str, prompt: str) -> Optional[str]:
        """Holt Benutzereingabe"""
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        result = dialog.get_input()
        logger.info(f"Input Dialog '{title}': {'Eingabe erhalten' if result else 'Abgebrochen'}")
        return result