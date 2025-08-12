# THT-Manager

Überblick über die Codebasis

Die Anwendung ist ein THT‑Produktmanager mit einer grafischen Oberfläche (GUI) zur Verwaltung von Produktdaten, Kommunikation mit externer Hardware (z. B. LIMA, Cobot) und Datenbank‑Anbindung. Die wichtigsten Module und ihr Zusammenspiel:
1. config.py

    Zentrale Konfigurationsklasse Config: Datenbankname, Standardwerte für LIMA‑Verbindungen, UI‑Größe, Logging‑Einstellungen und Listen aller Datenbankfelder.

    Methode get_all_fields() liefert die Reihenfolge der Felder für Formulare und die Datenbank.

2. exceptions.py / exeptions.py

    Definiert projektspezifische Fehlerklassen (DatabaseError, CommunicationError, ValidationError usw.), von denen alle anderen Module erben können.

    (Es gibt zwei nahezu identische Dateien – Tippfehler im Namen. Zum Lernen reicht eine.)

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

    WorkerQueue: einfache, thread‑sichere Aufgabenwarteschlange.

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

Wichtige Lerninhalte für Anfänger

    Python‑Grundlagen und OOP
    Klassen, Vererbung, Module, Ausnahmebehandlung.

    GUI‑Programmierung
    CustomTkinter (auf Tkinter basierend): Widgets, Events, Layouts, Zustandswechsel von Controls.

    Datenvalidierung und Fehlerbehandlung
    Eigene Exceptions, Validator‑Methoden, sinnvolle Fehlermeldungen.

    SQLite‑Datenbank
    Erstellen/Abfragen/Aktualisieren von Tabellen, Kontextmanager für sichere Verbindungen.

    Netzwerkkommunikation
    Socket‑Programmierung für Client/Server, Timeouts, Senden und Empfangen von Daten.

    Nebenläufigkeit
    Threads, Timer und Worker‑Queues zur Abwicklung langer oder wiederholter Aufgaben ohne Blockieren der GUI.

    Logging
    Protokollierung von Ereignissen (Fehler, Aktionen) zur Analyse und Fehlersuche.

Einstiegsempfehlung

    config.py – verstehen, welche Felder und Einstellungen existieren.

    main.py (oberer Bereich) – Einstiegspunkt, wie Komponenten zusammenkommen.

    ui_manager.py – einfache GUI‑Logik studieren und anpassen.

    database_manager.py und validation.py – Datenfluss von Formular → Validierung → Datenbank.

    communication_manager.py & thread_manager.py – später ansehen, wenn Netzwerk‑ und Threading‑Grundlagen sitzen.

Mit diesem Überblick kann ein Anfänger Schritt für Schritt die einzelnen Teile kennenlernen und erweitern.
