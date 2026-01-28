"""
Application controller connecting GUI, services, and the camera adapter.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtWidgets import QMessageBox

import config

logger = logging.getLogger(__name__)
from devices.exceptions import CameraConnectionError
from devices.thorlabs_camera import ThorlabsCameraAdapter, setup_dll_path
from gui.main_window import MainWindow
from models.camera import CameraSettings
from models.frame import Frame
from services import (
    AcquisitionThread,
    FocusMetric,
    FrameSaver,
    WhiteBalanceProcessor,
)


class ApplicationController:
    """Coordinates camera hardware, services, and the GUI."""

    def __init__(
        self,
        camera_adapter: Optional[ThorlabsCameraAdapter] = None,
        frame_saver: Optional[FrameSaver] = None,
        white_balance_processor: Optional[WhiteBalanceProcessor] = None,
        focus_metric: Optional[FocusMetric] = None,
        acquisition_thread_factory: Callable[[ThorlabsCameraAdapter], AcquisitionThread]
        = AcquisitionThread,
        main_window: Optional[MainWindow] = None,
        dll_setup: Callable[[Path], None] = setup_dll_path,
    ) -> None:
        self.camera = camera_adapter or ThorlabsCameraAdapter()
        self.frame_saver = frame_saver or FrameSaver(config.SNAPSHOTS_DIR)
        self.white_balance = white_balance_processor or WhiteBalanceProcessor(
            config.DEFAULT_WHITE_BALANCE
        )
        self.focus_metric = focus_metric or FocusMetric()
        self._acquisition_thread_factory = acquisition_thread_factory
        self._dll_setup = dll_setup

        self.main_window = main_window
        self.acquisition_thread: Optional[AcquisitionThread] = None
        self.current_settings: Optional[CameraSettings] = None
        self.latest_frame: Optional[Frame] = None
        self._handling_acquisition_error = False  # Guard against re-entrant error loop

    # ------------------------------------------------------------------ #
    # Initialization / shutdown
    # ------------------------------------------------------------------ #
    def initialize(self) -> bool:
        """Initialize camera, services, and GUI."""
        logger.info("Initializing application controller...")
        try:
            self._dll_setup(config.THORCAM_DLL_PATH)
            logger.info(f"DLL path configured: {config.THORCAM_DLL_PATH}")
        except Exception as exc:
            logger.error(f"DLL setup failed: {exc}", exc_info=True)
            QMessageBox.critical(None, "Initialization Error", str(exc))
            return False

        try:
            serials = self.camera.list_cameras()
            logger.info(f"Found {len(serials)} camera(s): {serials}")
            if not serials:
                raise CameraConnectionError("No Thorlabs cameras detected.")
            capabilities = self.camera.connect(serials[0])
            logger.info(f"Connected to {capabilities.model} (S/N: {capabilities.serial})")
        except Exception as exc:
            logger.error(f"Camera connection failed: {exc}", exc_info=True)
            QMessageBox.critical(None, "Camera Error", str(exc))
            return False

        self.current_settings = self.camera.get_current_settings()
        # white_balance_rgb always has a default value in CameraSettings dataclass
        self.white_balance.set_gains(*self.current_settings.white_balance_rgb)

        self.acquisition_thread = self._acquisition_thread_factory(self.camera)
        self.acquisition_thread.frame_ready.connect(self._on_frame_ready)
        self.acquisition_thread.fps_updated.connect(self._on_fps_update)
        self.acquisition_thread.error.connect(self._on_acquisition_error)

        if self.main_window is None:
            self.main_window = MainWindow()

        self._connect_gui_signals()

        exposure_ms = self.current_settings.exposure_sec * 1000.0
        gain_db = self.current_settings.gain_db
        self.main_window.set_initial_settings(exposure_ms, gain_db)
        self.main_window.white_balance_panel.set_gains(
            *self.current_settings.white_balance_rgb, notify=False
        )
        self.main_window.control_panel.set_live_state(False)
        self.main_window.refresh_presets()
        self.main_window.set_status_message(
            f"Connected to {capabilities.model} ({capabilities.serial})"
        )
        self.main_window.show()
        return True

    def shutdown(self) -> None:
        """Stop services and disconnect camera."""
        logger.info("Shutting down application controller...")
        if self.acquisition_thread:
            logger.info("Stopping acquisition thread...")
            self.acquisition_thread.stop_stream()
        if self.camera.is_connected:
            logger.info("Disconnecting camera...")
            self.camera.disconnect()
        logger.info("Shutdown complete.")

    # ------------------------------------------------------------------ #
    # GUI actions
    # ------------------------------------------------------------------ #
    def _connect_gui_signals(self) -> None:
        assert self.main_window is not None
        cp = self.main_window.control_panel
        cp.exposureChanged.connect(self._on_exposure_changed)
        cp.gainChanged.connect(self._on_gain_changed)
        cp.startRequested.connect(self.start_live)
        cp.stopRequested.connect(self.stop_live)
        cp.snapshotRequested.connect(self.capture_snapshot)

        # Connect MainWindow signals (for keyboard shortcuts)
        self.main_window.startRequested.connect(self.start_live)
        self.main_window.stopRequested.connect(self.stop_live)
        self.main_window.snapshotRequested.connect(self.capture_snapshot)

        self.main_window.white_balance_panel.whiteBalanceChanged.connect(
            self._on_white_balance_changed
        )

        sm = self.main_window.settings_widget
        sm.presetSaveRequested.connect(self._on_save_preset_requested)
        sm.presetLoadRequested.connect(self._on_load_preset_requested)
        sm.presetDeleteRequested.connect(self._on_delete_preset_requested)

    def start_live(self) -> None:
        if not self.current_settings or not self.acquisition_thread:
            logger.warning("start_live called but camera not initialized")
            self.main_window.set_status_message("Camera not initialized.")
            return
        try:
            logger.info("Applying settings and starting acquisition...")
            self.camera.apply_settings(self.current_settings)
            self.acquisition_thread.start_stream()

            # Check if acquisition actually started (signal emitted synchronously if it fails)
            if not self.acquisition_thread.running:
                # Async error path: _on_acquisition_error already set persistent message
                # Just ensure UI state is correct and exit (no status overwrite, no dialog)
                logger.warning("Acquisition failed to start (async error path handled)")
                self.main_window.control_panel.set_live_state(False)
                return

            self.main_window.control_panel.set_live_state(True)
            self.main_window.set_status_message("Live view started.", 1500)
            logger.info("Live view started successfully")
        except Exception as exc:
            # Synchronous error (e.g., apply_settings failed before start_stream)
            logger.error(f"Failed to start live view (sync error): {exc}", exc_info=True)
            self.main_window.set_status_message(f"Failed to start: {exc}")
            # Full cleanup: stop any partial acquisition state
            try:
                self.acquisition_thread.stop_stream()
                logger.info("Cleaned up partial acquisition state")
            except Exception as cleanup_exc:
                logger.error(f"Cleanup failed: {cleanup_exc}", exc_info=True)
            # Ensure UI reflects failure state
            self.main_window.control_panel.set_live_state(False)
            QMessageBox.critical(
                self.main_window,
                "Start Error",
                f"Could not start acquisition.\n\n{exc}"
            )

    def stop_live(self, preserve_status: bool = False) -> None:
        """
        Stop live view acquisition.

        Parameters
        ----------
        preserve_status : bool
            If True, don't overwrite status bar message or FPS (used when stopping due to error).
        """
        if self.acquisition_thread:
            self.acquisition_thread.stop_stream()
        self.main_window.control_panel.set_live_state(False)
        if not preserve_status:
            self.main_window.update_fps(0.0)
            self.main_window.set_status_message("Live view stopped.", 1500)

    def capture_snapshot(self) -> None:
        if self.latest_frame is None:
            logger.warning("Snapshot requested but no frame available")
            self.main_window.set_status_message("No frame available. Start live view first.", 3000)
            return
        try:
            logger.info(f"Capturing snapshot (frame #{self.latest_frame.frame_index})...")
            corrected = self.white_balance.process(self.latest_frame)
            frame = Frame(
                data=corrected,
                timestamp_ns=self.latest_frame.timestamp_ns,
                frame_index=self.latest_frame.frame_index,
                metadata=dict(self.latest_frame.metadata),
            )
            path = self.frame_saver.save_png(frame, autoscale=True)
            logger.info(f"Snapshot saved: {path}")
            self.main_window.set_status_message(f"Snapshot saved: {path.name}", 4000)
        except Exception as exc:
            logger.error(f"Failed to save snapshot: {exc}", exc_info=True)
            self.main_window.set_status_message(f"Save failed: {exc}")
            QMessageBox.critical(
                self.main_window,
                "Snapshot Error",
                f"Could not save frame to disk.\n\n{exc}"
            )

    # ------------------------------------------------------------------ #
    # Signal handlers
    # ------------------------------------------------------------------ #
    def _on_exposure_changed(self, exposure_ms: float) -> None:
        if not self.current_settings:
            return
        self.current_settings.exposure_sec = exposure_ms / 1000.0
        if self.camera.is_acquiring:
            try:
                self.camera.apply_settings(self.current_settings)
                logger.debug(f"Exposure updated: {exposure_ms}ms")
            except Exception as exc:
                logger.error(f"Failed to apply exposure {exposure_ms}ms: {exc}", exc_info=True)
                self.main_window.set_status_message(f"Failed to apply exposure: {exc}")

    def _on_gain_changed(self, gain_db: float) -> None:
        if not self.current_settings:
            return
        self.current_settings.gain_db = gain_db
        if self.camera.is_acquiring:
            try:
                self.camera.apply_settings(self.current_settings)
                logger.debug(f"Gain updated: {gain_db}dB")
            except Exception as exc:
                logger.error(f"Failed to apply gain {gain_db}dB: {exc}", exc_info=True)
                self.main_window.set_status_message(f"Failed to apply gain: {exc}")

    def _on_white_balance_changed(self, r: float, g: float, b: float) -> None:
        if not self.current_settings:
            return
        self.current_settings.white_balance_rgb = (r, g, b)
        self.white_balance.set_gains(r, g, b)

    def _on_save_preset_requested(self, name: str) -> None:
        if not self.current_settings:
            logger.warning("Save preset requested but no settings available")
            self.main_window.set_status_message("No settings to save.")
            return
        try:
            logger.info(f"Saving preset '{name}'...")
            self.main_window.settings_widget.save_preset(name, self.current_settings)
            logger.info(f"Preset '{name}' saved successfully")
            self.main_window.set_status_message(f"Preset '{name}' saved.", 3000)
        except Exception as exc:
            logger.error(f"Failed to save preset '{name}': {exc}", exc_info=True)
            self.main_window.set_status_message(f"Save failed: {exc}")
            QMessageBox.critical(
                self.main_window,
                "Save Preset Error",
                f"Could not save preset '{name}'.\n\n{exc}"
            )

    def _on_load_preset_requested(self, name: str) -> None:
        try:
            logger.info(f"Loading preset '{name}'...")
            settings = self.main_window.settings_widget.load_preset(name)
            if settings is None:
                logger.warning(f"Preset '{name}' not found")
                self.main_window.set_status_message(f"Preset '{name}' not found.", 3000)
                return
            self.apply_settings(settings)
            logger.info(f"Preset '{name}' loaded successfully")
            self.main_window.set_status_message(f"Preset '{name}' loaded.", 3000)
        except Exception as exc:
            logger.error(f"Failed to load preset '{name}': {exc}", exc_info=True)
            self.main_window.set_status_message(f"Load failed: {exc}")
            QMessageBox.critical(
                self.main_window,
                "Load Preset Error",
                f"Could not load preset '{name}'.\n\n{exc}"
            )

    def _on_delete_preset_requested(self, name: str) -> None:
        try:
            logger.info(f"Deleting preset '{name}'...")
            if self.main_window.settings_widget.delete_preset(name):
                logger.info(f"Preset '{name}' deleted")
                self.main_window.set_status_message(f"Preset '{name}' deleted.", 3000)
            else:
                logger.warning(f"Preset '{name}' not found for deletion")
                self.main_window.set_status_message(f"Preset '{name}' not found.", 3000)
        except Exception as exc:
            logger.error(f"Failed to delete preset '{name}': {exc}", exc_info=True)
            self.main_window.set_status_message(f"Delete failed: {exc}")
            QMessageBox.critical(
                self.main_window,
                "Delete Preset Error",
                f"Could not delete preset '{name}'.\n\n{exc}"
            )

    def _on_frame_ready(self, frame: Frame) -> None:
        self.latest_frame = frame
        corrected = self.white_balance.process(frame)
        display_frame = Frame(
            data=corrected,
            timestamp_ns=frame.timestamp_ns,
            frame_index=frame.frame_index,
            metadata=dict(frame.metadata),
        )
        self.main_window.display_frame(display_frame)
        focus_score = self.focus_metric.compute(corrected)
        self.main_window.update_focus_score(focus_score)

    def _on_fps_update(self, fps: float) -> None:
        self.main_window.update_fps(fps)

    def _on_acquisition_error(self, message: str) -> None:
        # Guard against re-entrant calls (e.g., stop_acquisition() itself throws)
        if self._handling_acquisition_error:
            logger.warning(f"Ignoring re-entrant acquisition error: {message}")
            return

        self._handling_acquisition_error = True
        try:
            logger.error(f"Acquisition error reported by hardware layer: {message}")
            # Set persistent error message (no timeout, no overwrite)
            self.main_window.set_status_message(f"ACQUISITION ERROR: {message}", timeout_ms=0)
            QMessageBox.critical(self.main_window, "Acquisition Error", message)
            # Stop but preserve the error status message
            self.stop_live(preserve_status=True)
        finally:
            self._handling_acquisition_error = False

    # ------------------------------------------------------------------ #
    def apply_settings(self, settings: CameraSettings) -> None:
        """Apply programmatic settings (e.g., from presets)."""
        logger.info(f"Applying settings: exp={settings.exposure_sec}s, gain={settings.gain_db}dB, wb={settings.white_balance_rgb}")
        self.current_settings = settings
        try:
            self.camera.apply_settings(settings)
            logger.info("Settings applied to camera successfully")
        except Exception as exc:
            logger.error(f"Failed to apply settings to camera: {exc}", exc_info=True)
            self.main_window.set_status_message(f"Failed to apply settings to camera: {exc}")
            QMessageBox.warning(
                self.main_window,
                "Settings Warning",
                f"Settings applied to UI but camera reported error:\n\n{exc}"
            )
        exposure_ms = settings.exposure_sec * 1000.0
        self.main_window.control_panel.set_exposure(exposure_ms)
        self.main_window.control_panel.set_gain(settings.gain_db)
        self.main_window.white_balance_panel.set_gains(
            *settings.white_balance_rgb, notify=False
        )
        self.white_balance.set_gains(*settings.white_balance_rgb)

