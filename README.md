# THT-Manager

Überblick über die Codebasis

Die Anwendung ist ein THT‑Produktmanager mit einer grafischen Oberfläche (GUI) zur Verwaltung von Produktdaten, Kommunikation mit externer Hardware (z. B. LIMA, Cobot) und Datenbank‑Anbindung. Die wichtigsten Module und ihr Zusammenspiel:
1. config.py

    Zentrale Konfigurationsklasse Config: Datenbankname, Standardwerte für LIMA‑Verbindungen, UI‑Größe, Logging‑Einstellungen und Listen aller Datenbankfelder.

    Methode get_all_fields() liefert die Reihenfolge der Felder für Formulare und die Datenbank.

2. exceptions.py

    Definiert projektspezifische Fehlerklassen (DatabaseError, CommunicationError, ValidationError usw.), von denen alle anderen Module erben können.

3. validation.py

    Enthält Validator: statische Methoden zur Prüfung von IPs, Ports, Produktnummern, Pflichtfeldern, numerischen Eingaben und LIMA‑Konfigurationen.

4. database_manager.py

    Klasse DatabaseManager steuert alle SQLite‑Operationen: Initialisierung, Einfügen/Ändern/Löschen von Produkten, Positionsspeicherung und Nachschlagen per WU‑Nummer.

    Nutzt Config für Feldnamen und Validator für Eingabekontrollen.

5. communication_manager.py

    Mehrere Klassen für Netzkommunikation via Sockets:

        LimaClient: Grundkommunikation mit LIMA.

        RobotCommunicator: nutzt LimaClient, um Autofokus, Trigger oder Positionsdaten abzufragen.

        ListenerMode: TCP‑Server, der externe Nachrichten annimmt und weiterleitet.

        CobotCommunicator: sendet Daten oder Befehle an einen Cobot.

    Wichtig zum Verständnis: asynchrone Kommunikation, Timeouts, Fehlerbehandlung.

6. thread_manager.py

    Klasse ThreadManager: startet/überwacht Threads.

    SafeTimer: wiederholte Ausführung mit Thread‑Sicherheit.

    TaskQueue: verwaltet Aufgaben über einen ThreadPoolExecutor.

7. ui_manager.py

    Mehrere UI‑Komponenten auf Basis von CustomTkinter:

        FormManager: erzeugt das scrollbare Formular für Produktdaten.

        SidebarManager: rechtsseitige Steuerleiste (Login, Listener‑Knöpfe, Produktliste).

        StatusManager: Statusanzeigen für LIMA/Listener.

        MessageHandler: Popup‑Dialogs (Info, Warnung, Fehler).

    Alle Widgets werden zentral verwaltet; Methoden aktivieren/deaktivieren Eingabefelder oder füllen Listen.

8. main.py

    Einstiegspunkt (main()), erzeugt ProduktManagerApp (eine ctk.CTk‑Klasse).

    Initialisiert Logging, Datenbank, ThreadManager, MessageHandler, UI‑Manager und Kommunikationsobjekte.

    Enthält umfangreiche Methoden zum:

        Admin‑Login/Logout

        Laden/Speichern von Produkten

        Listener‑Start/Stopp

        LIMA‑ und Autofokus‑Funktionen

        UI‑Updates und Programmende (Cleanup).


Eine Software Anleitung für den Endutzer befindet sich in Arbeit. 


🦾 RTDE-Integration (UR Cobot)

Ab Version 2.0 unterstützt der THT-Manager die direkte Abfrage der aktuellen TCP-Pose des UR-Cobots über das RTDE-Protokoll (Port 30004).

🔧 Funktionsweise

Die Cobot-IP wird aus dem Feld „Cobot IP (Send)“ übernommen.

Der Cobot Port (Send) bleibt frei wählbar für andere Funktionen.

Der RTDE-Port (30004) wird im LIMA-Panel als Hinweis angezeigt und ist fest vorgegeben.

Beim Klick auf „Abrufen“ neben den Feldern PosPCB_0 … PosPCB_4 wird die aktuelle Pose des Roboters gelesen.

📋 Gespeicherte Daten

Pose-Vektor im UR-Format:

p[x, y, z, rx, ry, rz]

Position in Metern

Orientierung in Radiant

Die Pose wird automatisch:

in das jeweilige Eingabefeld im Formular geschrieben

zusammen mit einem Zeitstempel in der Datenbank gespeichert

✅ Vorteile

Kein manuelles Copy-Paste der Roboter-Pose mehr nötig

Einheitliche Datenbasis direkt im Produktdatensatz

Robuste Verbindung durch RTDE-Handshake (Protokoll v2 → v1 Fallback)


