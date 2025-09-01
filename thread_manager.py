"""
Thread-Management für den THT-Produktmanager
"""
import threading
import logging
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class ThreadManager:
    """Verwaltet alle Threads der Anwendung"""
    
    def __init__(self):
        self.threads: List[threading.Thread] = []
        self._lock = threading.Lock()
    
    def start_thread(self, 
                    target: Callable,
                    name: Optional[str] = None,
                    daemon: bool = True,
                    args: tuple = (),
                    kwargs: dict = None) -> threading.Thread:
        """Startet einen neuen Thread und verwaltet ihn"""
        if kwargs is None:
            kwargs = {}
        
        with self._lock:
            thread = threading.Thread(
                target=self._thread_wrapper,
                name=name,
                daemon=daemon,
                args=(target, args, kwargs)
            )
            thread.start()
            self.threads.append(thread)
            logger.info(f"Thread gestartet: {name or thread.name}")
            return thread
    
    def _thread_wrapper(self, target: Callable, args: tuple, kwargs: dict):
        """Wrapper für Thread-Funktionen mit Exception-Handling"""
        thread_name = threading.current_thread().name
        try:
            logger.debug(f"Thread {thread_name} gestartet")
            target(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fehler in Thread {thread_name}: {e}", exc_info=True)
        finally:
            logger.debug(f"Thread {thread_name} beendet")
    
    def stop_all_threads(self, timeout: float = 2.0) -> None:
        """Stoppt alle verwalteten Threads"""
        with self._lock:
            active_threads = [t for t in self.threads if t.is_alive()]
            
            if not active_threads:
                return
            
            logger.info(f"Stoppe {len(active_threads)} aktive Threads...")
            
            for thread in active_threads:
                if thread.is_alive():
                    thread.join(timeout=timeout)
                    if thread.is_alive():
                        logger.warning(f"Thread {thread.name} konnte nicht gestoppt werden")
                    else:
                        logger.debug(f"Thread {thread.name} erfolgreich gestoppt")
            
            # Liste der Threads bereinigen
            self.threads = [t for t in self.threads if t.is_alive()]

    def shutdown(self) -> None:
        """Kompatibilitätsmethode zum Beenden aller Threads"""
        self.stop_all_threads()
    
    def get_active_threads(self) -> List[threading.Thread]:
        """Gibt alle aktiven Threads zurück"""
        with self._lock:
            return [t for t in self.threads if t.is_alive()]
    
    def cleanup_finished_threads(self) -> None:
        """Entfernt beendete Threads aus der Verwaltung"""
        with self._lock:
            before_count = len(self.threads)
            self.threads = [t for t in self.threads if t.is_alive()]
            after_count = len(self.threads)
            
            if before_count != after_count:
                logger.debug(f"{before_count - after_count} beendete Threads bereinigt")
    
    @contextmanager
    def managed_thread(self, 
                      target: Callable,
                      name: Optional[str] = None,
                      daemon: bool = True,
                      args: tuple = (),
                      kwargs: dict = None):
        """Context Manager für automatisches Thread-Management"""
        thread = self.start_thread(target, name, daemon, args, kwargs)
        try:
            yield thread
        finally:
            if thread.is_alive():
                thread.join(timeout=1.0)
                if thread.is_alive():
                    logger.warning(f"Thread {thread.name} läuft noch nach Context-Exit")

class SafeTimer:
    """Thread-sichere Timer-Implementierung"""
    
    def __init__(self, interval: float, callback: Callable, *args, **kwargs):
        self.interval = interval
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._running = False
    
    def start(self) -> None:
        """Startet den Timer"""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._schedule_next()
    
    def stop(self) -> None:
        """Stoppt den Timer"""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
    
    def _schedule_next(self) -> None:
        """Plant die nächste Timer-Ausführung"""
        if not self._running:
            return
        
        self._timer = threading.Timer(self.interval, self._execute)
        self._timer.daemon = True
        self._timer.start()
    
    def _execute(self) -> None:
        """Führt den Callback aus und plant die nächste Ausführung"""
        try:
            self.callback(*self.args, **self.kwargs)
        except Exception as e:
            logger.error(f"Fehler in Timer-Callback: {e}")
        finally:
            with self._lock:
                if self._running:
                    self._schedule_next()

class TaskQueue:
    """Einfache Aufgabenverwaltung auf Basis von ThreadPoolExecutor"""

    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, func: Callable, *args, **kwargs) -> None:
        """Übermittelt eine Aufgabe zur asynchronen Ausführung"""

        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Fehler in Worker-Task: {e}")

        self._executor.submit(wrapper)

    def shutdown(self, wait: bool = True) -> None:
        """Fährt den Executor kontrolliert herunter"""
        self._executor.shutdown(wait=wait)
        logger.info("TaskQueue heruntergefahren")
