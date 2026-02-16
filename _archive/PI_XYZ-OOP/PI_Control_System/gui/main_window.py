"""
Main window assembling all GUI components.

Responsibilities:
- Instantiate widgets and controller
- Layout UI panels (connection, position, controls, log)
- Apply window styling consistent with legacy GUI

Source: legacy/PI_Control_GUI/main_gui.py UI structure
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
                                QScrollArea, QMessageBox, QStackedWidget, QRadioButton, QLabel)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCloseEvent

from ..services.event_bus import EventBus
from ..services.connection_service import ConnectionService
from ..services.motion_service import MotionService

from .main_window_controller import MainWindowController
from .widgets.connection_panel import ConnectionPanel
from .widgets.position_display import PositionDisplayWidget
from .widgets.velocity_panel import VelocityPanel
from .widgets.manual_jog import ManualJogWidget
from .widgets.sequence_panel import SequencePanel
from .widgets.system_log import SystemLogWidget


class MainWindow(QMainWindow):
    """Main application window for PI stage control.

    Assembles all widgets and wires them through MainWindowController.
    Matches legacy GUI styling (gradient background, card layout).
    """

    def __init__(self,
                 event_bus: EventBus,
                 connection_service: ConnectionService,
                 motion_service: MotionService,
                 park_position: float = 200.0):
        """Initialize main window.

        Args:
            event_bus: EventBus for inter-service communication
            connection_service: Connection service instance
            motion_service: Motion service instance
            park_position: Park position for all axes (default 200.0)
        """
        super().__init__()

        self.event_bus = event_bus
        self.connection_service = connection_service
        self.motion_service = motion_service
        self.park_position = park_position

        # Setup window
        self.setWindowTitle("PI Stage Control System")
        self.setGeometry(100, 100, 1400, 800)
        self._apply_window_style()

        # Create controller
        self.controller = MainWindowController(
            event_bus=event_bus,
            connection_service=connection_service,
            motion_service=motion_service,
            park_position=park_position
        )

        # Build UI
        self._create_widgets()
        self._create_layout()

        # Wire widgets to controller
        self.controller.set_widgets(
            self.connection_panel,
            self.position_display,
            self.velocity_panel,
            self.manual_jog,
            self.sequence_panel,
            self.system_log
        )

    def _apply_window_style(self):
        """Apply gradient background styling (matches legacy GUI)."""
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0D1D55,
                    stop:0.5 #1E3A5F,
                    stop:1 #0D1D55
                );
            }
        """)

    def _create_widgets(self):
        """Instantiate all widget components."""
        self.connection_panel = ConnectionPanel()
        self.position_display = PositionDisplayWidget()
        self.velocity_panel = VelocityPanel(max_velocity=20.0, default_velocity=20.0)
        self.manual_jog = ManualJogWidget(default_step=1.0)
        self.sequence_panel = SequencePanel()
        self.system_log = SystemLogWidget()

    def _create_layout(self):
        """Assemble widget layout."""
        # Content widget with layout
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Top row: Connection + Position
        top_row = QHBoxLayout()
        top_row.addWidget(self._card_wrap(self.connection_panel))
        top_row.addWidget(self._card_wrap(self.position_display))
        main_layout.addLayout(top_row)

        # Velocity panel
        main_layout.addWidget(self._card_wrap(self.velocity_panel))

        # Mode switcher + stacked control (manual/sequence)
        main_layout.addWidget(self._create_mode_switcher())
        main_layout.addWidget(self._create_control_stack(), stretch=1)

        # Bottom: System Log
        main_layout.addWidget(self._card_wrap(self.system_log), stretch=1)

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll_area)

    def _card_wrap(self, widget: QWidget) -> QFrame:
        """Wrap widget in styled card frame.

        Args:
            widget: Widget to wrap

        Returns:
            Frame with card styling containing widget
        """
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(56, 104, 140, 0.3), stop:1 rgba(13, 29, 85, 0.3));
                border: 2px solid rgba(99, 179, 194, 0.3);
                border-radius: 12px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.addWidget(widget)

        return card

    def _create_mode_switcher(self) -> QFrame:
        """Create mode switch card (Manual/Automatic).

        Source: legacy/PI_Control_GUI/main_gui.py:354-370
        """
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(56, 104, 140, 0.3), stop:1 rgba(13, 29, 85, 0.3));
                border: 2px solid rgba(99, 179, 194, 0.3);
                border-radius: 12px;
                padding: 15px;
            }
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Control Mode")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        layout.addSpacing(30)

        self.manual_radio = QRadioButton("Manual Control")
        self.manual_radio.setChecked(True)
        self.manual_radio.setStyleSheet("""
            QRadioButton {
                color: #e2e8f0;
                font-size: 11pt;
                font-weight: bold;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.manual_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.manual_radio)

        layout.addSpacing(30)

        self.auto_radio = QRadioButton("Automated Sequence")
        self.auto_radio.setStyleSheet("""
            QRadioButton {
                color: #e2e8f0;
                font-size: 11pt;
                font-weight: bold;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.auto_radio.toggled.connect(self._on_mode_changed)
        layout.addWidget(self.auto_radio)

        layout.addStretch()

        return card

    def _create_control_stack(self) -> QFrame:
        """Create stacked widget for manual/sequence controls."""
        self.control_stack = QStackedWidget()

        # Page 0: Manual jog
        self.control_stack.addWidget(self._card_wrap(self.manual_jog))

        # Page 1: Sequence
        self.control_stack.addWidget(self._card_wrap(self.sequence_panel))

        return self.control_stack

    def _on_mode_changed(self):
        """Handle mode switch."""
        if self.manual_radio.isChecked():
            self.control_stack.setCurrentIndex(0)
        else:
            self.control_stack.setCurrentIndex(1)

    def closeEvent(self, event: QCloseEvent):
        """Handle window close - park and disconnect hardware.

        Source: legacy/PI_Control_GUI/main_gui.py:758-771
        """
        from ..core.models import ConnectionState

        # Check if connected
        if self.connection_service.state.connection == ConnectionState.DISCONNECTED:
            event.accept()
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            'Confirm Exit',
            'Park axes and disconnect from hardware?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            event.ignore()
            return

        try:
            # Park all axes first
            if self.connection_service.state.connection == ConnectionState.READY:
                park_future = self.motion_service.park_all(self.park_position)
                park_future.result(timeout=30)  # Wait up to 30s for parking

            # Then disconnect (returns None, not a Future)
            self.connection_service.disconnect()

            event.accept()
        except Exception as e:
            # If parking/disconnect fails, ask user if they still want to exit
            reply = QMessageBox.warning(
                self,
                'Exit Error',
                f'Error during shutdown: {str(e)}\n\nForce exit anyway?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
