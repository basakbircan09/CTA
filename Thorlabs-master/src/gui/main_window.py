"""
Main application window integrating camera controls and live view.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gui.camera_controls import CameraControlPanel
from gui.focus_assistant import FocusAssistantWidget
from gui.live_view import LiveViewWidget
from gui.settings_manager import SettingsManagerWidget
from gui.white_balance_panel import WhiteBalancePanel
from models.frame import Frame


class MainWindow(QMainWindow):
    """
    Composes the application UI and re-emits user interaction signals.
    """

    exposureChanged = Signal(float)
    gainChanged = Signal(float)
    startRequested = Signal()
    stopRequested = Signal()
    snapshotRequested = Signal()
    whiteBalanceChanged = Signal(float, float, float)
    savePresetRequested = Signal(str)
    loadPresetRequested = Signal(str)
    deletePresetRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thorlabs Camera")
        self.resize(1200, 800)

        self.live_view = LiveViewWidget(self)
        self.control_panel = CameraControlPanel(self)
        self.white_balance_panel = WhiteBalancePanel(self)
        self.focus_widget = FocusAssistantWidget(self)
        self.settings_widget = SettingsManagerWidget(self)
        self.settings_widget.setVisible(False)  # Hidden during early development

        self._build_layout()
        self._connect_signals()
        self._setup_shortcuts()

    def _build_layout(self) -> None:
        central = QWidget(self)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Use QSplitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Live view (takes most space)
        splitter.addWidget(self.live_view)

        # Right side: Control panels in a container
        controls_container = QWidget()
        # Note: No minimum width set - allows collapse for focus on imaging
        side_column = QVBoxLayout(controls_container)
        side_column.setContentsMargins(0, 0, 0, 0)
        side_column.addWidget(self.control_panel)
        side_column.addWidget(self.white_balance_panel)
        side_column.addWidget(self.focus_widget)
        side_column.addWidget(self.settings_widget)  # Hidden by default (line 52)
        side_column.addStretch(1)

        splitter.addWidget(controls_container)
        # Allow controls to collapse completely for full-screen imaging view

        # Set initial proportions: 75% live view, 25% controls
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setCentralWidget(central)

        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        self._record_button = QPushButton("Start Recording", self)
        self._record_button.setEnabled(False)  # Placeholder for future feature
        self._record_button.setToolTip("Reserved for future recording support.")
        status_bar.addPermanentWidget(self._record_button)

    def _connect_signals(self) -> None:
        self.control_panel.exposureChanged.connect(self.exposureChanged)
        self.control_panel.gainChanged.connect(self.gainChanged)
        self.control_panel.startRequested.connect(self.startRequested)
        self.control_panel.stopRequested.connect(self.stopRequested)
        self.control_panel.snapshotRequested.connect(self.snapshotRequested)

        self.white_balance_panel.whiteBalanceChanged.connect(self.whiteBalanceChanged)

        self.settings_widget.presetSaveRequested.connect(self.savePresetRequested)
        self.settings_widget.presetLoadRequested.connect(self.loadPresetRequested)
        self.settings_widget.presetDeleteRequested.connect(self.deletePresetRequested)

    def _setup_shortcuts(self) -> None:
        """Configure keyboard shortcuts for common operations."""
        # Store splitter reference for toggle
        self._splitter = self.centralWidget().findChild(QSplitter)
        self._controls_visible = True

        # Space: Toggle Start/Stop live view
        toggle_live_action = QAction("Toggle Live View", self)
        toggle_live_action.setShortcut(QKeySequence(Qt.Key_Space))
        toggle_live_action.setShortcutContext(Qt.ApplicationShortcut)
        toggle_live_action.triggered.connect(self._toggle_live_view)
        self.addAction(toggle_live_action)

        # Ctrl+S: Capture snapshot
        snapshot_action = QAction("Capture Snapshot", self)
        snapshot_action.setShortcut(QKeySequence.Save)  # Ctrl+S
        snapshot_action.setShortcutContext(Qt.ApplicationShortcut)
        snapshot_action.triggered.connect(self.snapshotRequested)
        self.addAction(snapshot_action)

        # Ctrl+H: Toggle controls panel (H for Hide)
        toggle_controls_action = QAction("Toggle Controls Panel", self)
        toggle_controls_action.setShortcut(QKeySequence("Ctrl+H"))
        toggle_controls_action.setShortcutContext(Qt.ApplicationShortcut)
        toggle_controls_action.triggered.connect(self._toggle_controls_panel)
        self.addAction(toggle_controls_action)

        # Ctrl+Q: Quit application
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.setShortcutContext(Qt.ApplicationShortcut)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

        # F1 (or Shift+F1): Show quick help
        help_action = QAction("Show Help", self)
        help_action.setShortcut(QKeySequence.HelpContents)
        help_action.setShortcutContext(Qt.ApplicationShortcut)
        help_action.triggered.connect(self._show_help)
        self.addAction(help_action)

    def _toggle_live_view(self) -> None:
        """Toggle between start and stop live view based on current state."""
        if self.control_panel.is_live():
            self.stopRequested.emit()
        else:
            self.startRequested.emit()

    def _toggle_controls_panel(self) -> None:
        """Toggle visibility of controls panel for full-screen imaging."""
        if self._splitter is None:
            return

        if self._controls_visible:
            # Hide controls - collapse to zero
            self._splitter.setSizes([self._splitter.width(), 0])
            self._controls_visible = False
            self.set_status_message("Controls hidden (Ctrl+H to restore)", 2000)
        else:
            # Restore controls - 75/25 split
            total = self._splitter.width()
            self._splitter.setSizes([int(total * 0.75), int(total * 0.25)])
            self._controls_visible = True
            self.set_status_message("Controls restored", 2000)

    # ------------------------------------------------------------------ #
    # External API
    # ------------------------------------------------------------------ #
    def display_frame(self, frame: Frame) -> None:
        """Forward frames to the live view widget."""
        self.live_view.update_frame(frame)

    def update_focus_score(self, score: float) -> None:
        self.focus_widget.update_score(score)

    def set_status_message(self, text: str, timeout_ms: int = 3000) -> None:
        if self.statusBar():
            self.statusBar().showMessage(text, timeout_ms)

    def update_fps(self, fps: float) -> None:
        self.set_status_message(f"Live FPS: {fps:.1f}", timeout_ms=1500)

    def set_initial_settings(self, exposure_ms: float, gain_db: float) -> None:
        self.control_panel.set_exposure(exposure_ms)
        self.control_panel.set_gain(gain_db)

    def refresh_presets(self) -> None:
        self.settings_widget.refresh()

    # ------------------------------------------------------------------ #
    # Help / guidance
    # ------------------------------------------------------------------ #
    def _show_help(self) -> None:
        """Display quick reference help text."""
        help_text = (
            "<b>Live View</b>: Press Space or click Start/Stop to toggle streaming.<br>"
            "<b>Exposure & Gain</b>: Use the spin boxes for precise values; the slider offers coarse exposure control.<br>"
            "<b>White Balance</b>: Pick a preset or fine-tune RGB gains. Reset restores the default (1.0, 1.0, 1.0).<br>"
            "<b>Focus Assistant</b>: Aim for the highest score while adjusting the lens.<br>"
            "<b>Snapshot</b>: Press Ctrl+S or click Snapshot to save the current frame.<br>"
            "<b>Presets</b>: Use the presets panel to load/save/delete JSON profiles. Toggle controls with Ctrl+H.<br>"
            "<b>Shortcuts</b>: Space (toggle live), Ctrl+S (snapshot), Ctrl+H (toggle controls), Ctrl+Q (quit), F1 (help)."
        )
        QMessageBox.information(self, "Quick Help", help_text)


