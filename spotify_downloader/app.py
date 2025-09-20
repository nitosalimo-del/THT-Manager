"""CustomTkinter based UI for the Spotify downloader."""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .controller import SpotifyDownloaderController
from .exceptions import SpotifyServiceError, ValidationIssue
from .models import Track


class SpotifyDownloaderApp(ctk.CTk):
    """Main application window."""

    def __init__(self, controller: SpotifyDownloaderController) -> None:
        super().__init__()
        self._controller = controller
        self.title("Spotify Playlist Downloader")
        self.geometry("900x640")
        self.minsize(820, 600)

        self._playlist_var = ctk.StringVar()
        self._folder_var = ctk.StringVar()
        self._status_var = ctk.StringVar(value="Bereit")

        self._track_vars: dict[str, ctk.BooleanVar] = {}
        self._tracks: list[Track] = []

        self._create_layout()

    def _create_layout(self) -> None:
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        header.columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Spotify Playlist URL").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkEntry(header, textvariable=self._playlist_var).grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(header, text="Tracks laden", command=self._load_tracks_async).grid(row=0, column=2, padx=10, pady=10)

        ctk.CTkLabel(header, text="Zielordner").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        folder_entry = ctk.CTkEntry(header, textvariable=self._folder_var)
        folder_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(header, text="Durchsuchen", command=self._select_folder).grid(row=1, column=2, padx=10, pady=10)

        action_bar = ctk.CTkFrame(self)
        action_bar.grid(row=2, column=0, padx=20, pady=(10, 0), sticky="ew")
        action_bar.columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(action_bar, text="Alle auswählen", command=lambda: self._toggle_all(True)).grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(action_bar, text="Alle abwählen", command=lambda: self._toggle_all(False)).grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(action_bar, text="Download starten", command=self._start_download_async).grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        self._track_frame = ctk.CTkScrollableFrame(self)
        self._track_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self._track_frame.columnconfigure(0, weight=1)

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        status_frame.columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(status_frame)
        self._progress.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        self._progress.set(0)

        self._status_label = ctk.CTkLabel(status_frame, textvariable=self._status_var, anchor="w")
        self._status_label.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")

    def _select_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self._folder_var.set(folder)

    def _load_tracks_async(self) -> None:
        playlist = self._playlist_var.get().strip()
        if not playlist:
            self._show_validation(ValidationIssue("Bitte Playlist-URL eingeben."))
            return

        thread = threading.Thread(target=self._load_tracks, args=(playlist,), daemon=True)
        thread.start()

    def _load_tracks(self, playlist: str) -> None:
        self._set_busy_state(True)
        try:
            tracks = self._controller.load_tracks(playlist)
        except SpotifyServiceError as exc:
            self._dispatch(lambda: messagebox.showerror("Fehler", str(exc)))
            self._set_busy_state(False)
            return

        self._dispatch(lambda: self._populate_tracks(tracks))
        self._set_busy_state(False)

    def _populate_tracks(self, tracks: list[Track]) -> None:
        for widget in self._track_frame.winfo_children():
            widget.destroy()

        self._tracks = tracks
        self._track_vars.clear()

        if not tracks:
            ctk.CTkLabel(self._track_frame, text="Keine Tracks gefunden.").grid(row=0, column=0, padx=10, pady=10)
            return

        for row_index, track in enumerate(tracks):
            var = ctk.BooleanVar(value=True)
            checkbox = ctk.CTkCheckBox(self._track_frame, text=track.display_name(), variable=var)
            checkbox.grid(row=row_index, column=0, sticky="w", padx=10, pady=5)
            self._track_vars[track.track_id] = var

        self._status_var.set(f"{len(tracks)} Tracks geladen")

    def _start_download_async(self) -> None:
        folder = self._folder_var.get().strip()
        playlist = self._playlist_var.get().strip()
        issues: list[ValidationIssue] = []
        if not playlist:
            issues.append(ValidationIssue("Playlist-URL fehlt"))
        if not folder:
            issues.append(ValidationIssue("Zielordner fehlt"))
        else:
            path = Path(folder)
            if not path.exists():
                issues.append(ValidationIssue("Zielordner existiert nicht", "Bitte zuerst anlegen."))
            elif not path.is_dir():
                issues.append(ValidationIssue("Zielordner ist keine Ordner"))

        if issues:
            self._show_validation(*issues)
            return

        selected_tracks = [track for track in self._tracks if self._track_vars.get(track.track_id, ctk.BooleanVar(value=False)).get()]
        if not selected_tracks:
            self._show_validation(ValidationIssue("Keine Tracks ausgewählt"))
            return

        destination = Path(folder)
        thread = threading.Thread(
            target=self._controller.download_tracks,
            args=(
                selected_tracks,
                destination,
                self._schedule_status_update,
                self._schedule_progress_update,
            ),
            daemon=True,
        )
        thread.start()

    def _schedule_status_update(self, message: str) -> None:
        self._dispatch(lambda: self._status_var.set(message))

    def _schedule_progress_update(self, index: int, total: int, track: Track, detail: str) -> None:
        def update() -> None:
            progress_value = index / total
            self._progress.set(progress_value)
            self._status_var.set(f"{track.display_name()} · {detail}")

        self._dispatch(update)

    def _toggle_all(self, value: bool) -> None:
        for var in self._track_vars.values():
            var.set(value)

    def _dispatch(self, callback) -> None:
        self.after(0, callback)

    def _set_busy_state(self, is_busy: bool) -> None:
        state = "disabled" if is_busy else "normal"
        for child in self.children.values():
            try:
                child.configure(state=state)
            except Exception:
                continue
        if is_busy:
            self._status_var.set("Bitte warten…")
            self._progress.set(0)

    def _show_validation(self, *issues: ValidationIssue) -> None:
        messages = "\n".join(issue.message for issue in issues)
        hints = "\n".join(issue.hint for issue in issues if issue.hint)
        full_message = f"{messages}\n{hints}" if hints else messages
        messagebox.showwarning("Eingabefehler", full_message)
