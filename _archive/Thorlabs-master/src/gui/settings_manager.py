"""
Settings manager widget for handling camera presets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

import config
from models.camera import CameraSettings


class SettingsManagerWidget(QWidget):
    """
    Displays saved presets and exposes signals for load/save/delete actions.
    """

    presetSaveRequested = Signal(str)
    presetLoadRequested = Signal(str)
    presetDeleteRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None, presets_dir: Optional[Path] = None) -> None:
        super().__init__(parent)
        self._presets_dir = Path(presets_dir or config.PRESETS_DIR)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._list_widget = QListWidget(self)
        self._list_widget.setToolTip("Saved presets on disk. Select to load, delete, or overwrite.")
        layout.addWidget(self._list_widget)

        button_row = QHBoxLayout()
        self._name_input = QLineEdit(self)
        self._name_input.setPlaceholderText("Preset name")
        self._name_input.setToolTip("Name used when saving/loading presets. Accepts alphanumeric characters.")
        self._load_button = QPushButton("Load", self)
        self._save_button = QPushButton("Save", self)
        self._delete_button = QPushButton("Delete", self)
        self._refresh_button = QPushButton("Refresh", self)
        self._load_button.setToolTip("Load the selected or typed preset from disk.")
        self._save_button.setToolTip("Save current camera settings under the typed name.")
        self._delete_button.setToolTip("Delete the selected preset file.")
        self._refresh_button.setToolTip("Re-scan the presets directory for new files.")

        button_row.addWidget(self._name_input, stretch=1)
        for btn in (self._load_button, self._save_button, self._delete_button, self._refresh_button):
            button_row.addWidget(btn)

        layout.addLayout(button_row)

        self._refresh_button.clicked.connect(self.refresh)
        self._load_button.clicked.connect(self._emit_load)
        self._delete_button.clicked.connect(self._emit_delete)
        self._save_button.clicked.connect(self._emit_save)
        self._list_widget.currentTextChanged.connect(self._name_input.setText)

    def refresh(self) -> None:
        """Reload preset list from disk."""
        self._presets_dir.mkdir(exist_ok=True, parents=True)
        self._list_widget.clear()
        for path in sorted(self._presets_dir.glob("*.json")):
            self._list_widget.addItem(path.stem)

    def save_preset(self, name: str, settings: CameraSettings) -> Path:
        """Persist settings to disk immediately."""
        path = self._presets_dir / f"{name}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(settings.to_dict(), handle, indent=2)
        self.refresh()
        return path

    def load_preset(self, name: str) -> Optional[CameraSettings]:
        """Load preset from disk. Returns None if missing."""
        path = self._presets_dir / f"{name}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return CameraSettings.from_dict(data)

    def delete_preset(self, name: str) -> bool:
        """Delete a preset file. Returns True if deleted."""
        path = self._presets_dir / f"{name}.json"
        if not path.exists():
            return False
        path.unlink()
        self.refresh()
        return True

    def _current_selection(self) -> Optional[str]:
        item = self._list_widget.currentItem()
        return item.text() if item else None

    def _emit_load(self) -> None:
        name = self._current_selection() or self._name_input.text().strip()
        if not name:
            self._show_message("Select or enter a preset to load.")
            return
        self.presetLoadRequested.emit(name)

    def _emit_delete(self) -> None:
        name = self._current_selection() or self._name_input.text().strip()
        if not name:
            self._show_message("Select or enter a preset to delete.")
            return
        self.presetDeleteRequested.emit(name)

    def _emit_save(self) -> None:
        name = self._current_selection() or self._name_input.text().strip()
        if not name:
            self._show_message("Enter a preset name before saving.")
            return
        self.presetSaveRequested.emit(name)

    @staticmethod
    def _show_message(text: str) -> None:
        QMessageBox.information(None, "Presets", text)
