import sys
from gui.thorlabs_control_panel import ThorlabsControlPanel
from gui.pi_control_panel import PIControlPanel
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTabWidget, QLabel, QTextEdit
)
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Catalyst Automation")
        self.resize(1200, 700)

        self._create_main_layout()

    def _create_main_layout(self):
        """Create main layout with left / center / right columns."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        outer_layout.setSpacing(5)

        # Main horizontal splitter: LEFT | CENTER | RIGHT
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---------- LEFT: device control tabs (PI, Thorlabs) ----------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        self.device_tabs = QTabWidget()
        # For now, just placeholder widgets; later you plug in real panels
        self.pi_tab = PIControlPanel()
        self.device_tabs.addTab(self.pi_tab, "PI XYZ")

        self.thorlabs_tab = ThorlabsControlPanel()
        self.device_tabs.addTab(self.thorlabs_tab, "Thorlabs")

        left_layout.addWidget(self.device_tabs)
        main_splitter.addWidget(left_widget)

        # ---------- CENTER: plot + log (vertical splitter) ----------
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(5)

        center_splitter = QSplitter(Qt.Orientation.Vertical)

        # Placeholder "plot" area
        self.plot_area = QLabel("Plot / live view will go here")
        self.plot_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_splitter.addWidget(self.plot_area)

        # Log area
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setPlaceholderText("Log output will appear here...")
        center_splitter.addWidget(self.log_widget)

        # Give more space to plot than log initially
        center_splitter.setSizes([400, 200])

        center_layout.addWidget(center_splitter)
        main_splitter.addWidget(center_widget)

        # ---------- RIGHT: device status (placeholder) ----------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)

        right_label = QLabel("Device status tiles / info will go here")
        right_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right_layout.addWidget(right_label)

        main_splitter.addWidget(right_widget)

        # Set initial column widths: Left 25%, Center 50%, Right 25%
        main_splitter.setSizes([300, 600, 300])

        outer_layout.addWidget(main_splitter)
