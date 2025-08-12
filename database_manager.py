"""
Datenbankmanagement für den THT-Produktmanager
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from config import Config
from exceptions import DatabaseError
from validation import Validator

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Verwaltet alle Datenbankoperationen"""
    
    def __init__(self, db_file: str = Config.DB_FILE):
        self.db_file = db_file
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context Manager für Datenbankverbindungen"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Datenbankfehler: {e}")
            raise DatabaseError(f"Datenbankfehler: {e}")
        finally:
            if conn:
                conn.close()
    
    def init_database(self) -> None:
        """Initialisiert die Datenbank mit allen erforderlichen Feldern"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Basis-Tabelle erstellen
                c.execute(self._get_create_table_sql())
                
                # Position-Felder hinzufügen (falls noch nicht vorhanden)
                self._add_position_fields(c)
                
                conn.commit()
                logger.info("Datenbank erfolgreich initialisiert")
        
        except Exception as e:
            logger.error(f"Fehler bei Datenbank-Initialisierung: {e}")
            raise DatabaseError(f"Datenbank-Initialisierung fehlgeschlagen: {e}")
    
    def _get_create_table_sql(self) -> str:
        """Generiert das CREATE TABLE SQL-Statement"""
        return f"""
            CREATE TABLE IF NOT EXISTS produkte (
                "Laufende Nummer" INTEGER PRIMARY KEY,
                "Produktnummer" TEXT,
                "Kunde" TEXT,
                "Notizen" TEXT,
                "Frame Width (mm)" TEXT,
                "Frame Height (mm)" TEXT,
                "PCB_0 Top" TEXT,
                "PCB_1 Back" TEXT,
                "PCB_2 Right" TEXT,
                "PCB_3 Front" TEXT,
                "PCB_4 Left" TEXT,
                "AF Ursprung" TEXT,
                "AF Breite" TEXT,
                "AF Höhe" TEXT,
                "AF Tiefe" TEXT,
                "AI angelegt" INTEGER DEFAULT 0,
                "AI Zeitstempel" TEXT,
                "Cobot angelegt" INTEGER DEFAULT 0,
                "Cobot Zeitstempel" TEXT
            )
        """
    
    def _add_position_fields(self, cursor) -> None:
        """Fügt Position-Felder zur Tabelle hinzu (falls nicht vorhanden)"""
        for field in Config.POSITION_FIELDS:
            try:
                cursor.execute(f'ALTER TABLE produkte ADD COLUMN "{field}" TEXT')
                logger.info(f"Feld {field} zur Tabelle hinzugefügt")
            except sqlite3.OperationalError:
                # Feld existiert bereits
                pass
    
    def fetch_all_products(self) -> List[sqlite3.Row]:
        """Holt alle Produkte aus der Datenbank"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM produkte ORDER BY "Laufende Nummer" ASC')
                products = c.fetchall()
                logger.info(f"{len(products)} Produkte aus Datenbank geladen")
                return products
        
        except Exception as e:
            logger.error(f"Fehler beim Laden der Produkte: {e}")
            raise DatabaseError(f"Produkte konnten nicht geladen werden: {e}")
    
    def insert_product(self, data: Dict[str, Any]) -> None:
        """Fügt ein neues Produkt hinzu"""
        try:
            # Validierung
            if "Laufende Nummer" in data:
                Validator.validate_required_field(str(data["Laufende Nummer"]), "Laufende Nummer")
                if not Validator.validate_laufnummer(str(data["Laufende Nummer"])):
                    raise ValidationError("Ungültige Laufende Nummer")
            
            with self.get_connection() as conn:
                c = conn.cursor()
                columns = ', '.join([f'"{k}"' for k in data.keys()])
                placeholders = ', '.join(['?'] * len(data))
                sql = f'INSERT INTO produkte ({columns}) VALUES ({placeholders})'
                c.execute(sql, list(data.values()))
                conn.commit()
                logger.info(f"Produkt {data.get('Laufende Nummer')} eingefügt")
        
        except Exception as e:
            logger.error(f"Fehler beim Einfügen des Produkts: {e}")
            raise DatabaseError(f"Produkt konnte nicht eingefügt werden: {e}")
    
    def update_product(self, laufende_nummer: int, data: Dict[str, Any]) -> None:
        """Aktualisiert ein vorhandenes Produkt"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                setstr = ', '.join([f'"{k}"=?' for k in data.keys()])
                values = list(data.values()) + [laufende_nummer]
                sql = f'UPDATE produkte SET {setstr} WHERE "Laufende Nummer"=?'
                c.execute(sql, values)
                conn.commit()
                logger.info(f"Produkt {laufende_nummer} aktualisiert")
        
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Produkts: {e}")
            raise DatabaseError(f"Produkt konnte nicht aktualisiert werden: {e}")
    
    def delete_product(self, laufende_nummer: int) -> None:
        """Löscht ein Produkt"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('DELETE FROM produkte WHERE "Laufende Nummer"=?', (laufende_nummer,))
                conn.commit()
                logger.info(f"Produkt {laufende_nummer} gelöscht")
        
        except Exception as e:
            logger.error(f"Fehler beim Löschen des Produkts: {e}")
            raise DatabaseError(f"Produkt konnte nicht gelöscht werden: {e}")
    
    def lookup_product_by_wu(self, wu_nummer: str) -> Optional[Dict[str, Any]]:
        """Sucht Produkt nach WU-Nummer"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM produkte WHERE "Produktnummer"=?', (wu_nummer,))
                row = c.fetchone()
                return dict(row) if row else None
        
        except Exception as e:
            logger.error(f"Fehler bei der Produktsuche: {e}")
            return None
    
    def save_position(self, laufende_nummer: int, field: str, value: str) -> bool:
        """Speichert Position für ein Produkt"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Prüfen ob bereits ein Wert vorhanden ist
                c.execute(f'SELECT "{field}" FROM produkte WHERE "Laufende Nummer"=?', (laufende_nummer,))
                existing = c.fetchone()
                
                if existing and existing[0] and existing[0].strip():
                    logger.warning(f"Feld '{field}' für Produkt {laufende_nummer} bereits gesetzt")
                    return False
                
                # Wert speichern
                c.execute(f'UPDATE produkte SET "{field}"=? WHERE "Laufende Nummer"=?', (value, laufende_nummer))
                conn.commit()
                logger.info(f"Position {field} für Produkt {laufende_nummer} gespeichert")
                return True
        
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Position: {e}")
            raise DatabaseError(f"Position konnte nicht gespeichert werden: {e}")
    
    def product_exists(self, laufende_nummer: int) -> bool:
        """Prüft ob Produkt existiert"""
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT 1 FROM produkte WHERE "Laufende Nummer"=?', (laufende_nummer,))
                return c.fetchone() is not None
        
        except Exception as e:
            logger.error(f"Fehler bei der Produktprüfung: {e}")
            return False