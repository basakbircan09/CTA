"""
GOED GUI Application v3 - Modular Architecture with Full v2 Parity

Main operator dashboard with decomposed architecture.
Uses separate executors for sequence logic while keeping full v2 UI and handlers.

Layout matches docs/assets/generalGUI.jpg:
- Top: Navigation bar (session controls, mode selector, per-device dropdowns)
- Left: Sequence manager + Device control tabs
- Center: Live Run plots/logs OR Sequence Builder
- Right: (merged into left device tabs)
"""

import sys
import os
import logging
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QSplitter, QMessageBox, QPushButton, QComboBox,
    QStackedWidget, QToolBar, QTabWidget, QFileDialog, QMenu, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QThread
from PySide6.QtGui import QFont, QAction, QTextCursor

from supervisor.supervisor_service import SupervisorService
from config.config_loader import ConfigLoader
from supervisor.command_dispatcher import CommandDispatcher
from devices import DeviceRegistry, ThorlabsWrapperDevice, PIWrapperDevice, GamryDevice, PerimaxWrapperDevice, ForceWrapperDevice
from sequence.action_mapper import DEFAULT_TIMEOUTS
from sequence.sequence_worker import SequenceWorker
from diagnostics.error_classifier import classify_error, ErrorSeverity, RecoveryAction
from sequence.sequence_validator import validate_sequence

# Import widgets
from widgets.sequence_table_widget import SequenceTableWidget
from widgets.log_widget import LogWidget
from widgets.ec_plot_widget import ECPlotWidget as PlotWidget
from widgets.warning_bar import WarningBar
from widgets.splash_screen import InitializationResult
from widgets.hardware_status_bar import HardwareStatusBar
from widgets.collapsible_splitter import CollapsibleSplitter, CollapseButton
from utils.vocv_detector import VocvBuffer

# Import device panels
from gui.panels.pi_control_panel import PIControlPanel
from gui.panels.gamry_control_panel_v2 import GamryControlPanel
from gui.panels.thorlabs_control_panel_v2 import ThorlabsControlPanelV2
from gui.panels.perimax_control_panel import PerimaxControlPanel
from gui.panels.force_control_panel import ForceControlPanel

# Import executors
from executors.gamry_sequence_executor import GamrySequenceExecutor
from executors.mixed_sequence_executor import MixedSequenceExecutor
from executors.array_mode_executor import ArrayModeExecutor

# Import utilities
from utils.gamry_param_normalizer import normalize_gamry_params, calculate_technique_timeout
from utils.export_helpers import (
    extract_artifacts_from_result,
    generate_sequence_exports,
    write_gamry_sequence_manifest,
    write_mixed_sequence_manifest,
    write_pi_step_artifact
)
from utils.event_logger import event_log
from utils.resource_monitor import ResourceMonitor

# Long-run reliability support (Phase 8+)
from policies.long_run_policy import LongRunPolicy

from models.array_models import ArrayRunPhase, ArraySequenceConfig

logger = logging.getLogger(__name__)


class GOEDMainWindowV3(QMainWindow):
    """Main application window with full v2 parity.

    This version includes all v2 functionality:
    - Full toolbar with per-device dropdown controls
    - Complete layout with Vocv status bar
    - All supervisor and dispatcher signal handlers
    - Streaming data and VOCV estimation
    - Reliability event handlers (auto-restart)
    """

    # Cross-thread signals (from v2)
    _mixed_pi_step_done = Signal(bool, str)  # success, error_msg
    _array_pi_step_done = Signal(bool, str)  # success, error_msg
    _device_state_for_array = Signal()  # device thread -> GUI thread

    def __init__(
        self,
        supervisor_service: Optional[SupervisorService] = None,
        init_result: Optional[InitializationResult] = None
    ):
        super().__init__()
        self.setWindowTitle("GOED - Orchestrator Dashboard v3")
        self.setMinimumSize(1400, 900)

        # Store initialization result for warning display
        self._init_result = init_result
        self._failed_devices = set(init_result.failed_devices) if init_result else set()

        # Repo root
        self.repo_root = Path(__file__).resolve().parents[2]
        env_config = os.environ.get("GOED_CONFIG_PATH")
        self.config_path = Path(env_config) if env_config else (self.repo_root / "config" / "device_paths.yaml")

        # Gamry controller disabled in 3.13 (ToolkitPy is 3.7/32-bit). Use wrapper sidecar always.
        self.gamry_controller = None

        # Supervisor service - either from splash screen or create new
        if supervisor_service:
            self.supervisor_service = supervisor_service
            logger.info("Using supervisor service from splash screen initialization")
        else:
            self.supervisor_service = SupervisorService(self.config_path)
            self.supervisor_service.start()
            logger.info("Created new supervisor service (no splash screen)")

        # Device Abstraction Layer
        self.device_registry = DeviceRegistry()

        # Load device config for wrapper configuration
        self._device_config = self._load_device_config()

        # Initialize devices (from v2 lines 1153-1196)
        self._init_devices()

        # Bridge device registry to supervisor for circuit breaker status (Phase 2: Reliability)
        self.supervisor_service.set_device_registry(self.device_registry)

        # Connect supervisor signals (from v2 lines 1198-1209)
        self.supervisor_service.status_updated.connect(self._on_status_updated)
        self.supervisor_service.command_completed.connect(self._on_command_completed)
        self.supervisor_service.error_occurred.connect(self._on_error)
        self.supervisor_service.capabilities_updated.connect(self._on_capabilities_updated)

        # Reliability signals (auto-restart notifications)
        self.supervisor_service.restart_started.connect(self._on_restart_started)
        self.supervisor_service.restart_completed.connect(self._on_restart_completed)
        self.supervisor_service.max_restarts_reached.connect(self._on_max_restarts_reached)
        self.supervisor_service.operator_confirmation_needed.connect(self._on_operator_confirmation_needed)
        self.supervisor_service.device_recovered.connect(self._on_device_recovered)
        self.supervisor_service.hardware_disconnected.connect(self._on_hardware_disconnected)
        self.supervisor_service.command_stuck.connect(self._on_command_stuck)

        # Command dispatcher (from v2 lines 1211-1221)
        self.command_dispatcher = CommandDispatcher(
            config_path=self.config_path,
            supervisor_service=self.supervisor_service,
            parent=self
        )
        self.command_dispatcher.command_started.connect(self._on_command_started)
        self.command_dispatcher.command_completed.connect(self._on_command_completed_dispatcher)
        self.command_dispatcher.command_failed.connect(self._on_command_failed_dispatcher)
        self.command_dispatcher.command_interrupted.connect(self._on_command_interrupted_dispatcher)
        self.command_dispatcher.data_point_received.connect(self._on_streaming_data_point)

        # Cross-thread signal connections (from v2 lines 1223-1227)
        self._mixed_pi_step_done.connect(self._on_mixed_step_completed)
        self._device_state_for_array.connect(self._update_array_device_status)

        # Sequence worker (from v2 lines 1229-1235)
        self.sequence_worker: Optional[SequenceWorker] = None
        self.current_manifest_path: Optional[Path] = None
        self.is_adhoc_sequence: bool = False
        self.active_command_panel: Optional[object] = None
        self.selected_sequence_path: Optional[Path] = None  # Legacy - toolbar sequence removed in v3.1
        self.current_temp_sequence: Optional[str] = None
        self._sequence_running: bool = False  # Track sequence state internally

        # Manifest refresh timer (from v2 lines 1237-1240)
        self.manifest_timer = QTimer()
        self.manifest_timer.timeout.connect(self._refresh_manifest_view)
        self.manifest_timer.setInterval(500)

        # Vocv buffer for live estimation (from v2 lines 1242-1245)
        self._vocv_buffer = VocvBuffer()
        self._vocv_update_counter = 0
        self._current_technique = None
        self._pending_target_cycles = 0  # For cycle indicator display

        # Resource monitor for long-running operations (Phase 3A: Reliability)
        self._resource_monitor = ResourceMonitor(
            warning_mb=1024,   # 1GB warning
            critical_mb=2048,  # 2GB critical
            disk_warning_gb=1.0,
            check_interval_s=30.0,
            parent=self
        )
        self._resource_monitor.memory_warning.connect(self._on_memory_warning)
        self._resource_monitor.memory_critical.connect(self._on_memory_critical)
        self._resource_monitor.disk_warning.connect(self._on_disk_warning)

        # Long-run policy for configurable behavior (Phase 8+ Reliability)
        # Uses default policy - can be changed via set_long_run_policy() or presets
        self._long_run_policy = LongRunPolicy.default()

        # Create UI
        self._create_menu_bar()
        self._create_toolbar()
        self._create_main_layout()
        self._set_sequence_controls_running(False)

        # Create executors
        self._create_executors()

        # Explicit array run flag (like v2 - independent of executor state)
        self._array_run_active = False

        # Status bar
        self.statusBar().showMessage("GOED Ready")

        # Show initialization warnings after UI is ready
        if self._init_result and self._init_result.warnings:
            QTimer.singleShot(500, self._show_initialization_warnings)

        # Start resource monitoring
        self._resource_monitor.set_disk_path(str(self.repo_root / "runs"))
        self._resource_monitor.start()
        logger.info("Resource monitor started")

    def _load_device_config(self) -> dict:
        """Load device configuration."""
        try:
            return ConfigLoader(str(self.config_path)).load()
        except Exception as e:
            logger.warning(f"Failed to load device config: {e}")
            return {}

    def _init_devices(self):
        """Initialize device wrappers (from v2 lines 1153-1196)."""
        # Thorlabs
        thorlabs_config = self._device_config.get("thorlabs", {})
        if thorlabs_config and "thorlabs" not in self._failed_devices:
            self._thorlabs_device = ThorlabsWrapperDevice(
                thorlabs_config, supervisor_service=self.supervisor_service
            )
            logger.info("Thorlabs: Using wrapper device for process isolation")
        else:
            self._thorlabs_device = None
            if "thorlabs" in self._failed_devices:
                logger.warning("Thorlabs: Wrapper failed during initialization")
            else:
                logger.warning("Thorlabs: No wrapper config found, device not available")
        if self._thorlabs_device:
            self.device_registry.register(self._thorlabs_device)

        # PI XYZ
        pi_config = self._device_config.get("pi_xyz", {})
        if pi_config and "pi_xyz" not in self._failed_devices:
            self._pi_device = PIWrapperDevice(
                pi_config, supervisor_service=self.supervisor_service
            )
            logger.info("PI XYZ: Using wrapper device for process isolation")
        else:
            self._pi_device = None
            if "pi_xyz" in self._failed_devices:
                logger.warning("PI XYZ: Wrapper failed during initialization")
            else:
                logger.warning("PI XYZ: No wrapper config found, device not available")
        if self._pi_device:
            self.device_registry.register(self._pi_device)

        # Gamry
        gamry_config = self._device_config.get("gamry", {})
        if gamry_config and "gamry" not in self._failed_devices:
            self._gamry_device = GamryDevice(
                gamry_config, supervisor_service=self.supervisor_service
            )
            logger.info("Gamry: Using wrapper device for Python 3.7-32bit isolation")
        else:
            self._gamry_device = None
            if "gamry" in self._failed_devices:
                logger.warning("Gamry: Wrapper failed during initialization")
            else:
                logger.warning("Gamry: No wrapper config found, device not available")
        if self._gamry_device:
            self.device_registry.register(self._gamry_device)

        # Perimax
        perimax_config = self._device_config.get("perimax", {})
        if perimax_config and "perimax" not in self._failed_devices:
            self._perimax_device = PerimaxWrapperDevice(
                perimax_config, supervisor_service=self.supervisor_service
            )
            logger.info("Perimax: Using wrapper device for process isolation")
        else:
            self._perimax_device = None
            if "perimax" in self._failed_devices:
                logger.warning("Perimax: Wrapper failed during initialization")
            else:
                logger.warning("Perimax: No wrapper config found, device not available")
        if self._perimax_device:
            self.device_registry.register(self._perimax_device)

        # Force Sensor
        force_config = self._device_config.get("force_sensor", {})
        if force_config and "force_sensor" not in self._failed_devices:
            self._force_device = ForceWrapperDevice(
                force_config, supervisor_service=self.supervisor_service
            )
            logger.info("Force sensor: Using wrapper device for process isolation")
        else:
            self._force_device = None
            if "force_sensor" in self._failed_devices:
                logger.warning("Force sensor: Wrapper failed during initialization")
            else:
                logger.warning("Force sensor: No wrapper config found, device not available")
        if self._force_device:
            self.device_registry.register(self._force_device)

    def _show_initialization_warnings(self):
        """Show warnings for devices that failed to initialize (from v2 lines 1259-1302)."""
        if not self._init_result or not self._init_result.warnings:
            return

        failed = self._init_result.failed_devices
        ready = self._init_result.ready_devices

        if failed:
            self._show_warning("warning", f"Some devices failed to initialize: {', '.join(failed)}")

            for warning in self._init_result.warnings:
                self._log(f"⚠ Startup: {warning}")
                event_log.error("startup", warning)

            if len(failed) == 5:
                QMessageBox.critical(
                    self,
                    "Initialization Failed",
                    "All device wrappers failed to start.\n\n"
                    f"Errors:\n" + "\n".join(f"• {w}" for w in self._init_result.warnings) +
                    "\n\nThe GUI will open but no devices are available.\n"
                    "Check device connections and configuration.",
                    QMessageBox.Ok
                )
            elif len(failed) > 0:
                QMessageBox.warning(
                    self,
                    "Partial Initialization",
                    f"Some device wrappers failed to start:\n\n" +
                    "\n".join(f"• {w}" for w in self._init_result.warnings) +
                    f"\n\nAvailable devices: {', '.join(ready) if ready else 'None'}\n"
                    "You can still use the available devices.",
                    QMessageBox.Ok
                )

            self.statusBar().showMessage(f"Ready ({len(ready)}/{len(ready)+len(failed)} devices)")

    def _create_menu_bar(self):
        """Create application menu bar with File and Tools menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Resume Session action
        resume_action = QAction("&Resume Session...", self)
        resume_action.setShortcut("Ctrl+R")
        resume_action.setStatusTip("Resume an interrupted measurement session")
        resume_action.triggered.connect(self._on_resume_session)
        file_menu.addAction(resume_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        # Analysis action
        analysis_action = QAction("&Analysis Window...", self)
        analysis_action.setShortcut("Ctrl+A")
        analysis_action.setStatusTip("Open post-run data analysis window")
        analysis_action.triggered.connect(self._on_open_analysis_window)
        tools_menu.addAction(analysis_action)

    def _on_resume_session(self):
        """Handle Resume Session menu action."""
        from PySide6.QtWidgets import QDialog
        from widgets.resume_dialog import ResumeDialog
        from executors.base_executor import BaseSequenceExecutor

        self._log("File > Resume Session selected")

        # Open file dialog to select checkpoint
        checkpoint_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Checkpoint File",
            str(self.repo_root / "runs"),
            "Checkpoint Files (checkpoint.json);;All Files (*.*)"
        )

        if not checkpoint_path:
            self._log("  Cancelled - no file selected")
            return

        checkpoint_path = Path(checkpoint_path)
        self._log(f"  Selected: {checkpoint_path}")

        # Show resume dialog
        dialog = ResumeDialog(checkpoint_path, parent=self)
        result = dialog.exec()

        self._log(f"  Dialog result: {result} (Accepted={QDialog.Accepted}), dialog.result={dialog.result}")

        if result == QDialog.Accepted and dialog.result == "resume":
            checkpoint_state = dialog.get_checkpoint_state()
            self._log(f"  Checkpoint state: {checkpoint_state is not None}")
            if checkpoint_state:
                self._execute_resume(checkpoint_state)
            else:
                self._log("  ERROR: checkpoint_state is None")
        else:
            self._log(f"  Resume not triggered - dialog cancelled or result mismatch")

    def _execute_resume(self, checkpoint_state):
        """Execute resume from checkpoint state.

        Args:
            checkpoint_state: CheckpointState to resume from
        """
        from executors.base_executor import BaseSequenceExecutor

        self._log(f"--- Resume Session ---")
        self._log(f"Sequence: {checkpoint_state.sequence_id}")
        self._log(f"Type: {checkpoint_state.sequence_type}")
        self._log(f"Progress: {checkpoint_state.get_completed_count()}/{checkpoint_state.total_steps} steps completed")

        # Check if resumable
        if not checkpoint_state.is_resumable():
            QMessageBox.warning(
                self,
                "Resume Failed",
                f"Checkpoint is not resumable.\n\n"
                f"Completed: {checkpoint_state.get_completed_count()}/{checkpoint_state.total_steps} steps\n"
                f"This may be a completed or empty sequence."
            )
            return

        # Load sequence definition from session folder
        session_folder = Path(checkpoint_state.output_dir)
        steps = BaseSequenceExecutor.load_sequence_definition(session_folder)

        if not steps:
            self._log(f"  Warning: sequence_definition.json not found in {session_folder}")
            # Fallback: reconstruct minimal steps from checkpoint (limited info)
            steps = self._reconstruct_steps_from_checkpoint(checkpoint_state)
            if not steps:
                QMessageBox.warning(
                    self,
                    "Resume Failed",
                    f"Could not load sequence definition from:\n{session_folder}\n\n"
                    "The sequence_definition.json file is missing and could not be reconstructed.\n"
                    "This checkpoint may have been created with an older version."
                )
                return
            self._log(f"  Reconstructed {len(steps)} steps from checkpoint (limited params)")

        self._log(f"  Loaded {len(steps)} step definitions")

        # Select appropriate executor based on sequence type
        seq_type = checkpoint_state.sequence_type.lower()
        if seq_type == "mixed":
            executor = self.mixed_executor
            self._log(f"  Using MixedSequenceExecutor")
        elif seq_type == "gamry":
            executor = self.gamry_executor
            self._log(f"  Using GamrySequenceExecutor")
        else:
            QMessageBox.warning(
                self,
                "Resume Failed",
                f"Unknown sequence type: {checkpoint_state.sequence_type}\n"
                "Only 'gamry' and 'mixed' sequences are supported."
            )
            return

        # Ensure devices are connected for Gamry sequences
        if seq_type in ("gamry", "mixed"):
            gamry_device = self.device_registry.get("gamry")
            if not gamry_device or not gamry_device.is_connected():
                QMessageBox.warning(
                    self,
                    "Resume Failed",
                    "Gamry potentiostat is not connected.\n\n"
                    "Please connect to Gamry before resuming the sequence."
                )
                return

        # Populate sequence table with steps for visual feedback
        self._log(f"  Populating sequence table...")
        self.sequence_table.clear_steps()
        for i, step in enumerate(steps):
            # Mark already completed steps
            step_state = None
            for ss in checkpoint_state.step_states:
                if ss.index == i:
                    step_state = ss
                    break

            if step_state and step_state.status == "success":
                step['state'] = 'done'
            elif step_state and step_state.status == "failed":
                step['state'] = 'failed'
            else:
                step['state'] = 'pending'

            self.sequence_table.add_step_dict(step)

        self._log(f"  Starting execution from step {checkpoint_state.next_step_index + 1}...")

        # Start from checkpoint, passing pre-loaded steps
        success = executor.start_from_checkpoint(checkpoint_state, steps=steps)

        if success:
            self._log(f"Resume started successfully")
        else:
            QMessageBox.warning(
                self,
                "Resume Failed",
                f"Failed to resume sequence: {checkpoint_state.sequence_id}\n\n"
                "Check the log for details."
            )

    def _reconstruct_steps_from_checkpoint(self, checkpoint_state) -> list:
        """Reconstruct minimal step definitions from checkpoint state.

        This is a fallback for older checkpoints without sequence_definition.json.
        Only provides basic step info - actual params may be missing.

        Args:
            checkpoint_state: CheckpointState to reconstruct from

        Returns:
            List of step dicts, or empty list if reconstruction fails
        """
        steps = []
        seq_type = checkpoint_state.sequence_type.lower()

        for ss in checkpoint_state.step_states:
            if seq_type == "gamry":
                # Gamry-only sequence: assume technique from artifacts or default to CV
                technique = "CV"  # Default fallback
                if ss.artifacts:
                    # Try to infer technique from artifact filename
                    for art in ss.artifacts:
                        art_name = Path(art).stem.upper()
                        for tech in ["OCV", "CV", "LSV", "CA", "CP", "EIS"]:
                            if tech in art_name:
                                technique = tech
                                break

                steps.append({
                    "device": "gamry",
                    "technique": technique,
                    "params": {},  # Params not available
                })
            elif seq_type == "mixed":
                # Mixed sequence: harder to reconstruct device info
                steps.append({
                    "device": "gamry",  # Assume gamry for now
                    "technique": "CV",
                    "params": {},
                })
            else:
                return []

        return steps

    def _on_open_analysis_window(self):
        """Handle Tools > Analysis Window menu action."""
        from analysis import AnalysisWindow

        self._log("Tools > Analysis Window selected")

        # Create and show analysis window (non-modal)
        # Store reference to prevent garbage collection
        if not hasattr(self, '_analysis_window') or self._analysis_window is None:
            self._analysis_window = AnalysisWindow(
                runs_root=self.repo_root / "runs",
                parent=None  # Independent window
            )

        self._analysis_window.show()
        self._analysis_window.raise_()
        self._analysis_window.activateWindow()

    def _create_toolbar(self):
        """Create toolbar with hardware status bar widget.

        Uses modular HardwareStatusBar widget (v3.1 refactor).
        See widgets/hardware_status_bar.py for implementation details.
        """
        toolbar = QToolBar("Hardware Status")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # Create hardware status bar widget
        self.hardware_status_bar = HardwareStatusBar()
        toolbar.addWidget(self.hardware_status_bar)

        # Connect status bar signals for logging
        self.hardware_status_bar.connection_changed.connect(self._on_device_connection_changed)

        # Wire force sensor streaming to hardware status bar for live reading
        if self._force_device:
            self.hardware_status_bar.set_force_device(self._force_device)
            self._force_device.signals.force_updated.connect(
                self.hardware_status_bar.update_force_reading
            )

    def _create_gamry_control_widget(self) -> QWidget:
        """Create Gamry control widget (from v2 lines 1418-1449)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.gamry_control_panel = GamryControlPanel(
            device_registry=self.device_registry,
            supervisor_service=self.supervisor_service,
            gamry_controller=self.gamry_controller,
            parent=container
        )
        self.gamry_control_panel.command_requested.connect(self._on_device_command)
        self.gamry_control_panel.sequence_run_requested.connect(self._on_gamry_sequence_requested)
        self.gamry_control_panel.validation_warning.connect(self._show_warning)
        self.gamry_control_panel.pause_requested.connect(self._on_pause_requested)
        self.gamry_control_panel.continue_requested.connect(self._on_continue_requested)
        self.gamry_control_panel.stop_requested.connect(self._on_stop_requested)
        self.gamry_control_panel.rolling_window_changed.connect(self._on_rolling_window_changed)
        self.gamry_control_panel.add_step_requested.connect(self._on_add_step_from_panel)
        layout.addWidget(self.gamry_control_panel)

        return container

    def _create_main_layout(self):
        """Create main layout with splitters (from v2 lines 1452-1612)."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Outer vertical layout: main content + warning bar at bottom
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        outer_layout.setSpacing(5)

        # Main content container
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Main horizontal splitter
        main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter = main_splitter

        # LEFT COLUMN: Sequence table + Device control tabs
        # Use CollapsibleSplitter with grip handle (collapse via buttons)
        self._left_splitter = CollapsibleSplitter(Qt.Vertical, enable_double_click=False)

        self.sequence_table = SequenceTableWidget()
        self.sequence_table.set_main_window(self)
        # Allow full vertical splitter travel without altering width behavior
        self.sequence_table.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.sequence_table.setMinimumHeight(0)
        self.sequence_table.run_sequence_requested.connect(self._on_sequence_table_run)
        self.sequence_table.run_array_requested.connect(self._on_run_array_sequence)
        self.sequence_table.array_stop_requested.connect(self._on_array_stop)
        self.sequence_table.array_stop_now_requested.connect(self._on_array_stop_now)
        self.sequence_table.array_pause_requested.connect(self._on_array_pause)
        self.sequence_table.array_resume_requested.connect(self._on_array_resume)
        # Connect collapse button in sequence table to splitter (use self._left_splitter)
        self.sequence_table.collapse_requested.connect(self._on_sequence_collapse_requested)
        self._left_splitter.addWidget(self.sequence_table)

        # Connect device state changes to Array Mode status updates
        if self._pi_device:
            self._pi_device.on_state_change(self._on_device_state_for_array)
        if self._gamry_device:
            self._gamry_device.on_state_change(self._on_device_state_for_array)

        # Device control tabs
        self.device_control_tabs = QTabWidget()

        # PI XYZ tab
        self.pi_control_panel = PIControlPanel(
            device_registry=self.device_registry,
            supervisor_service=self.supervisor_service
        )
        self.pi_control_panel.command_requested.connect(self._on_device_command)
        self.device_control_tabs.addTab(self.pi_control_panel, "PI XYZ")

        # Gamry tab
        self.gamry_manual_widget = self._create_gamry_control_widget()
        self.device_control_tabs.addTab(self.gamry_manual_widget, "Gamry")

        # Thorlabs tab
        self.thorlabs_control_panel = ThorlabsControlPanelV2(
            device_registry=self.device_registry
        )
        self.device_control_tabs.addTab(self.thorlabs_control_panel, "Thorlabs")

        # Perimax tab
        self.perimax_control_panel = PerimaxControlPanel(
            device_registry=self.device_registry
        )
        self.device_control_tabs.addTab(self.perimax_control_panel, "Perimax")

        # Force Sensor tab
        self.force_control_panel = ForceControlPanel(
            device_registry=self.device_registry
        )
        self.device_control_tabs.addTab(self.force_control_panel, "Force")

        # USB coordination
        self.pi_control_panel.usb_operation_starting.connect(
            self.thorlabs_control_panel.pause_for_usb_operation
        )
        self.pi_control_panel.usb_operation_finished.connect(
            self.thorlabs_control_panel.resume_after_usb_operation
        )
        event_log.system("usb_coordination_enabled", pi_xyz="pause_thorlabs")

        # Container for device tabs + persistent Vocv display
        device_container = QWidget()
        # Allow full vertical splitter travel without altering width behavior
        device_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        device_container.setMinimumHeight(0)
        device_layout = QVBoxLayout(device_container)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(2)

        # Device panel header with collapse control
        self._device_header = QWidget()
        device_header_layout = QHBoxLayout(self._device_header)
        device_header_layout.setContentsMargins(0, 0, 0, 0)
        device_header_layout.setSpacing(5)
        self._device_header_label = QLabel("Device Panels")
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        self._device_header_label.setFont(header_font)
        device_header_layout.addWidget(self._device_header_label)
        device_header_layout.addStretch()
        self._device_collapse_btn = CollapseButton("Device Panels", initial_collapsed=False)
        self._device_collapse_btn.clicked.connect(self._on_device_collapse_requested)
        device_header_layout.addWidget(self._device_collapse_btn)
        device_layout.addWidget(self._device_header)

        # Device panel body
        self._device_body = QWidget()
        device_body_layout = QVBoxLayout(self._device_body)
        device_body_layout.setContentsMargins(0, 0, 0, 0)
        device_body_layout.setSpacing(2)
        device_body_layout.addWidget(self.device_control_tabs, 1)
        self.device_control_tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.device_control_tabs.setMinimumHeight(0)

        # Persistent Vocv status bar
        self.vocv_status_frame = QFrame()
        self.vocv_status_frame.setFrameShape(QFrame.NoFrame)
        self.vocv_status_frame.setStyleSheet("background-color: #f0f4f8; border-radius: 3px;")
        vocv_layout = QHBoxLayout(self.vocv_status_frame)
        vocv_layout.setContentsMargins(8, 4, 8, 4)
        vocv_label = QLabel("Latest Stable Vocv:")
        vocv_label.setStyleSheet("font-weight: bold; color: #333;")
        vocv_layout.addWidget(vocv_label)
        self.vocv_value_label = QLabel("N/A")
        self.vocv_value_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        vocv_layout.addWidget(self.vocv_value_label)
        vocv_layout.addStretch()
        device_body_layout.addWidget(self.vocv_status_frame)
        device_layout.addWidget(self._device_body, 1)

        self._left_splitter.addWidget(device_container)

        # Set initial ratio: Sequence 40%, Device 60%
        self._left_splitter.setSizes([240, 360])

        # Enable collapsing
        self._left_splitter.setCollapsible(0, True)
        self._left_splitter.setCollapsible(1, True)
        self.sequence_table.setMinimumHeight(0)
        device_container.setMinimumHeight(0)
        self.device_control_tabs.setMinimumHeight(0)

        # Connect splitter signals
        self._left_splitter.collapse_state_changed.connect(self._on_panel_collapse_changed)

        main_splitter.addWidget(self._left_splitter)

        # CENTER COLUMN: Stacked widget (Live Run / Sequence Builder)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(5)

        self.center_stack = QStackedWidget()

        # Live Run view: Plot + Log
        self.plot_log_splitter = QSplitter(Qt.Vertical)

        self.plot_widget = PlotWidget(plot_policy=self._long_run_policy.plot)
        self.plot_log_splitter.addWidget(self.plot_widget)

        self.log_widget = LogWidget()
        self.plot_log_splitter.addWidget(self.log_widget)

        self.plot_log_splitter.setSizes([680, 120])
        self.plot_log_splitter.setCollapsible(1, True)

        self.center_stack.addWidget(self.plot_log_splitter)  # index 0

        # Sequence Builder view (placeholder)
        builder_widget = QFrame()
        builder_widget.setFrameShape(QFrame.NoFrame)
        builder_label = QLabel("SEQUENCE BUILDER\n\n(Drag-and-drop sequence editor)")
        builder_label.setAlignment(Qt.AlignCenter)
        builder_label.setStyleSheet("color: #888; font-size: 14pt; font-style: italic;")
        builder_layout = QVBoxLayout(builder_widget)
        builder_layout.addWidget(builder_label)

        self.center_stack.addWidget(builder_widget)  # index 1

        center_layout.addWidget(self.center_stack)
        main_splitter.addWidget(center_widget)

        # Keep a stable 30/70 split on first show and proportional resize
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 7)

        main_layout.addWidget(main_splitter)

        outer_layout.addWidget(main_content, stretch=1)

        # Warning bar at bottom
        self.warning_bar = WarningBar()
        outer_layout.addWidget(self.warning_bar)

    def _apply_initial_main_splitter_sizes(self):
        """Set initial main splitter ratio after layout/size hints settle."""
        if not getattr(self, "_main_splitter", None):
            return
        total = self._main_splitter.size().width()
        if total <= 0:
            return
        self._update_left_min_width()
        left = int(total * 0.30)
        self._main_splitter.setSizes([left, max(total - left, 0)])

    def _update_left_min_width(self):
        """Ensure left panel can't shrink below fully-visible controls."""
        if not getattr(self, "_left_splitter", None):
            return

        candidates = []
        if getattr(self, "sequence_table", None):
            header = getattr(self.sequence_table, "_header_widget", None)
            if header:
                candidates.append(header.minimumSizeHint().width())
                candidates.append(header.sizeHint().width())
            else:
                candidates.append(self.sequence_table.minimumSizeHint().width())
        if getattr(self, "_device_header", None):
            candidates.append(self._device_header.minimumSizeHint().width())
        if getattr(self, "device_control_tabs", None):
            tab_bar = self.device_control_tabs.tabBar()
            if tab_bar:
                candidates.append(tab_bar.minimumSizeHint().width())
                candidates.append(tab_bar.sizeHint().width())
            for i in range(self.device_control_tabs.count()):
                w = self.device_control_tabs.widget(i)
                if w:
                    candidates.append(w.minimumSizeHint().width())
                    candidates.append(w.sizeHint().width())

        min_width = max(candidates) if candidates else 0
        # Add a small pad for margins/scrollbars
        min_width = max(min_width + 12, 0)
        self._left_splitter.setMinimumWidth(min_width)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_splitter_initialized", False):
            self._splitter_initialized = True
            QTimer.singleShot(0, self._apply_initial_main_splitter_sizes)

    def _on_left_splitter_moved(self, pos: int, index: int):
        """Handle left splitter movement - elastic resistance at 70% threshold (from v2 lines 1614-1651)."""
        sizes = self._left_splitter.sizes()
        if len(sizes) < 2:
            return

        total = sum(sizes)
        if total <= 0:
            return

        seq_ratio = sizes[0] / total

        TITLE_HEIGHT = 32
        SOFT_THRESHOLD = 0.70
        HARD_THRESHOLD = 0.80

        if SOFT_THRESHOLD < seq_ratio < HARD_THRESHOLD:
            overshoot = (seq_ratio - SOFT_THRESHOLD) / (HARD_THRESHOLD - SOFT_THRESHOLD)
            damped_ratio = SOFT_THRESHOLD + overshoot * 0.5 * (HARD_THRESHOLD - SOFT_THRESHOLD)
            new_seq = int(total * damped_ratio)
            self._left_splitter.setSizes([new_seq, total - new_seq])
        elif seq_ratio >= HARD_THRESHOLD:
            self._left_splitter.setSizes([total - TITLE_HEIGHT, TITLE_HEIGHT])
        elif (1 - HARD_THRESHOLD) < seq_ratio < (1 - SOFT_THRESHOLD):
            overshoot = ((1 - SOFT_THRESHOLD) - seq_ratio) / (HARD_THRESHOLD - SOFT_THRESHOLD)
            damped_ratio = (1 - SOFT_THRESHOLD) - overshoot * 0.5 * (HARD_THRESHOLD - SOFT_THRESHOLD)
            new_seq = int(total * damped_ratio)
            self._left_splitter.setSizes([new_seq, total - new_seq])
        elif seq_ratio <= (1 - HARD_THRESHOLD):
            self._left_splitter.setSizes([TITLE_HEIGHT, total - TITLE_HEIGHT])

    def _on_panel_collapse_changed(self, panel_index: int, is_collapsed: bool):
        """Handle collapse state change - update collapse button icons.

        Args:
            panel_index: 0 = Sequence Manager, 1 = Device Panels
            is_collapsed: True if panel is now collapsed
        """
        if panel_index == 0:
            # Sequence Manager panel - update its collapse button
            self.sequence_table.set_collapse_state(is_collapsed)
        elif panel_index == 1:
            self._device_collapse_btn.set_collapsed(is_collapsed)
            self._device_body.setVisible(not is_collapsed)

    def _on_sequence_collapse_requested(self):
        """Handle collapse request from Sequence Manager's collapse button."""
        self._left_splitter.toggle_collapse(0)

    def _on_device_collapse_requested(self):
        """Handle collapse request from Device Panels' collapse button."""
        self._left_splitter.toggle_collapse(1)

    def _create_executors(self):
        """Create sequence executors."""
        # Gamry sequence executor
        self.gamry_executor = GamrySequenceExecutor(
            command_dispatcher=self.command_dispatcher,
            device_registry=self.device_registry,
            sequence_table=self.sequence_table,
            log_fn=self._log,
            show_warning_fn=self._show_warning,
            gamry_control_panel=self.gamry_control_panel,
            plot_widget=self.plot_widget,
            long_run_policy=self._long_run_policy,
            parent=self
        )
        # Wire executor resource warning signals
        self.gamry_executor.memory_warning.connect(self._on_memory_warning)
        self.gamry_executor.memory_critical.connect(self._on_memory_critical)
        self.gamry_executor.disk_warning.connect(self._on_disk_warning)

        # Mixed sequence executor
        self.mixed_executor = MixedSequenceExecutor(
            command_dispatcher=self.command_dispatcher,
            device_registry=self.device_registry,
            sequence_table=self.sequence_table,
            log_fn=self._log,
            show_warning_fn=self._show_warning,
            gamry_control_panel=self.gamry_control_panel,
            pi_device=self._pi_device,
            plot_widget=self.plot_widget,
            long_run_policy=self._long_run_policy,
            parent=self
        )
        self.mixed_executor.memory_warning.connect(self._on_memory_warning)
        self.mixed_executor.memory_critical.connect(self._on_memory_critical)
        self.mixed_executor.disk_warning.connect(self._on_disk_warning)

        # Array mode executor
        self.array_executor = ArrayModeExecutor(
            command_dispatcher=self.command_dispatcher,
            device_registry=self.device_registry,
            sequence_table=self.sequence_table,
            log_fn=self._log,
            show_warning_fn=self._show_warning,
            gamry_control_panel=self.gamry_control_panel,
            pi_device=self._pi_device,
            gamry_device=self._gamry_device,
            plot_widget=self.plot_widget,
            long_run_policy=self._long_run_policy,
            parent=self
        )
        self.array_executor.memory_warning.connect(self._on_memory_warning)
        self.array_executor.memory_critical.connect(self._on_memory_critical)
        self.array_executor.disk_warning.connect(self._on_disk_warning)
        # Connect to clear explicit flag when array completes
        self.array_executor.execution_completed.connect(self._on_array_execution_completed)

    # =========================================================================
    # Toolbar Handlers (from v2 lines 1653-1771)
    # =========================================================================

    def _on_view_changed(self, view_name: str):
        """Handle view mode change."""
        if view_name == "Live Run":
            self.center_stack.setCurrentIndex(0)
        elif view_name == "Sequence Builder":
            self.center_stack.setCurrentIndex(1)

    def _on_start_all(self):
        """Handle Start All button."""
        self._log("Starting all devices...")
        self.statusBar().showMessage("Starting all devices...")
        self.supervisor_service.request_start_all.emit()

    def _on_start_device(self, device_name: str):
        """Handle per-device Start action."""
        display_name = device_name.replace('_', ' ').title()
        self._log(f"Starting {display_name}...")
        self.statusBar().showMessage(f"Starting {display_name}...")
        self.supervisor_service.request_start_device.emit(device_name)

    def _on_stop_device(self, device_name: str):
        """Handle per-device Stop action."""
        display_name = device_name.replace('_', ' ').title()
        self._log(f"Stopping {display_name}...")
        self.statusBar().showMessage(f"Stopping {display_name}...")
        self.supervisor_service.request_stop_device.emit(device_name)

    def _on_ping_device(self, device_name: str):
        """Handle per-device Ping action."""
        display_name = device_name.replace('_', ' ').title()
        self._log(f"Pinging {display_name}...")
        self.statusBar().showMessage(f"Pinging {display_name}...")
        self.supervisor_service.request_ping_device.emit(device_name)

    def _on_select_sequence(self):
        """Choose sequence plan to run.

        Note: Toolbar plan selector removed in v3.1.
        This method is kept for programmatic use but no longer has a UI button.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sequence File",
            str(self.repo_root / "examples"),
            "YAML Files (*.yaml *.yml)"
        )

        if not file_path:
            return

        self.selected_sequence_path = Path(file_path)
        self._log(f"Selected plan: {self.selected_sequence_path.name}")

    def _on_abort_sequence(self):
        """Abort currently running sequence without stopping devices."""
        if self.sequence_worker and self.sequence_worker.isRunning():
            self.sequence_worker.stop()
            self._log("Abort requested for active sequence")
            self.statusBar().showMessage("Aborting sequence...")
        else:
            QMessageBox.information(self, "No Active Sequence", "There is no running sequence to abort.")

    def _on_stop_all(self):
        """Handle Stop All button."""
        aborted = self._stop_active_operations()
        if aborted:
            self._log("Abort requested for active commands/sequences")
        self._log("Stopping all devices...")
        self.statusBar().showMessage("Stopping all devices...")
        self.supervisor_service.request_stop_all.emit()

    def _stop_active_operations(self) -> bool:
        """Attempt to abort any running sequences or ad-hoc commands."""
        aborted = False

        if self.sequence_worker and self.sequence_worker.isRunning():
            self.sequence_worker.stop()
            aborted = True

        if self.command_dispatcher.is_busy():
            if self.command_dispatcher.stop_current_command():
                aborted = True

        return aborted

    def _set_sequence_controls_running(self, running: bool):
        """Enable/disable sequence controls.

        Note: Toolbar sequence buttons removed in v3.1.
        This method is kept for compatibility but is now a no-op.
        Sequence state is tracked internally for proper cleanup.
        """
        # Toolbar buttons removed - track state internally instead
        self._sequence_running = running

    def _on_ping_all(self):
        """Handle Ping All button."""
        self._log("Pinging all devices...")
        self.statusBar().showMessage("Pinging all devices...")
        self.supervisor_service.request_ping_all.emit()

    def _on_run_sequence(self):
        """Handle Run Sequence action (from toolbar)."""
        if self.sequence_worker and self.sequence_worker.isRunning():
            QMessageBox.warning(self, "Sequence Running", "A sequence is already running.")
            return

        if not self.selected_sequence_path or not self.selected_sequence_path.exists():
            QMessageBox.warning(self, "No Plan Selected", "Select a sequence plan before running.")
            return

        file_path = str(self.selected_sequence_path)

        self._log(f"Starting sequence: {self.selected_sequence_path.name}")
        self.statusBar().showMessage(f"Running sequence: {self.selected_sequence_path.name}...")

        self.is_adhoc_sequence = False

        supervisors = self.supervisor_service.get_supervisors_snapshot()
        self.sequence_worker = SequenceWorker(self.config_path, file_path, dry_run=False, supervisors=supervisors)
        self.sequence_worker.sequence_started.connect(self._on_sequence_started)
        self.sequence_worker.sequence_completed.connect(self._on_sequence_completed)
        self.sequence_worker.sequence_failed.connect(self._on_sequence_failed)
        self.sequence_worker.start()
        self._set_sequence_controls_running(True)

    # =========================================================================
    # Sequence Worker Handlers (from v2 lines 1773-1931)
    # =========================================================================

    def _on_sequence_started(self, output_dir: str):
        """Handle sequence start."""
        self._log(f"Sequence started - Output: {output_dir}")

        self.current_manifest_path = Path(output_dir) / "manifest.json"
        self.manifest_timer.start()

        if not self.is_adhoc_sequence:
            self.sequence_table.clear_steps()
            self._seed_sequence_table_from_plan()
        else:
            self._log("Ad-hoc sequence running (table not updated)")

    def _on_sequence_completed(self, result: dict):
        """Handle sequence completion (from v2 lines 1788-1856)."""
        self.manifest_timer.stop()

        if not self.is_adhoc_sequence:
            self._refresh_manifest_view()

        self._generate_sequence_exports(result)

        if self.current_temp_sequence:
            try:
                import os
                os.remove(self.current_temp_sequence)
                self._log(f"Cleaned up temp file: {self.current_temp_sequence}")
            except Exception as e:
                self._log(f"Warning: Failed to clean temp file: {e}")
            finally:
                self.current_temp_sequence = None

        was_adhoc = self.is_adhoc_sequence
        self.is_adhoc_sequence = False

        status = result.get('status', 'unknown')
        duration = result.get('duration_s', 0)

        if status == 'success':
            self._log(f"Sequence SUCCESS ({duration:.1f}s)")
            self.statusBar().showMessage(f"Sequence completed ({duration:.1f}s)")

            if was_adhoc and self.active_command_panel:
                self.active_command_panel.on_command_success(f"Completed in {duration:.1f}s")
                self.active_command_panel = None

            if not was_adhoc:
                QMessageBox.information(self, "Sequence Complete", f"Sequence completed in {duration:.1f}s")
        elif status == 'interrupted':
            self._log("Sequence INTERRUPTED by operator")
            self.statusBar().showMessage("Sequence interrupted")

            if was_adhoc and self.active_command_panel:
                self.active_command_panel.on_command_failure("Command interrupted")
                self.active_command_panel = None

            if not was_adhoc:
                QMessageBox.information(self, "Sequence Interrupted", "Sequence stopped by operator.")
        else:
            self._log("Sequence FAILED")
            self.statusBar().showMessage("Sequence failed")

            if was_adhoc and self.active_command_panel:
                self.active_command_panel.on_command_failure("Sequence execution failed")
                self.active_command_panel = None

            if not was_adhoc:
                QMessageBox.warning(self, "Sequence Failed", "Sequence execution failed")

        if not was_adhoc:
            self._set_sequence_controls_running(False)

        self.sequence_worker = None

    def _on_sequence_failed(self, error_msg: str):
        """Handle sequence failure."""
        self.manifest_timer.stop()

        if self.current_temp_sequence:
            try:
                import os
                os.remove(self.current_temp_sequence)
                self._log(f"Cleaned up temp file: {self.current_temp_sequence}")
            except Exception as e:
                self._log(f"Warning: Failed to clean temp file: {e}")
            finally:
                self.current_temp_sequence = None

        was_adhoc = self.is_adhoc_sequence
        self.is_adhoc_sequence = False

        self._log(f"Sequence ERROR: {error_msg}")
        self.statusBar().showMessage("Sequence error")

        if was_adhoc and self.active_command_panel:
            self.active_command_panel.on_command_failure(error_msg)
            self.active_command_panel = None

        if not was_adhoc:
            QMessageBox.critical(self, "Sequence Error", error_msg)
            self._set_sequence_controls_running(False)

        self.sequence_worker = None

    def _seed_sequence_table_from_plan(self):
        """Seed sequence table from the loaded sequence plan."""
        if not self.sequence_worker:
            return

        sequence_path = self.sequence_worker.sequence_path
        try:
            import yaml
            with open(sequence_path, 'r') as f:
                sequence = yaml.safe_load(f)

            for step in sequence.get('steps', []):
                step_id = step.get('id', 'unknown')
                device = step.get('device', 'N/A')
                action = step.get('action', 'N/A')

                technique = action.replace('_', ' ').title()

                params = step.get('params', {})
                hold = params.get('hold', '-')
                final = params.get('final_v', params.get('final', '-'))
                scan_rate = params.get('scan_rate', '-')
                cycles = params.get('cycles', '-')

                self.sequence_table.add_step(
                    f"⏸ {device}",
                    technique,
                    str(hold),
                    str(final),
                    str(scan_rate),
                    str(cycles)
                )

        except Exception as e:
            self._log(f"Warning: Failed to seed table from plan: {e}")

    def _refresh_manifest_view(self):
        """Refresh sequence table and log from current manifest file (from v2 lines 1933-1982)."""
        if not self.current_manifest_path or not self.current_manifest_path.exists():
            return

        # Skip during executor sequences - they use their own step tracking
        is_gamry_sequence = self.gamry_executor and self.gamry_executor.is_running()
        is_mixed_sequence = self.mixed_executor and self.mixed_executor.is_running()
        is_array_sequence = self.array_executor and self.array_executor.is_running()
        if is_gamry_sequence or is_mixed_sequence or is_array_sequence:
            return

        try:
            with open(self.current_manifest_path, 'r') as f:
                manifest = json.load(f)

            self.sequence_table.clear_steps()
            for step in manifest.get('steps', []):
                step_id = step.get('id', 'unknown')
                device = step.get('device', 'N/A')
                action = step.get('action', 'N/A')
                state = step.get('state', 'pending')
                duration = step.get('duration_s', 0)

                technique = action.replace('_', ' ').title()

                params = step.get('params', {})
                hold = params.get('hold', '-')
                final = params.get('final_v', params.get('final', '-'))
                scan_rate = params.get('scan_rate', '-')
                cycles = params.get('cycles', '-')

                state_icon = {'pending': '⏸', 'running': '▶', 'success': '✓', 'failed': '✗', 'skipped': '⊘'}.get(state, '?')
                self.sequence_table.add_step(
                    f"{state_icon} {device}",
                    technique,
                    str(hold),
                    str(final),
                    str(scan_rate),
                    str(cycles)
                )

        except FileNotFoundError:
            pass  # File doesn't exist yet - expected during startup
        except json.JSONDecodeError as e:
            logger.debug(f"Manifest parse error (file may be mid-write): {e}")
        except Exception as e:
            logger.warning(f"Failed to refresh manifest view: {e}")

    # =========================================================================
    # Status Update Handlers (from v2 lines 1984-2111)
    # =========================================================================

    @Slot(dict)
    def _on_status_updated(self, status_data: dict):
        """Handle status update from supervisor.

        Delegates to HardwareStatusBar widget for toolbar updates.
        Also updates Array Mode widget with device connection status.
        """
        # Status update logging suppressed (too verbose for console)
        # Update toolbar via widget (with defensive check)
        if not hasattr(self, 'hardware_status_bar') or self.hardware_status_bar is None:
            logger.warning("hardware_status_bar not initialized yet, skipping status update")
            return

        try:
            self.hardware_status_bar.update_status(status_data)
            logger.debug(f"hardware_status_bar updated, summary: {self.hardware_status_bar.get_summary_text()}")
        except Exception as e:
            logger.error(f"Failed to update hardware status bar: {e}")
            import traceback
            traceback.print_exc()

        # Update status bar with summary
        try:
            self.statusBar().showMessage(self.hardware_status_bar.get_summary_text())
        except Exception as e:
            logger.error(f"Failed to update status bar: {e}")

        # Update Array Mode widget using hardware status bar data
        pi_connected = self.hardware_status_bar.is_device_connected('pi_xyz')
        gamry_connected = self.hardware_status_bar.is_device_connected('gamry')

        # Fallback to device objects if available (for more immediate updates)
        if not pi_connected and self._pi_device:
            try:
                pi_connected = self._pi_device.is_connected()
            except Exception:
                pass
        if not gamry_connected and self._gamry_device:
            try:
                gamry_connected = self._gamry_device.is_connected()
            except Exception:
                pass

        self.sequence_table.set_device_status(pi_connected, gamry_connected)

    def _on_device_connection_changed(self, device_id: str, connected: bool):
        """Handle device connection state change from hardware status bar.

        Logs connection changes for operator visibility.
        """
        display_names = {
            'gamry': 'Gamry potentiostat',
            'pi_xyz': 'PI XYZ stage',
            'thorlabs': 'Thorlabs camera',
            'perimax': 'Perimax pump',
            'force_sensor': 'Force sensor'
        }
        device_name = display_names.get(device_id, device_id)

        if connected:
            self._log(f"{device_name} connected")
        else:
            self._log(f"{device_name} disconnected")

    def _on_device_state_for_array(self, old_state, new_state):
        """Callback from device thread when PI or Gamry state changes."""
        try:
            self._device_state_for_array.emit()
        except RuntimeError as e:
            # Qt signal emission can fail if object is being destroyed
            logger.debug(f"Device state signal emission failed (object may be destroyed): {e}")
        except Exception as e:
            logger.warning(f"Unexpected error emitting device state signal: {e}")

    @Slot()
    def _update_array_device_status(self):
        """Update Array Mode device status on GUI thread."""
        pi_connected = False
        gamry_connected = False

        if self._pi_device:
            try:
                pi_connected = self._pi_device.is_connected()
            except Exception as e:
                logger.debug(f"PI device connection check failed: {e}")

        if self._gamry_device:
            try:
                gamry_connected = self._gamry_device.is_connected()
            except Exception as e:
                logger.debug(f"Gamry device connection check failed: {e}")

        self.sequence_table.set_device_status(pi_connected, gamry_connected)

    # =========================================================================
    # Supervisor Signal Handlers (from v2 lines 2113-2264)
    # =========================================================================

    def _on_command_completed(self, command: str, device: str, success: bool, message: str):
        """Handle command completion from supervisor."""
        status = "OK" if success else "FAILED"
        log_msg = f"{command.upper()} {device}: {status}"
        self._log(log_msg)

        if success:
            event_log.device(device, command, "success", message=message[:100] if message else None)
        else:
            event_log.error(device, f"{command} failed: {message}")
            self._show_classified_error(device, command, message)

    def _on_error(self, error_msg: str):
        """Handle error from supervisor."""
        event_log.error("supervisor", error_msg)
        self._log(f"ERROR: {error_msg}")
        self.statusBar().showMessage(f"Error: {error_msg}")

    def _show_classified_error(self, device: str, command: str, message: str):
        """Show error with classification information."""
        error_info = classify_error(device, {"code": "COMMAND_ERROR", "message": message})

        severity_labels = {
            ErrorSeverity.TRANSIENT: ("Temporary", "⟳"),
            ErrorSeverity.RECOVERABLE: ("Recoverable", "↻"),
            ErrorSeverity.PERMANENT: ("Permanent", "⚠"),
        }
        severity_text, severity_icon = severity_labels.get(error_info.severity, ("Unknown", "?"))

        action_guidance = {
            RecoveryAction.RETRY_IMMEDIATE: "Will retry automatically.",
            RecoveryAction.RETRY_SHORT: "Will retry after a brief delay.",
            RecoveryAction.RESET_DEVICE: "Device will be restarted automatically.",
            RecoveryAction.RECONNECT: "Attempting to reconnect...",
            RecoveryAction.STOP_NOTIFY: "Manual intervention required.",
            RecoveryAction.OPERATOR_CONFIRM: "Please confirm before proceeding.",
        }
        guidance = action_guidance.get(error_info.action, "")

        self._log(f"{severity_icon} {device}/{command}: {error_info.user_message} [{severity_text}]")

        if error_info.severity == ErrorSeverity.PERMANENT:
            self._show_warning("error", f"{device}: {error_info.user_message}")
        elif error_info.severity == ErrorSeverity.RECOVERABLE:
            self._show_warning("warning", f"{device}: {error_info.user_message}")
        else:
            self.statusBar().showMessage(f"{device}: {error_info.user_message}", 5000)

    # Reliability Event Handlers

    def _on_restart_started(self, device_name: str):
        """Handle restart_started signal."""
        event_log.device(device_name, "restart", "started")
        self._log(f"⟳ {device_name}: Auto-restart initiated...")
        self._show_warning("warning", f"{device_name}: Restarting device...")
        self.statusBar().showMessage(f"Restarting {device_name}...")

    def _on_restart_completed(self, device_name: str, success: bool):
        """Handle restart_completed signal."""
        if success:
            event_log.device(device_name, "restart", "success")
            self._log(f"✓ {device_name}: Restart successful")
            self._show_warning("info", f"{device_name}: Restart successful")
            self.statusBar().showMessage(f"{device_name} recovered", 5000)
        else:
            event_log.error(device_name, "restart failed")
            self._log(f"✗ {device_name}: Restart FAILED")
            self._show_warning("error", f"{device_name}: Restart failed - check device")
            self.statusBar().showMessage(f"{device_name} restart failed")

    def _on_max_restarts_reached(self, device_name: str):
        """Handle max_restarts_reached signal."""
        event_log.error(device_name, "max restarts reached - manual intervention required")
        self._log(f"⚠ {device_name}: Max restart attempts reached - MANUAL INTERVENTION REQUIRED")
        self._show_warning("error", f"{device_name}: Max restarts reached - requires manual intervention")

        QMessageBox.critical(
            self,
            f"{device_name} Recovery Failed",
            f"Device '{device_name}' failed to recover after multiple restart attempts.\n\n"
            f"Manual intervention required:\n"
            f"1. Check physical connections\n"
            f"2. Restart the device manually\n"
            f"3. Click 'Start' in the device dropdown to reconnect",
            QMessageBox.Ok
        )

    def _on_operator_confirmation_needed(self, device_name: str):
        """Handle operator_confirmation_needed signal."""
        event_log.device(device_name, "restart", "confirmation_needed")
        self._log(f"⚠ {device_name}: Operator confirmation required for restart")
        self._show_warning("warning", f"{device_name}: Device unhealthy - manual restart required")

        result = QMessageBox.warning(
            self,
            f"{device_name} Restart Required",
            f"Device '{device_name}' has become unhealthy.\n\n"
            f"This device requires operator confirmation before restarting.\n"
            f"Please verify the device state before proceeding.\n\n"
            f"Do you want to restart the device now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if result == QMessageBox.Yes:
            self._log(f"Operator confirmed restart for {device_name}")
            self.supervisor_service.auto_restart.trigger_manual_restart(device_name)
        else:
            self._log(f"Operator declined restart for {device_name}")
            self._show_warning("warning", f"{device_name}: Restart declined - device remains unhealthy")

    def _on_device_recovered(self, device_name: str):
        """Handle device_recovered signal."""
        event_log.device(device_name, "recovery", "self_healed")
        self._log(f"✓ {device_name}: Device recovered on its own")
        self._show_warning("info", f"{device_name}: Self-recovered")
        self.statusBar().showMessage(f"{device_name} recovered", 5000)
        self._clear_warning()

    def _on_hardware_disconnected(self, device_name: str, error_msg: str):
        """Handle hardware_disconnected signal (USB unplugged during operation).

        This is called when the heartbeat detects hardware_ok=False during a busy
        state (measurement in progress). Unlike timeout-based detection, this
        provides immediate notification of USB disconnection.
        """
        event_log.device(device_name, "hardware", "disconnected")
        self._log(f"⛔ {device_name}: HARDWARE DISCONNECTED - {error_msg}")
        self._show_warning("error", f"{device_name}: Hardware disconnected!")

        # Show critical error dialog - this is a serious issue requiring attention
        QMessageBox.critical(
            self,
            f"{device_name} Hardware Disconnected",
            f"Device '{device_name}' has lost connection!\n\n"
            f"Error: {error_msg}\n\n"
            f"The USB cable may have been disconnected or the device may have "
            f"lost power. Any measurement in progress has likely failed.\n\n"
            f"Please:\n"
            f"1. Check USB cable connection\n"
            f"2. Verify device power\n"
            f"3. Restart the device when ready",
            QMessageBox.Ok
        )

    def _on_command_stuck(self, device_name: str, action: str, elapsed_s: float, timeout_s: float):
        """Handle command_stuck signal (Phase 3B: Reliability).

        This is called when a command exceeds its expected timeout, providing
        early warning before CommandDispatcher forces a stop.
        """
        event_log.device(device_name, action, "stuck", elapsed_s=elapsed_s, timeout_s=timeout_s)
        self._log(f"⚠️ {device_name}: Command '{action}' stuck ({elapsed_s:.0f}s > {timeout_s:.0f}s timeout)")
        self._show_warning(
            "warning",
            f"{device_name}: '{action}' exceeds timeout ({elapsed_s:.0f}s)"
        )

    def _on_capabilities_updated(self, device: str, capabilities: dict):
        """Handle capabilities_updated signal from supervisor."""
        actions = capabilities.get('actions', [])
        techniques = capabilities.get('techniques', {})
        self._log(f"Capabilities received for {device}: {len(actions)} actions, {len(techniques)} techniques")

    # =========================================================================
    # Pause / Continue / Stop handlers (from v2 lines 2287-2388)
    # =========================================================================

    def _on_pause_requested(self):
        """Handle pause request from control panel."""
        self._log("Pause requested")
        if self.command_dispatcher.is_busy():
            self._send_wrapper_command('gamry', 'pause_task', {})
        else:
            self._log("No active command to pause")
            if hasattr(self, 'gamry_control_panel'):
                self.gamry_control_panel.status_label.setText("Nothing to pause")

    def _on_continue_requested(self):
        """Handle continue request from control panel."""
        self._log("Continue requested")
        self._send_wrapper_command('gamry', 'continue_task', {})

    def _on_stop_requested(self):
        """Handle stop request from control panel."""
        self._log("Stop requested")

        # Stop any active executor sequences
        if self.gamry_executor and self.gamry_executor.is_running():
            self.gamry_executor.stop()
            self._log("  Gamry sequence stop requested")
        if self.mixed_executor and self.mixed_executor.is_running():
            self.mixed_executor.stop()
            self._log("  Mixed sequence stop requested")
        if self.array_executor and self.array_executor.is_running():
            self.array_executor.stop()
            self._log("  Array sequence stop requested")

        self._send_wrapper_command('gamry', 'stop_task', {})

        if self.command_dispatcher.is_busy():
            self.command_dispatcher.stop_current_command()

    def _on_rolling_window_changed(self, window_s: float):
        """Handle rolling window change from control panel."""
        self._log(f"Rolling window changed: {window_s}s")
        if hasattr(self, 'plot_widget') and self.plot_widget:
            self.plot_widget.set_rolling_window(window_s)

    def _prepare_plot_for_live_continue(self) -> None:
        """Refresh the live plot canvas after an in-run Continue ACK."""
        plot_widget = getattr(self, 'plot_widget', None)
        if plot_widget is None or not hasattr(plot_widget, 'prepare_for_live_continue'):
            return

        try:
            plot_widget.prepare_for_live_continue()
        except Exception as exc:
            self._log(f"Warning: failed to refresh plot on continue: {exc}")

    def _send_wrapper_command(self, device: str, action: str, params: dict):
        """Send a command directly to wrapper (for pause/continue/stop) - from v2 lines 2328-2388."""
        if not self.supervisor_service:
            self._log(f"Cannot send {action}: no supervisor service")
            self._rollback_gamry_panel_state(action)
            return

        try:
            supervisors = self.supervisor_service.get_supervisors_snapshot()
            if device not in supervisors:
                self._log(f"Cannot send {action}: device '{device}' not running")
                self._show_warning('error', f"Device '{device}' not running")
                self._rollback_gamry_panel_state(action)
                return

            supervisor = supervisors[device]

            cmd = {'action': action}
            if params:
                cmd['params'] = params

            response = supervisor.send_command(cmd, timeout=10.0)
            if response is None:
                self._log(f"{action} failed: no response from wrapper")
                self._show_warning('error', f"{action}: No response from wrapper")
                self._rollback_gamry_panel_state(action)
                return

            if response.get('ok'):
                details = response.get('details', {})
                self._log(f"{action} acknowledged: {details}")
                if action == 'pause_task' and hasattr(self, 'gamry_control_panel'):
                    self.gamry_control_panel.set_paused_state()
                elif action == 'continue_task' and hasattr(self, 'gamry_control_panel'):
                    self._prepare_plot_for_live_continue()
                    from gui.base.device_control_base import ControlPanelState
                    self.gamry_control_panel.set_state(ControlPanelState.RUNNING)
                    self._log("Continue accepted - resuming measurement...")
                elif action == 'stop_task' and hasattr(self, 'gamry_control_panel'):
                    from gui.base.device_control_base import ControlPanelState
                    self.gamry_control_panel.set_state(ControlPanelState.IDLE)
            else:
                error = response.get('error', {})
                self._log(f"{action} failed: {error.get('message', 'Unknown error')}")
                self._show_warning('error', f"{action}: {error.get('message', 'Failed')}")
                self._rollback_gamry_panel_state(action)
        except Exception as e:
            self._log(f"{action} error: {e}")
            self._show_warning('error', f"{action} error: {e}")
            self._rollback_gamry_panel_state(action)

    def _rollback_gamry_panel_state(self, action: str) -> None:
        """Restore 1WE panel state after a wrapper control failure."""
        if not hasattr(self, 'gamry_control_panel'):
            return

        from gui.base.device_control_base import ControlPanelState

        if action == 'pause_task':
            self.gamry_control_panel.set_state(ControlPanelState.RUNNING)
        elif action == 'continue_task':
            self.gamry_control_panel.set_paused_state()
        elif action == 'stop_task':
            self.gamry_control_panel.set_state(ControlPanelState.IDLE)

    # =========================================================================
    # Device Command Handler (from v2 lines 2451-2547)
    # =========================================================================

    def _on_device_command(self, device: str, action: str, params: dict):
        """Handle command_requested signal from device control panels."""
        # Guard: prevent concurrent execution
        if self.command_dispatcher.is_busy() or (self.sequence_worker and self.sequence_worker.isRunning()):
            QMessageBox.warning(self, "Busy", "A command or sequence is already running. Wait for it to complete.")
            self._log(f"Device command rejected: dispatcher busy")

            sender_panel = self.sender()
            if sender_panel and hasattr(sender_panel, "reset_state"):
                sender_panel.reset_state()
            return

        # Track which panel issued this command
        sender_panel = self.sender()
        if sender_panel and hasattr(sender_panel, "reset_state"):
            self.active_command_panel = sender_panel
        else:
            self.active_command_panel = None

        # Log EIS params compactly
        if device == "gamry" and action == "run_eis":
            eis_summary = {
                "bias_mode": params.get("bias_mode"),
                "f_start": params.get("initial_freq") or params.get("freq_start"),
                "f_end": params.get("final_freq") or params.get("freq_end"),
                "ppd": params.get("points_per_decade"),
                "ac": params.get("ac_voltage") or params.get("ac_amplitude"),
                "dc_v": params.get("dc_voltage"),
                "dc_i": params.get("dc_current"),
                "z_est": params.get("estimated_z") or params.get("z_est_ohm"),
                "session_id": params.get("session_id"),
                # Initial Delay params
                "init_delay": params.get("initial_delay_enabled"),
                "init_delay_s": params.get("initial_delay_time_s"),
            }
            self._log(f"Device command: {device}.{action} {eis_summary}")
        else:
            self._log(f"Device command: {device}.{action}({params})")

        # Calculate timeout dynamically
        timeout_s = calculate_technique_timeout(action, params)

        # Store target cycles for CV/LSV display (will be used in _on_command_started)
        if device == 'gamry' and action in ('run_cv', 'run_lsv'):
            self._pending_target_cycles = params.get('cycles', params.get('num_cycles', 0))
        else:
            self._pending_target_cycles = 0

        # Generate organized output_dir for single Gamry technique runs
        output_dir = None
        if device == "gamry" and action.startswith("run_"):
            profile = params.get('profile')
            if profile:
                timestamp = datetime.now().strftime("%H%M%S")
                date_str = datetime.now().strftime("%Y-%m-%d")
                technique = action.replace('run_', '').upper()
                if technique == 'CELL_OFF_WAIT':
                    technique = 'STANDBY'

                operator = profile.get('operator', 'Unknown')
                sample_id = profile.get('sample_id', '')

                base_dir = self.repo_root / "runs" / date_str / operator
                if sample_id:
                    base_dir = base_dir / sample_id

                session_id = f"{operator}_{technique}_{timestamp}"
                session_folder = base_dir / session_id

                output_dir = str(session_folder)

                params['session_id'] = session_id
                params['output_dir'] = str(base_dir)

                self._log(f"  Session ID: {session_id}")
                self._log(f"  Session folder: {session_folder}")

        # Dispatch
        success = self.command_dispatcher.execute_command(device, action, params, timeout_s=timeout_s, dry_run=False, output_dir=output_dir)

        if not success:
            self._log("Command rejected: dispatcher busy")
            QMessageBox.warning(self, "Dispatch Failed", "Failed to dispatch command (dispatcher busy)")
            if self.active_command_panel:
                self.active_command_panel.reset_state()
                self.active_command_panel = None
        else:
            self.is_adhoc_sequence = True

    # =========================================================================
    # Command Dispatcher Signal Handlers (from v2 lines 2549-2760)
    # =========================================================================

    def _on_command_started(self, device: str, action: str, output_dir: str):
        """Handle command_started signal from CommandDispatcher (from v2 lines 2549-2585)."""
        self._log(f"Command started: {device}.{action} → {output_dir}")

        self._clear_warning()

        # Clear plot for new Gamry measurement
        if device == 'gamry' and action.startswith('run_'):
            technique_map = {
                'run_cv': 'cv', 'run_lsv': 'lsv',
                'run_ca': 'ca', 'run_cp': 'cp',
                'run_ocv': 'ocv', 'run_eis': 'eis',
            }
            technique = technique_map.get(action, 'cv')
            self._current_technique = technique

            if hasattr(self, 'plot_widget') and self.plot_widget:
                self.plot_widget.clear()
                self.plot_widget.set_technique(technique)

                # Set target cycles for CV/LSV from stored params
                if technique in ('cv', 'lsv') and hasattr(self, '_pending_target_cycles'):
                    self.plot_widget.set_target_cycles(self._pending_target_cycles)
                    self._pending_target_cycles = 0

            # Clear Vocv buffer for new OCV run
            if technique == 'ocv':
                self._vocv_buffer.clear()
                self._vocv_update_counter = 0
                if hasattr(self, 'gamry_control_panel') and hasattr(self.gamry_control_panel, 'panels'):
                    ocv_panel = self.gamry_control_panel.panels.get('ocv')
                    if ocv_panel and hasattr(ocv_panel, 'reset_vocv_estimate'):
                        ocv_panel.reset_vocv_estimate()

        if device == 'gamry' and hasattr(self, '_gamry_sequence_manifest_dir'):
            self.current_manifest_path = Path(self._gamry_sequence_manifest_dir) / "manifest.json"
        else:
            self.current_manifest_path = Path(output_dir) / "manifest.json"
        self.manifest_timer.start()

    def _on_command_completed_dispatcher(self, device: str, action: str, result: dict):
        """Handle command_completed signal from CommandDispatcher (from v2 lines 2587-2674)."""
        self._log(f"Command completed: {device}.{action}")
        self.manifest_timer.stop()

        # Flush streaming data
        if hasattr(self, 'plot_widget') and self.plot_widget:
            self.plot_widget.finish_streaming()
            try:
                self.plot_widget.controller.set_state('COMPLETE')
            except Exception as e:
                self._log(f"Warning: set_state('COMPLETE') failed: {e}")

        # Check if part of a sequence (use executor state, not legacy attributes)
        is_array_sequence = self._is_array_run_active() and device == 'gamry'
        is_gamry_only_sequence = self.gamry_executor and self.gamry_executor.is_running() and device == 'gamry'
        is_mixed_sequence = self.mixed_executor and self.mixed_executor.is_running() and device == 'gamry'
        is_sequence_step = is_array_sequence or is_gamry_only_sequence or is_mixed_sequence

        # Load artifacts for non-sequence runs
        if device == 'gamry' and action.startswith('run_') and not is_sequence_step:
            self._load_gamry_artifacts_to_plot(action, result)

        # Route to executor if in sequence
        if is_array_sequence:
            self.array_executor.handle_gamry_step_result(success=True, result=result)
            return
        elif is_gamry_only_sequence:
            self.gamry_executor.handle_step_result(success=True, result=result)
            return
        elif is_mixed_sequence:
            self.mixed_executor.handle_gamry_step_result(success=True, result=result)
            return

        # Generate exports for single technique runs
        if device == 'gamry' and action.startswith('run_'):
            try:
                self._generate_sequence_exports(result, skip_sequence_info=True)
            except Exception as e:
                self._log(f"Warning: Failed to generate exports: {e}")

        # Notify panel
        if self.active_command_panel:
            self.active_command_panel.set_state_idle()
            self.active_command_panel.notify_completion(success=True, message="Command completed successfully")
            self.active_command_panel = None

        self.is_adhoc_sequence = False

    def _on_command_failed_dispatcher(self, device: str, action: str, error_message: str):
        """Handle command_failed signal from CommandDispatcher (from v2 lines 2676-2710)."""
        self._log(f"Command failed: {device}.{action} - {error_message}")
        self.manifest_timer.stop()

        self._show_warning('error', f"{device}.{action} failed: {error_message}")

        # Route to executor if in sequence (use executor state, not legacy attributes)
        if device == 'gamry':
            if self._is_array_run_active():
                self.array_executor.handle_gamry_step_result(success=False, error_msg=error_message, result=None)
                return
            elif self.gamry_executor and self.gamry_executor.is_running():
                self.gamry_executor.handle_step_result(success=False, error_msg=error_message)
                return
            elif self.mixed_executor and self.mixed_executor.is_running():
                self.mixed_executor.handle_gamry_step_result(success=False, error_msg=error_message)
                return

        # Notify panel of failure
        if self.active_command_panel:
            self.active_command_panel.set_state_error(error_message)
            self.active_command_panel.notify_completion(success=False, message=error_message)
            self.active_command_panel = None

        self.is_adhoc_sequence = False

        QMessageBox.critical(self, "Command Failed", f"{device}.{action} failed:\n{error_message}")

    def _on_command_interrupted_dispatcher(self, device: str, action: str):
        """Handle command_interrupted signal (user-initiated stop) - from v2 lines 2712-2760."""
        self._log(f"Command interrupted: {device}.{action} (user stop)")
        self.manifest_timer.stop()

        self._show_warning('warning', f"{device}.{action} stopped by user")

        # Check if part of array sequence
        if self._is_array_run_active() and device == 'gamry':
            self._log("Array sequence interrupted by user")
            self.array_executor.stop_now()
            return

        # Check if part of Gamry-only sequence (use executor state, not legacy attributes)
        if self.gamry_executor and self.gamry_executor.is_running() and device == 'gamry':
            self._log("Gamry sequence interrupted by user")
            self.gamry_executor.stop_now()
            return

        # Check if part of mixed sequence (use executor state, not legacy attributes)
        if self.mixed_executor and self.mixed_executor.is_running():
            self._log("Mixed sequence interrupted by user")
            self.mixed_executor.stop_now()
            return

        if device == 'gamry' and action.startswith('run_'):
            try:
                self._generate_sequence_exports({}, skip_sequence_info=True)
            except Exception as exc:
                self._log(f"Warning: Failed to generate interrupted exports: {exc}")

        # Reset panel
        if self.active_command_panel:
            from gui.base.device_control_base import ControlPanelState
            self.active_command_panel.set_state(ControlPanelState.IDLE)
            self.active_command_panel = None

        if hasattr(self, 'gamry_control_panel'):
            from gui.base.device_control_base import ControlPanelState
            self.gamry_control_panel.set_state(ControlPanelState.IDLE)

        self.is_adhoc_sequence = False

    # =========================================================================
    # Sequence Handlers (from v2 lines 2762-3250)
    # =========================================================================

    def _on_add_step_from_panel(self, technique: str, params: dict):
        """Handle add_step_requested from GamryControlPanel — add step to sequence table."""
        if hasattr(self, 'sequence_table') and self.sequence_table:
            self.sequence_table._add_gamry_step(technique)

    def _on_gamry_sequence_requested(self, steps: list, profile):
        """Handle sequence_run_requested from GamryControlPanel."""
        self.gamry_executor.start(steps, profile)

    def _on_sequence_table_run(self, steps: list):
        """Handle run_sequence_requested from SequenceTableWidget (from v2 lines 2766-2787)."""
        devices_used = set(s.get('device', 'gamry') for s in steps)
        has_pi = 'pi_xyz' in devices_used
        has_gamry = 'gamry' in devices_used

        # Show profile dialog if enabled
        profile = None
        if has_gamry and hasattr(self, 'gamry_control_panel') and self.gamry_control_panel.profile_checkbox.isChecked():
            profile = self.gamry_control_panel._show_profile_dialog()
            if profile is None:
                self._log("Sequence cancelled - no profile")
                return

        # Select executor based on devices used
        if has_pi:
            executor = self.mixed_executor
        else:
            executor = self.gamry_executor

        # Start execution and pass executor to sequence table for live editing
        started = executor.start(steps, profile)
        if started:
            self.sequence_table.set_executor(executor)

    def _on_mixed_step_completed(self, success: bool, error_msg: str = ""):
        """Handle mixed sequence step completion (cross-thread signal handler)."""
        if self.mixed_executor and self.mixed_executor.is_running():
            # This is routed via the executor's internal signal
            pass

    # =========================================================================
    # Array Mode Handlers (from v2 lines 3449-4400)
    # =========================================================================

    def _on_run_array_sequence(self, config: ArraySequenceConfig):
        """Handle array mode run request."""
        profile = None
        if hasattr(self, 'gamry_control_panel') and self.gamry_control_panel.profile_checkbox.isChecked():
            profile = self.gamry_control_panel._show_profile_dialog()
            if profile is None:
                self._log("Array sequence cancelled - no profile")
                return

        # Set explicit flag BEFORE starting (like v2)
        self._array_run_active = True
        started = self.array_executor.start(config=config, profile=profile)
        if not started:
            self._array_run_active = False

    def _on_array_stop(self):
        """Handle array stop request."""
        if self.array_executor:
            self.array_executor.stop()
            # Flag will be cleared by execution_completed signal

    def _on_array_stop_now(self):
        """Handle array immediate stop request."""
        if self.array_executor:
            self.array_executor.stop_now()
            # Flag will be cleared by execution_completed signal

    def _on_array_pause(self):
        """Handle array pause request."""
        if self.array_executor:
            self.array_executor.pause()

    def _on_array_resume(self):
        """Handle array resume request."""
        if self.array_executor:
            self.array_executor.resume()

    def _on_array_execution_completed(self, result: dict):
        """Handle array execution completion - clear explicit flag."""
        self._array_run_active = False
        self._log(f"Array sequence completed: {result.get('status', 'unknown')}")

    def _is_array_run_active(self) -> bool:
        """Check if array mode is currently running - use explicit flag like v2."""
        return getattr(self, '_array_run_active', False)

    # =========================================================================
    # Export Generation (from v2 lines 4605-4780)
    # =========================================================================

    def _resolve_export_manifest_path(self, result: Optional[dict] = None) -> Optional[Path]:
        """Resolve a manifest path from command results or the active session."""
        candidates: List[Path] = []

        if isinstance(result, dict):
            for key in ('manifest_path', 'output_dir'):
                value = result.get(key)
                if value:
                    candidates.append(Path(value))

            details = result.get('details', {})
            if isinstance(details, dict):
                for key in ('manifest_path', 'output_dir'):
                    value = details.get(key)
                    if value:
                        candidates.append(Path(value))

                nested_results = details.get('results', [])
                if isinstance(nested_results, list):
                    for item in nested_results:
                        if not isinstance(item, dict):
                            continue
                        for key in ('manifest_path', 'output_dir', 'file'):
                            value = item.get(key)
                            if value:
                                candidates.append(Path(value))

        if self.current_manifest_path:
            candidates.append(Path(self.current_manifest_path))

        for candidate in candidates:
            manifest_path = candidate
            if candidate.suffix.lower() == '.csv':
                manifest_path = candidate.parent / "manifest.json"
            elif candidate.is_dir():
                manifest_path = candidate / "manifest.json"
            elif candidate.name.lower() != "manifest.json" and not candidate.suffix:
                manifest_path = candidate / "manifest.json"

            if manifest_path.exists():
                return manifest_path

        return None

    def _generate_sequence_exports(self, result: dict, skip_sequence_info: bool = False):
        """Generate sequence-info.txt and PNG plots."""
        try:
            manifest_path = self._resolve_export_manifest_path(result)
            if manifest_path:
                generate_sequence_exports(manifest_path, self._log, skip_sequence_info)
        except Exception as e:
            self._log(f"Warning: Failed to generate exports: {e}")

    def _load_gamry_artifacts_to_plot(self, action: str, result: dict):
        """Load Gamry artifacts to plot widget."""
        technique_map = {
            'run_cv': 'cv', 'run_lsv': 'lsv',
            'run_ca': 'ca', 'run_cp': 'cp',
            'run_ocv': 'ocv', 'run_eis': 'eis',
        }
        technique = technique_map.get(action, 'cv')

        artifacts = extract_artifacts_from_result(result)
        if artifacts and hasattr(self, 'plot_widget') and self.plot_widget:
            self.plot_widget.load_from_artifacts(artifacts, technique)

    # =========================================================================
    # Streaming Data Handler (from v2 lines 5059-5098)
    # =========================================================================

    def _on_streaming_data_point(self, event: dict):
        """Handle streaming data_point from wrapper (real-time plot updates)."""
        technique = event.get('technique', 'cv').lower()
        data = event.get('data', {})

        # Check for overload conditions
        over_flags = data.get('over_flags', 0)
        if over_flags:
            overloads = []
            if data.get('over_i_ovld'):
                overloads.append('Current overload')
            if data.get('over_v_ovld'):
                overloads.append('Voltage overload')
            if data.get('over_ca_ovld'):
                overloads.append('Control amp overload')
            if overloads:
                self._show_warning('warning', f"Hardware: {', '.join(overloads)}")

        # Update plot widget
        if hasattr(self, 'plot_widget') and self.plot_widget:
            self.plot_widget.add_data_point(data)

        # Accumulate OCV data for Vocv estimation
        if self._current_technique == 'ocv' and technique == 'ocv':
            vf = data.get('vf')
            time_s = data.get('time_s', data.get('t', data.get('time')))

            if vf is not None and time_s is not None:
                self._vocv_buffer.add_point(float(vf), float(time_s))
                self._vocv_update_counter += 1

                if self._vocv_update_counter % 10 == 0:
                    self._update_vocv_estimate()

    # =========================================================================
    # Vocv Estimation (from v2 lines 5100-5159)
    # =========================================================================

    def _update_vocv_estimate(self):
        """Compute and display live Vocv estimate during OCV run."""
        if not hasattr(self, 'gamry_control_panel') or not hasattr(self.gamry_control_panel, 'panels'):
            return

        ocv_panel = self.gamry_control_panel.panels.get('ocv')
        if not ocv_panel:
            return

        utilize_vocv = getattr(ocv_panel, 'utilize_vocv_var', None)
        if not utilize_vocv or not utilize_vocv.get():
            return

        vocv_mode = 'average'
        if hasattr(ocv_panel, 'vocv_mode_var'):
            vocv_mode = ocv_panel.vocv_mode_var.get() or 'average'

        estimate = self._vocv_buffer.compute_estimate(mode=vocv_mode)

        ocv_panel.update_live_vocv_estimate(estimate)
        self._update_vocv_status_bar(estimate)

    def _update_vocv_status_bar(self, estimate: dict):
        """Update the persistent Vocv status bar."""
        if not hasattr(self, 'vocv_value_label'):
            return

        status = estimate.get('status', 'no_data')
        value = estimate.get('value_V', 0.0)
        std_dev = estimate.get('std_dev_V', 0.0)

        if status == 'stable':
            text = f"{value:.6f} V  ±{std_dev*1000:.2f} mV  [Stable]"
            self.vocv_value_label.setStyleSheet("color: #008800; font-weight: bold;")
        elif status == 'stabilizing':
            text = f"{value:.6f} V  (stabilizing...)"
            self.vocv_value_label.setStyleSheet("color: #cc6600; font-weight: bold;")
        else:
            text = "N/A"
            self.vocv_value_label.setStyleSheet("color: #0066cc; font-weight: bold;")

        self.vocv_value_label.setText(text)

    def _reset_vocv_status_bar(self):
        """Reset the persistent Vocv status bar to N/A."""
        if hasattr(self, 'vocv_value_label'):
            self.vocv_value_label.setText("N/A")
            self.vocv_value_label.setStyleSheet("color: #0066cc; font-weight: bold;")

    # =========================================================================
    # Resource Monitor Handlers (Phase 3A: Reliability)
    # =========================================================================

    def _on_memory_warning(self, current_mb: int, threshold_mb: int):
        """Handle memory warning signal from ResourceMonitor."""
        self._log(f"Memory warning: {current_mb}MB (threshold: {threshold_mb}MB)")
        self._show_warning(
            "warning",
            f"Memory usage high: {current_mb}MB - consider saving work"
        )
        event_log.system("memory_warning", current_mb=current_mb, threshold_mb=threshold_mb)

    def _on_memory_critical(self, current_mb: int, threshold_mb: int):
        """Handle memory critical signal from ResourceMonitor."""
        self._log(f"CRITICAL: Memory usage {current_mb}MB exceeds {threshold_mb}MB!")
        self._show_warning(
            "error",
            f"CRITICAL: Memory {current_mb}MB - save immediately!"
        )
        event_log.error("memory", f"Critical memory usage: {current_mb}MB")

        # Show dialog for critical memory
        QMessageBox.warning(
            self,
            "Critical Memory Usage",
            f"Memory usage has reached {current_mb}MB.\n\n"
            f"Please save your work and consider:\n"
            f"- Closing unused plots or data\n"
            f"- Reducing sequence complexity\n"
            f"- Restarting the application if needed",
            QMessageBox.Ok
        )

    def _on_disk_warning(self, free_gb: float, threshold_gb: float, path: str):
        """Handle disk warning signal from ResourceMonitor."""
        self._log(f"Disk warning: {free_gb:.1f}GB free at {path} (threshold: {threshold_gb}GB)")
        self._show_warning(
            "warning",
            f"Low disk space: {free_gb:.1f}GB free"
        )
        event_log.system("disk_warning", free_gb=free_gb, path=path)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _log(self, message: str):
        """Append message to log widget."""
        self.log_widget.append_log(message)

    def _show_warning(self, level: str, message: str):
        """Show message in warning bar."""
        if hasattr(self, 'warning_bar') and self.warning_bar:
            self.warning_bar.show_message(level, message)

    def _clear_warning(self):
        """Clear the warning bar."""
        if hasattr(self, 'warning_bar') and self.warning_bar:
            self.warning_bar.clear()

    # =========================================================================
    # Close Event (from v2 lines 5040-5057)
    # =========================================================================

    def closeEvent(self, event):
        """Handle window close."""
        self._log("Shutting down...")

        # Stop resource monitor
        if hasattr(self, '_resource_monitor'):
            self._resource_monitor.stop()

        # Disconnect Thorlabs if connected
        if self._thorlabs_device:
            try:
                if self._thorlabs_device.is_connected():
                    self._thorlabs_device.disconnect_async()
            except Exception as e:
                logger.warning(f"Error disconnecting Thorlabs: {e}")

        # Disconnect PI if connected
        if self._pi_device:
            try:
                if self._pi_device.is_connected():
                    self._pi_device.disconnect_async()
            except Exception as e:
                logger.warning(f"Error disconnecting PI: {e}")

        # Disconnect Gamry if connected
        if self._gamry_device:
            try:
                if self._gamry_device.is_connected():
                    self._gamry_device.disconnect_async()
            except Exception as e:
                logger.warning(f"Error disconnecting Gamry: {e}")

        self.supervisor_service.stop_service()
        self.supervisor_service.wait(3000)
        event.accept()


def main():
    """Launch GOED GUI v3."""
    from app.bootstrap import main as bootstrap_main
    bootstrap_main()


def main_no_splash():
    """Launch GOED GUI v3 without splash."""
    from app.bootstrap import main_no_splash as bootstrap_no_splash
    bootstrap_no_splash()


if __name__ == "__main__":
    if "--no-splash" in sys.argv:
        main_no_splash()
    else:
        main()
