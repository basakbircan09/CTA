import os
import sys
from pathlib import Path
from openpyxl import Workbook

# Set up project root and paths FIRST
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Add PI DLL directory to PATH before any PI imports
os.environ['PATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PATH', '')

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox, QTextEdit,
    QFileDialog, QGroupBox, QGridLayout, QDoubleSpinBox, QComboBox,
    QDialog, QGraphicsView, QGraphicsScene, QScrollArea, QCheckBox,
)
from PySide6.QtGui import (
    QPixmap, QImage, QPen, QBrush, QColor, QFont, QPainter,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF

# Hardware / vision imports
from device_drivers.PI_Control_System.core.models import Axis, Position
from device_drivers.PI_Control_System.app_factory import create_services
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.GPT_Merge import analyze_plate_and_spots
from device_drivers.spot_analysis.pipeline import run_spot_analysis
from device_drivers.image_utils import load_image, save_image, bgr_to_rgb
from device_drivers.spot_alignment import SpotAligner, AlignmentResult


# ---------------------------------------------------------------------------
# Background worker – keeps WE Detect off the UI thread
# ---------------------------------------------------------------------------

class SpotAnalysisWorker(QThread):
    """Run run_spot_analysis() in a background thread."""
    finished = Signal(dict)
    error    = Signal(str)

    def __init__(self, image_path: str, output_dir: str) -> None:
        super().__init__()
        self.image_path = image_path
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            result = run_spot_analysis(
                image_path=self.image_path,
                output_dir=self.output_dir,
                export_excel=True,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Spot alignment motion worker – executes a pre-computed MotionStep list
# ---------------------------------------------------------------------------

class SpotAlignmentWorker(QThread):
    """Execute a list of MotionStep objects on the stage in a background thread.

    Each step moves to an absolute (x, y, z) position.  The step order
    already encodes all Z-safety rules (raise before XY, lower after).
    """
    step_done = Signal(str)     # description of the completed step
    finished  = Signal()
    error     = Signal(str)

    def __init__(self, motion_service, steps: list) -> None:
        super().__init__()
        self.motion_service = motion_service
        self.steps          = steps          # list[MotionStep]

    def run(self) -> None:
        try:
            for step in self.steps:
                target = Position(
                    x=step.target_x,
                    y=step.target_y,
                    z=step.target_z,
                )
                self.motion_service.move_to_position_safe_z(target).result(timeout=120)
                self.step_done.emit(step.description)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Manual spot picker – Qt scene that emits left-click coordinates
# ---------------------------------------------------------------------------

class _SpotScene(QGraphicsScene):
    spot_clicked = Signal(float, float)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.scenePos()
            self.spot_clicked.emit(p.x(), p.y())
        super().mousePressEvent(event)


class _SpotView(QGraphicsView):
    """Graphics view with scroll-wheel zoom."""

    def wheelEvent(self, event) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)


class ManualSpotDialog(QDialog):
    """Interactive spot-picker dialog.

    Left-click to place numbered spot markers (S1, S2, ...).
    Click 'Set Reference' then left-click to place the Reference marker.
    Scroll wheel zooms in/out.  Undo removes the last regular spot.
    Done saves an Excel file + annotated image and closes.
    """

    def __init__(self, image_bgr, save_dir: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manual Spot Detect  -  left-click to mark spots")
        self.resize(1100, 750)

        self._spots: list[dict] = []
        self._marker_items: list[tuple] = []   # (ellipse, text) per spot
        self._ref_spot: dict | None = None
        self._ref_items: tuple | None = None   # (ellipse, text) for reference
        self._next_is_ref: bool = False
        self._save_dir = save_dir

        # Convert BGR ndarray to QPixmap
        img_rgb = bgr_to_rgb(image_bgr)
        h, w, ch = img_rgb.shape
        qimg    = QImage(img_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap  = QPixmap.fromImage(qimg)

        # Scene
        self._scene = _SpotScene(self)
        self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self._scene.spot_clicked.connect(self._on_scene_click)

        # View
        self._view = _SpotView(self._scene, self)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._view.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._view.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

        # Status and buttons
        self._lbl_count = QLabel("Spots marked: 0")
        self._lbl_mode  = QLabel("Mode: Mark Spots  |  Reference: Not set")
        self._lbl_mode.setStyleSheet("color: #888;")

        self._btn_set_ref = QPushButton("Set Reference")
        btn_undo          = QPushButton("Undo Last")
        btn_clear         = QPushButton("Clear All")
        btn_done          = QPushButton("Done")
        btn_done.setDefault(True)

        self._btn_set_ref.clicked.connect(self._toggle_ref_mode)
        btn_undo.clicked.connect(self._undo)
        btn_clear.clicked.connect(self._clear)
        btn_done.clicked.connect(self._finish)

        hint = QLabel("Scroll = zoom   |   Left-click = mark spot")
        hint.setStyleSheet("color: #888;")

        top_bar = QHBoxLayout()
        top_bar.addWidget(hint)
        top_bar.addStretch()
        top_bar.addWidget(self._lbl_mode)

        bot_bar = QHBoxLayout()
        bot_bar.addWidget(self._lbl_count)
        bot_bar.addStretch()
        bot_bar.addWidget(self._btn_set_ref)
        bot_bar.addWidget(btn_undo)
        bot_bar.addWidget(btn_clear)
        bot_bar.addWidget(btn_done)

        layout = QVBoxLayout(self)
        layout.addWidget(self._view, stretch=1)
        layout.addLayout(top_bar)
        layout.addLayout(bot_bar)

    # ------------------------------------------------------------------
    # Slot called by _SpotScene on left-click
    # ------------------------------------------------------------------

    def _on_scene_click(self, sx: float, sy: float) -> None:
        rect = self._scene.sceneRect()
        if not rect.contains(sx, sy):
            return
        x, y = int(round(sx)), int(round(sy))
        if self._next_is_ref:
            self._next_is_ref = False
            self._btn_set_ref.setStyleSheet("")
            self._add_reference(x, y)
        else:
            self._add_spot(x, y)

    def _add_spot(self, x: int, y: int) -> None:
        idx   = len(self._spots) + 1
        label = f"S{idx}"
        self._spots.append({"label": label, "x": x, "y": y})

        r    = 10
        pen  = QPen(QColor(0, 60, 180), 2)
        fill = QBrush(QColor(0, 60, 180, 90))
        circle = self._scene.addEllipse(x - r, y - r, 2 * r, 2 * r, pen, fill)

        txt = self._scene.addText(label)
        txt.setDefaultTextColor(QColor(30, 100, 255))
        fnt = QFont("Arial", 11, QFont.Weight.Bold)
        txt.setFont(fnt)
        txt.setPos(x + r + 2, y - 14)

        self._marker_items.append((circle, txt))
        self._lbl_count.setText(f"Spots marked: {idx}")

    def _add_reference(self, x: int, y: int) -> None:
        # Remove previous reference marker if any
        if self._ref_items:
            for item in self._ref_items:
                self._scene.removeItem(item)
            self._ref_items = None

        self._ref_spot = {"label": "Reference", "x": x, "y": y}

        r    = 12
        pen  = QPen(QColor(255, 140, 0), 2)
        fill = QBrush(QColor(255, 140, 0, 100))
        circle = self._scene.addEllipse(x - r, y - r, 2 * r, 2 * r, pen, fill)

        txt = self._scene.addText("REF")
        txt.setDefaultTextColor(QColor(255, 140, 0))
        fnt = QFont("Arial", 11, QFont.Weight.Bold)
        txt.setFont(fnt)
        txt.setPos(x + r + 2, y - 14)

        self._ref_items = (circle, txt)
        self._update_mode_label()

    def _toggle_ref_mode(self) -> None:
        self._next_is_ref = not self._next_is_ref
        if self._next_is_ref:
            self._btn_set_ref.setStyleSheet(
                "background-color: #ff8800; color: white; font-weight: bold;"
            )
            self._lbl_mode.setText("Mode: PLACE REFERENCE - click on image")
            self._lbl_mode.setStyleSheet("color: #ff8800; font-weight: bold;")
        else:
            self._btn_set_ref.setStyleSheet("")
            self._update_mode_label()

    def _update_mode_label(self) -> None:
        ref_status = "Set" if self._ref_spot else "Not set"
        self._lbl_mode.setText(f"Mode: Mark Spots  |  Reference: {ref_status}")
        self._lbl_mode.setStyleSheet("color: #888;" if not self._ref_spot
                                     else "color: #ff8800;")

    def _undo(self) -> None:
        if not self._spots:
            return
        self._spots.pop()
        circle, txt = self._marker_items.pop()
        self._scene.removeItem(circle)
        self._scene.removeItem(txt)
        self._lbl_count.setText(f"Spots marked: {len(self._spots)}")

    def _clear(self) -> None:
        for circle, txt in self._marker_items:
            self._scene.removeItem(circle)
            self._scene.removeItem(txt)
        self._spots.clear()
        self._marker_items.clear()

        if self._ref_items:
            for item in self._ref_items:
                self._scene.removeItem(item)
            self._ref_items = None
        self._ref_spot = None

        self._next_is_ref = False
        self._btn_set_ref.setStyleSheet("")
        self._lbl_count.setText("Spots marked: 0")
        self._update_mode_label()

    def _finish(self) -> None:
        has_data = bool(self._spots or self._ref_spot)
        self._excel_path = self._save_excel() if has_data else None
        self._image_path = self._save_image() if has_data else None
        self.accept()

    def _save_excel(self) -> str:
        out = Path(self._save_dir)
        out.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "Manual Spots"
        ws.append(["Label", "X pixel", "Y pixel"])
        # Reference row first
        if self._ref_spot:
            ws.append([self._ref_spot["label"],
                        self._ref_spot["x"],
                        self._ref_spot["y"]])
        for s in self._spots:
            ws.append([s["label"], s["x"], s["y"]])
        path = str(out / "manual_spots.xlsx")
        wb.save(path)
        return path

    def _save_image(self) -> str:
        """Render the scene (image + all markers) to a PNG file."""
        out = Path(self._save_dir)
        out.mkdir(parents=True, exist_ok=True)
        rect    = self._scene.sceneRect()
        img_out = QImage(int(rect.width()), int(rect.height()),
                         QImage.Format_RGB888)
        img_out.fill(Qt.black)
        painter = QPainter(img_out)
        self._scene.render(painter)
        painter.end()
        path = str(out / "manual_spots_image.png")
        img_out.save(path)
        return path

    def get_spots(self) -> list:
        return list(self._spots)

    def get_reference(self) -> dict | None:
        return self._ref_spot

    def excel_path(self) -> str | None:
        return getattr(self, "_excel_path", None)

    def image_path(self) -> str | None:
        return getattr(self, "_image_path", None)


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class SimpleStageApp(QMainWindow):
    def __init__(self, use_mock: bool = True):
        super().__init__()

        # --- PI services ---
        event_bus, connection_service, motion_service, config = create_services(use_mock=use_mock)
        self.event_bus          = event_bus
        self.connection_service = connection_service
        self.motion_service     = motion_service

        # --- Camera ---
        TL_DLL_DIR  = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
        self.camera = ThorlabsCamera(dll_dir=TL_DLL_DIR)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._update_live_view)
        self.live_running = False

        # --- State ---
        self.last_image_path: str | None = None
        self.last_plate_path: str | None = None
        self._we_worker: SpotAnalysisWorker | None = None

        # --- Alignment state ---
        self._manual_reference: dict | None = None   # REF pixel from ManualSpotDialog
        self._manual_spots: list[dict]      = []     # S1..Sn pixels from ManualSpotDialog
        self._align_base_x: float | None    = None   # stage X when image was captured
        self._align_base_y: float | None    = None   # stage Y when image was captured
        self._at_spot: bool                 = False  # True once the stage has reached a spot
        self._align_worker: SpotAlignmentWorker | None = None
        self._current_spot_idx: int         = 0      # tracks next spot for Move Next Spot

        # --- Positions ---
        self.park_position = Position(x=200.0, y=200.0, z=200.0)

        # ================================================================
        # Window layout
        # ================================================================
        self.setWindowTitle("CTA - Stage + Plate Check")
        self.resize(1400, 850)

        central      = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)
        self.setCentralWidget(central)

        # ---- Top toolbar ----
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

        self.status_label = QLabel("DISCONNECTED")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-weight: bold;
                padding: 6px 12px;
                background-color: #2a2a2a;
                border-radius: 4px;
                min-width: 140px;
            }
        """)
        toolbar_layout.addWidget(self.status_label)
        toolbar_layout.addSpacing(10)

        btn_style = """
            QPushButton {
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover   { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #3a3a3a; }
        """

        self.btn_connect      = QPushButton("Connect")
        self.btn_init         = QPushButton("Initialize")
        self.btn_cam_start    = QPushButton("Camera")
        self.btn_capture      = QPushButton("Capture")
        self.btn_plate        = QPushButton("Plate Detect")
        self.btn_we           = QPushButton("WE Detect")
        self.btn_manual_spot  = QPushButton("Manual Spot Detect")

        for btn in [self.btn_connect, self.btn_init, self.btn_cam_start,
                    self.btn_capture, self.btn_plate, self.btn_we,
                    self.btn_manual_spot]:
            btn.setStyleSheet(btn_style)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        outer_layout.addLayout(toolbar_layout)

        # ---- Middle: settings + image ----
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        outer_layout.addLayout(middle_layout, stretch=4)

        # Left panel inside a scroll area so it can be scrolled when content
        # exceeds the window height
        settings_widget = QWidget()
        settings_panel  = QVBoxLayout(settings_widget)
        settings_panel.setSpacing(10)
        settings_panel.setContentsMargins(4, 4, 4, 4)

        left_scroll = QScrollArea()
        left_scroll.setWidget(settings_widget)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMaximumWidth(310)
        middle_layout.addWidget(left_scroll)

        # Camera settings group
        cam_group  = QGroupBox("Camera Settings")
        cam_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cam_layout = QGridLayout(cam_group)
        cam_layout.setSpacing(8)

        cam_layout.addWidget(QLabel("Exposure (ms):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(1.0, 5000.0)
        self.spin_exposure.setValue(100.0)
        self.spin_exposure.setSingleStep(10.0)
        self.spin_exposure.setDecimals(1)
        self.spin_exposure.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_exposure, 0, 1)
        btn_exp = QPushButton("Set")
        btn_exp.clicked.connect(self.on_set_exposure)
        cam_layout.addWidget(btn_exp, 0, 2)

        cam_layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.setDecimals(1)
        self.spin_gain.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_gain, 1, 1)
        btn_gain = QPushButton("Set")
        btn_gain.clicked.connect(self.on_set_gain)
        cam_layout.addWidget(btn_gain, 1, 2)

        cam_layout.addWidget(QLabel("White Balance:"), 2, 0)
        self.combo_wb = QComboBox()
        self.combo_wb.addItems(["Default", "Warm", "Cool", "Reduce NIR", "Custom"])
        self.combo_wb.currentTextChanged.connect(self.on_wb_preset_changed)
        cam_layout.addWidget(self.combo_wb, 2, 1, 1, 2)

        rgb_layout = QHBoxLayout()
        rgb_layout.setSpacing(4)
        for label_text, attr in [("R:", "spin_wb_r"), ("G:", "spin_wb_g"), ("B:", "spin_wb_b")]:
            rgb_layout.addWidget(QLabel(label_text))
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 4.0)
            spin.setValue(1.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.setMaximumWidth(65)
            setattr(self, attr, spin)
            rgb_layout.addWidget(spin)
        rgb_layout.addStretch()
        cam_layout.addLayout(rgb_layout, 3, 0, 1, 3)

        self.btn_apply_wb = QPushButton("Apply White Balance")
        self.btn_apply_wb.clicked.connect(self.on_apply_white_balance)
        cam_layout.addWidget(self.btn_apply_wb, 4, 0, 1, 3)

        settings_panel.addWidget(cam_group)

        # Stage control group
        stage_group  = QGroupBox("Stage Control")
        stage_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        stage_layout = QVBoxLayout(stage_group)
        stage_layout.setSpacing(10)

        self.pos_label = QLabel("Position:  X = ?.??    Y = ?.??    Z = ?.??")
        self.pos_label.setStyleSheet("""
            QLabel {
                font-family: monospace;
                font-size: 12px;
                padding: 8px;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)
        stage_layout.addWidget(self.pos_label)

        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step (mm):"))
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.1, 50.0)
        self.spin_step.setValue(5.0)
        self.spin_step.setSingleStep(1.0)
        self.spin_step.setDecimals(1)
        self.spin_step.setMaximumWidth(80)
        step_layout.addWidget(self.spin_step)
        step_layout.addStretch()
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.on_refresh_position)
        step_layout.addWidget(btn_refresh)
        stage_layout.addLayout(step_layout)

        jog_grid     = QGridLayout()
        jog_grid.setSpacing(6)
        jog_btn_style = """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-width: 50px;
                min-height: 35px;
            }
        """
        for row_idx, (axis, lbl) in enumerate([(Axis.X, "X"), (Axis.Y, "Y"), (Axis.Z, "Z")]):
            axis_lbl = QLabel(f"{lbl}:")
            axis_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            jog_grid.addWidget(axis_lbl, row_idx, 0)
            for col_idx, direction in enumerate([-1, 1]):
                symbol = "-" if direction == -1 else "+"
                btn    = QPushButton(symbol)
                btn.setStyleSheet(jog_btn_style)
                btn.clicked.connect(
                    lambda checked=False, a=axis, d=direction: self.on_jog_axis(a, d)
                )
                jog_grid.addWidget(btn, row_idx, col_idx + 1)
        jog_grid.setColumnStretch(3, 1)
        stage_layout.addLayout(jog_grid)

        separator = QLabel("")
        separator.setStyleSheet("background-color: #3a3a3a; min-height: 1px; max-height: 1px;")
        stage_layout.addWidget(separator)

        goto_layout = QHBoxLayout()
        goto_layout.setSpacing(8)
        goto_layout.addWidget(QLabel("Go to:"))
        self.spin_goto_x = QDoubleSpinBox()
        self.spin_goto_y = QDoubleSpinBox()
        self.spin_goto_z = QDoubleSpinBox()
        for axis_lbl, spin in [("X:", self.spin_goto_x), ("Y:", self.spin_goto_y), ("Z:", self.spin_goto_z)]:
            spin.setRange(0.0, 300.0)
            spin.setValue(200.0)
            spin.setDecimals(2)
            spin.setMaximumWidth(80)
            goto_layout.addWidget(QLabel(axis_lbl))
            goto_layout.addWidget(spin)
        btn_goto = QPushButton("Go")
        btn_goto.setStyleSheet("font-weight: bold; min-width: 60px;")
        btn_goto.clicked.connect(self.on_goto_position)
        goto_layout.addWidget(btn_goto)
        goto_layout.addStretch()
        stage_layout.addLayout(goto_layout)

        settings_panel.addWidget(stage_group)

        # Move to Spot group
        move_spot_group  = QGroupBox("Spot Navigation")
        move_spot_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        move_spot_layout = QGridLayout(move_spot_group)
        move_spot_layout.setSpacing(6)

        move_spot_layout.addWidget(QLabel("Spot:"), 0, 0)
        self.combo_move_spot = QComboBox()
        self.combo_move_spot.setToolTip(
            "Populated automatically after Manual Spot Detect.\n"
            "Select a spot then press Go."
        )
        move_spot_layout.addWidget(self.combo_move_spot, 0, 1)

        self.btn_move_spot = QPushButton("Go")
        self.btn_move_spot.setStyleSheet("font-weight: bold;")
        self.btn_move_spot.setToolTip("Compute alignment for the selected spot and move to it.")
        self.btn_move_spot.clicked.connect(self.on_move_to_spot_clicked)
        move_spot_layout.addWidget(self.btn_move_spot, 0, 2)

        self.btn_move_next = QPushButton("Move Next Spot")
        self.btn_move_next.setStyleSheet("font-weight: bold;")
        self.btn_move_next.setToolTip(
            "Move to the next spot in sequence (S1 → S2 → S3 …).\n"
            "Each click advances one spot so you can supervise every step."
        )
        self.btn_move_next.clicked.connect(self.on_move_next_spot_clicked)
        move_spot_layout.addWidget(self.btn_move_next, 1, 0, 1, 3)

        self.lbl_next_spot = QLabel("Next: —")
        self.lbl_next_spot.setStyleSheet("color: #888; font-size: 11px;")
        move_spot_layout.addWidget(self.lbl_next_spot, 2, 0, 1, 3)

        settings_panel.addWidget(move_spot_group)

        # SFC Calibration group
        sfc_group  = QGroupBox("SFC Calibration")
        sfc_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        sfc_layout = QGridLayout(sfc_group)
        sfc_layout.setSpacing(6)

        sfc_layout.addWidget(QLabel("Holder→SFC X (mm):"), 0, 0)
        self.spin_sfc_offset_x = QDoubleSpinBox()
        self.spin_sfc_offset_x.setRange(-400.0, 400.0)
        self.spin_sfc_offset_x.setValue(0.0)
        self.spin_sfc_offset_x.setSingleStep(0.1)
        self.spin_sfc_offset_x.setDecimals(2)
        sfc_layout.addWidget(self.spin_sfc_offset_x, 0, 1)

        sfc_layout.addWidget(QLabel("Holder→SFC Y (mm):"), 1, 0)
        self.spin_sfc_offset_y = QDoubleSpinBox()
        self.spin_sfc_offset_y.setRange(-400.0, 400.0)
        self.spin_sfc_offset_y.setValue(0.0)
        self.spin_sfc_offset_y.setSingleStep(0.1)
        self.spin_sfc_offset_y.setDecimals(2)
        sfc_layout.addWidget(self.spin_sfc_offset_y, 1, 1)

        sfc_layout.addWidget(QLabel("SFC Z (mm):"), 2, 0)
        self.spin_sfc_z = QDoubleSpinBox()
        self.spin_sfc_z.setRange(0.0, 400.0)
        self.spin_sfc_z.setValue(0.0)
        self.spin_sfc_z.setSingleStep(0.1)
        self.spin_sfc_z.setDecimals(2)
        sfc_layout.addWidget(self.spin_sfc_z, 2, 1)

        sfc_layout.addWidget(QLabel("Ref Stage X (mm):"), 3, 0)
        self.spin_base_x = QDoubleSpinBox()
        self.spin_base_x.setRange(0.0, 400.0)
        self.spin_base_x.setValue(200.0)
        self.spin_base_x.setSingleStep(0.1)
        self.spin_base_x.setDecimals(2)
        self.spin_base_x.setToolTip(
            "Stage X position when the image was captured\n"
            "(i.e. where the holder reference corner sits on the stage)"
        )
        sfc_layout.addWidget(self.spin_base_x, 3, 1)

        sfc_layout.addWidget(QLabel("Ref Stage Y (mm):"), 4, 0)
        self.spin_base_y = QDoubleSpinBox()
        self.spin_base_y.setRange(0.0, 400.0)
        self.spin_base_y.setValue(200.0)
        self.spin_base_y.setSingleStep(0.1)
        self.spin_base_y.setDecimals(2)
        self.spin_base_y.setToolTip(
            "Stage Y position when the image was captured\n"
            "(i.e. where the holder reference corner sits on the stage)"
        )
        sfc_layout.addWidget(self.spin_base_y, 4, 1)

        btn_set_base = QPushButton("Read from Stage")
        btn_set_base.setToolTip(
            "Read current stage XY and store as the reference stage position"
        )
        btn_set_base.clicked.connect(self.on_set_alignment_base)
        sfc_layout.addWidget(btn_set_base, 5, 0, 1, 2)

        settings_panel.addWidget(sfc_group)

        # Alignment Options group
        align_opt_group  = QGroupBox("Alignment Options")
        align_opt_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        align_opt_layout = QGridLayout(align_opt_group)
        align_opt_layout.setSpacing(6)

        self.chk_dry_run = QCheckBox("Dry Run (no stage movement)")
        self.chk_dry_run.setToolTip(
            "When checked: compute offsets, log them, but do NOT move the stage."
        )
        align_opt_layout.addWidget(self.chk_dry_run, 0, 0, 1, 2)

        self.chk_flip_x = QCheckBox("Flip X")
        self.chk_flip_x.setToolTip(
            "Invert the X axis direction when converting pixel offset to stage move.\n"
            "Use this if the stage moves in the wrong X direction."
        )
        align_opt_layout.addWidget(self.chk_flip_x, 1, 0)

        self.chk_flip_y = QCheckBox("Flip Y")
        self.chk_flip_y.setToolTip(
            "Invert the Y axis direction when converting pixel offset to stage move.\n"
            "Use this if the stage moves in the wrong Y direction."
        )
        align_opt_layout.addWidget(self.chk_flip_y, 1, 1)

        align_opt_layout.addWidget(QLabel("Safety limit (mm):"), 2, 0)
        self.spin_max_move = QDoubleSpinBox()
        self.spin_max_move.setRange(0.1, 400.0)
        self.spin_max_move.setValue(10.0)
        self.spin_max_move.setSingleStep(1.0)
        self.spin_max_move.setDecimals(1)
        self.spin_max_move.setToolTip(
            "If the computed XY move exceeds this distance (mm),\n"
            "a warning is shown and confirmation is required before moving."
        )
        align_opt_layout.addWidget(self.spin_max_move, 2, 1)

        settings_panel.addWidget(align_opt_group)
        settings_panel.addStretch()

        # Image display
        self.image_label = QLabel("Live / captured / processed image will appear here")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #666;
                border: 2px solid #333;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        self.image_label.setMinimumSize(800, 500)
        middle_layout.addWidget(self.image_label, stretch=2)

        # ---- Log panel ----
        log_group  = QGroupBox("Log")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(4, 4, 4, 4)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setPlaceholderText("Log output will appear here...")
        self.log_widget.setMaximumHeight(120)
        self.log_widget.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: none;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_widget)
        outer_layout.addWidget(log_group)

        # ---- Wire buttons ----
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_init.clicked.connect(self.on_initialize_clicked)
        self.btn_cam_start.clicked.connect(self.on_cam_start_clicked)
        self.btn_capture.clicked.connect(self.on_capture_clicked)
        self.btn_plate.clicked.connect(self.on_plate_clicked)
        self.btn_we.clicked.connect(self.on_we_clicked)
        self.btn_manual_spot.clicked.connect(self.on_manual_spot_clicked)

    # ================================================================
    # Helpers
    # ================================================================

    def log(self, message: str, level: str = "info") -> None:
        prefix = {"info": "[INFO]", "warn": "[WARN]", "error": "[ERROR]"}.get(level, "[INFO]")
        self.log_widget.append(f"{prefix} {message}")

    def set_status(self, status: str, state: str = "disconnected") -> None:
        colors = {
            "disconnected": "#ff6b6b",
            "connecting":   "#ffd93d",
            "ready":        "#6bcb77",
            "error":        "#ff6b6b",
        }
        color = colors.get(state, "#ff6b6b")
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                padding: 6px 12px;
                background-color: #2a2a2a;
                border-radius: 4px;
                min-width: 140px;
            }}
        """)

    def _show_image(self, img) -> None:
        img_rgb = bgr_to_rgb(img)
        h, w, ch = img_rgb.shape
        qimg = QImage(img_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg).scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(pix)

    def _is_stage_ready(self) -> bool:
        return self.connection_service.is_ready()

    def _pick_image_file(self, title: str) -> str | None:
        path, _ = QFileDialog.getOpenFileName(
            self, title, str(PROJECT_ROOT),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        return path or None

    # ================================================================
    # Workflow button handlers
    # ================================================================

    def on_connect_clicked(self) -> None:
        try:
            self.set_status("CONNECTING...", "connecting")
            self.log("Stage: connecting to all controllers...", "info")
            self.connection_service.connect().result(timeout=30)
            self.set_status("CONNECTED", "connecting")
            self.log("Stage: all controllers connected.", "info")
        except Exception as exc:
            self.set_status("ERROR", "error")
            self.log(f"Stage connect error: {exc}", "error")
            QMessageBox.critical(self, "Connection error", str(exc))

    def on_initialize_clicked(self) -> None:
        try:
            if not self.connection_service.state.connection.name == "CONNECTED":
                QMessageBox.warning(self, "Not Connected",
                    "Please connect to controllers first.")
                return

            self.set_status("INITIALIZING...", "connecting")
            self.log("Stage: referencing all axes...", "info")
            self.connection_service.initialize().result(timeout=120)

            self.set_status("PARKING...", "connecting")
            self.log("Stage: moving to park position...", "info")
            self.motion_service.move_to_position_safe_z(self.park_position).result(timeout=60)

            self.set_status("READY", "ready")
            self.log(f"Stage ready. Parked at {self.park_position}.", "info")
        except Exception as exc:
            self.set_status("ERROR", "error")
            self.log(f"Initialize error: {exc}", "error")
            QMessageBox.critical(self, "Initialize error", str(exc))

    def on_cam_start_clicked(self) -> None:
        if not self.live_running:
            try:
                if not self.camera.is_connected:
                    self.camera.connect()
                self.live_timer.start(100)
                self.live_running = True
                self.btn_cam_start.setText("Camera Stop")
                self.log("Camera live view started.", "info")
            except Exception as exc:
                self.log(f"Live start error: {exc}", "error")
        else:
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("Camera")
            self.log("Camera live view stopped.", "info")

    def on_capture_clicked(self) -> None:
        camera_available = self.camera.is_connected
        if not camera_available:
            try:
                self.camera.connect()
                camera_available = True
            except Exception:
                camera_available = False

        if camera_available:
            self._capture_from_camera()
        else:
            self._capture_from_file()

    def _capture_from_camera(self) -> None:
        try:
            save_dir = PROJECT_ROOT / "artifacts" / "captures"
            save_dir.mkdir(parents=True, exist_ok=True)

            exp        = self.spin_exposure.value()
            gain       = self.spin_gain.value()
            r, g, b    = self.spin_wb_r.value(), self.spin_wb_g.value(), self.spin_wb_b.value()
            base       = f"Photo_{exp:.1f}_{gain:.1f}_{r:.2f}_{g:.2f}_{b:.2f}"
            filename   = save_dir / f"{base}.png"
            counter    = 1
            while filename.exists():
                filename = save_dir / f"{base}_{counter}.png"
                counter += 1

            frame                = self.camera.save_frame(str(filename))
            self.last_image_path = str(filename)
            self._show_image(frame)
            self.log(f"Captured: {filename}", "info")
        except Exception as exc:
            self.log(f"Capture error: {exc}", "error")
            QMessageBox.critical(self, "Capture error", str(exc))

    def _capture_from_file(self) -> None:
        self.log("Camera not connected - select an image file.", "warn")
        path = self._pick_image_file("Select image (no camera connected)")
        if not path:
            self.log("Capture cancelled.", "warn")
            return
        img = load_image(path)
        if img is None:
            self.log(f"Could not load: {path}", "error")
            QMessageBox.critical(self, "Load error", f"Cannot read image:\n{path}")
            return
        self.last_image_path = path
        self._show_image(img)
        self.log(f"Loaded image: {path}", "info")

    def on_plate_clicked(self) -> None:
        image_path = self.last_image_path
        if not image_path:
            image_path = self._pick_image_file("Select image for plate detection")
            if not image_path:
                self.log("Plate detection cancelled.", "warn")
                return
            self.log(f"Using selected image: {image_path}", "info")

        try:
            save_dir = PROJECT_ROOT / "artifacts" / "plate_detection"
            save_dir.mkdir(parents=True, exist_ok=True)

            result = analyze_plate_and_spots(image_path, str(save_dir))

            if result.get("error"):
                msg = f"Detection error: {result['error']}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            if not result["plate_detected"]:
                msg = "No plate detected in image."
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            plate_img        = result["plate_image"]
            plate_path       = str(save_dir / "plate.png")
            save_image(plate_path, plate_img)
            self.last_plate_path = plate_path

            self._show_image(plate_img)
            bbox = result["plate_bbox"]
            self.log(f"Plate detected at {bbox}. Saved: {plate_path}", "info")
            QMessageBox.information(self, "Plate detection",
                f"Plate detected at {bbox}\nSaved to: {plate_path}")
        except Exception as exc:
            self.log(f"Plate detection error: {exc}", "error")
            QMessageBox.critical(self, "Plate detection error", str(exc))

    def on_we_clicked(self) -> None:
        image_path = self.last_plate_path

        if not image_path:
            self.log("No plate image available. Select manually?", "warn")
            reply = QMessageBox.question(
                self, "WE Detection",
                "No plate image available.\n\nSelect an image manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            image_path = self._pick_image_file("Select image for WE detection")
            if not image_path:
                self.log("WE detection cancelled.", "warn")
                return
            self.log(f"WE detection using: {image_path}", "info")
        else:
            self.log(f"WE detection using plate image: {image_path}", "info")

        save_dir = str(PROJECT_ROOT / "artifacts" / "we_detection")

        self.btn_we.setEnabled(False)
        self.btn_we.setText("WE Detect (running...)")

        self._we_worker = SpotAnalysisWorker(image_path, save_dir)
        self._we_worker.finished.connect(self._on_we_finished)
        self._we_worker.error.connect(self._on_we_error)
        self._we_worker.start()

    def _on_we_finished(self, result: dict) -> None:
        self.btn_we.setEnabled(True)
        self.btn_we.setText("WE Detect")

        overlay = result.get("overlay_image")
        if overlay is not None:
            self._show_image(overlay)

        total           = len(result["all_spots"])
        accepted        = len(result["accepted_spots"])
        rejected        = len(result["rejected_spots"])
        rejected_labels = result.get("rejected_labels", [])
        missing_spots   = result.get("missing_spots", [])
        excel_path      = result.get("excel_path")
        err             = result.get("error")

        self.log(f"Detected spots:  {total}", "info")
        self.log(f"Accepted:        {accepted}", "info")
        self.log(f"Rejected:        {rejected}", "warn" if rejected else "info")

        if rejected_labels:
            self.log(f"Rejected labels: {', '.join(rejected_labels)}", "warn")
        if missing_spots:
            self.log(f"Missing spots:   {', '.join(missing_spots)}", "warn")
        if excel_path:
            self.log(f"Excel saved:     {excel_path}", "info")
        if err:
            self.log(f"Warning: {err}", "warn")

        issues: list[str] = []
        if rejected:
            issues.append(f"Rejected: {rejected} spot(s) - {', '.join(rejected_labels)}")
        if missing_spots:
            issues.append(f"Missing: {', '.join(missing_spots)}")

        if not issues:
            QMessageBox.information(self, "WE Detection",
                f"All {accepted} spot(s) accepted. No defects detected.")
        else:
            QMessageBox.warning(self, "WE Detection",
                f"Detected: {total}  Accepted: {accepted}  Rejected: {rejected}\n"
                + "\n".join(issues))

    def _on_we_error(self, error_msg: str) -> None:
        self.btn_we.setEnabled(True)
        self.btn_we.setText("WE Detect")
        self.log(f"WE detection error: {error_msg}", "error")
        QMessageBox.critical(self, "WE Detection Error", error_msg)

    def on_manual_spot_clicked(self) -> None:
        """Open the interactive spot-picker dialog on the current image."""
        image_path = self.last_image_path or self.last_plate_path
        if not image_path:
            image_path = self._pick_image_file("Select image for manual spot marking")
            if not image_path:
                return

        img = load_image(image_path)
        if img is None:
            QMessageBox.critical(self, "Load error", f"Cannot load image:\n{image_path}")
            return

        save_dir = str(PROJECT_ROOT / "artifacts" / "manual_spots")
        dlg      = ManualSpotDialog(img, save_dir, parent=self)

        if dlg.exec() == QDialog.Accepted:
            ref   = dlg.get_reference()
            spots = dlg.get_spots()

            if ref or spots:
                # Persist for alignment use
                self._manual_reference  = ref
                self._manual_spots      = spots
                self._at_spot           = False   # reset motion state
                self._current_spot_idx  = 0       # start from S1 on next Move Next
                self._refresh_spot_combo()
                self._update_next_spot_label()

                if ref:
                    self.log(f"  Reference: X={ref['x']}  Y={ref['y']}", "info")
                self.log(f"Manual spots saved: {len(spots)} spot(s)", "info")
                for s in spots:
                    self.log(f"  {s['label']}: X={s['x']}  Y={s['y']}", "info")
                ep = dlg.excel_path()
                if ep:
                    self.log(f"Excel saved:  {ep}", "info")
                ip = dlg.image_path()
                if ip:
                    self.log(f"Image saved: {ip}", "info")
                    annotated = load_image(ip)
                    if annotated is not None:
                        self._show_image(annotated)
            else:
                self.log("Manual spot detect: no spots marked.", "warn")

    def on_set_alignment_base(self) -> None:
        """Read current stage XY and store as the alignment base position."""
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Connect and initialize the stage first.")
            return
        try:
            pos = self.motion_service.get_current_position()
            self.spin_base_x.setValue(pos.x)
            self.spin_base_y.setValue(pos.y)
            self._align_base_x = pos.x
            self._align_base_y = pos.y
            self.log(f"Alignment base set: X={pos.x:.2f}  Y={pos.y:.2f} mm", "info")
        except Exception as exc:
            self.log(f"Set base error: {exc}", "error")

    # ------------------------------------------------------------------
    # Alignment helpers
    # ------------------------------------------------------------------

    def _refresh_spot_combo(self) -> None:
        """Repopulate the spot combo from the currently loaded manual spots."""
        self.combo_move_spot.clear()
        for spot in self._manual_spots:
            self.combo_move_spot.addItem(spot["label"])

    def _update_next_spot_label(self) -> None:
        """Update the 'Next: Sx' status label below Move Next Spot."""
        if not self._manual_spots:
            self.lbl_next_spot.setText("Next: —")
            return
        if self._current_spot_idx >= len(self._manual_spots):
            self.lbl_next_spot.setText("Next: — (all visited)")
        else:
            nxt = self._manual_spots[self._current_spot_idx]["label"]
            remaining = len(self._manual_spots) - self._current_spot_idx
            self.lbl_next_spot.setText(
                f"Next: {nxt}  ({self._current_spot_idx + 1}/{len(self._manual_spots)})"
            )

    def _build_aligner(self) -> SpotAligner:
        # invert_x/invert_y default to True (camera vs stage axis convention).
        # The Flip checkboxes let the user toggle each axis without touching code.
        return SpotAligner(
            holder_to_sfc_x=self.spin_sfc_offset_x.value(),
            holder_to_sfc_y=self.spin_sfc_offset_y.value(),
            sfc_z=self.spin_sfc_z.value(),
            invert_x=not self.chk_flip_x.isChecked(),
            invert_y=not self.chk_flip_y.isChecked(),
        )

    def _check_alignment_ready(self) -> bool:
        """Return True if spots, reference and base are all set; log + warn otherwise."""
        if not self._manual_reference:
            QMessageBox.warning(self, "No Reference",
                "Use 'Manual Spot Detect' and mark a Reference point first.")
            return False
        if not self._manual_spots:
            QMessageBox.warning(self, "No Spots",
                "Use 'Manual Spot Detect' and mark at least one spot first.")
            return False
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Connect and initialize the stage first.")
            return False
        return True

    def _log_alignment(self, result: AlignmentResult) -> None:
        ppx, ppy = result.pixel_pos
        opx, opy = result.pixel_offset
        rx, ry   = result.real_offset_mm
        mx, my   = result.stage_move_mm
        self.log(
            f"  {result.label}  Pixel pos:    ({ppx}, {ppy})", "info"
        )
        self.log(
            f"  {result.label}  Pixel offset: dx={opx:+d}  dy={opy:+d}", "info"
        )
        self.log(
            f"  {result.label}  Real offset:  dx={rx:+.2f} mm  dy={ry:+.2f} mm", "info"
        )
        self.log(
            f"  {result.label}  Stage move:   X={mx:+.3f} mm  Y={my:+.3f} mm", "info"
        )

    def _set_move_buttons_enabled(self, enabled: bool) -> None:
        self.btn_move_spot.setEnabled(enabled)
        self.btn_move_next.setEnabled(enabled)

    def _run_steps(self, steps: list, label: str) -> None:
        """Kick off a SpotAlignmentWorker for the given step list.

        If Dry Run is checked, log all planned steps without moving the stage.
        """
        if self._align_worker and self._align_worker.isRunning():
            QMessageBox.warning(self, "Busy", "A move is already in progress.")
            return

        if self.chk_dry_run.isChecked():
            self.log(f"[DRY RUN] Steps planned for {label}:", "info")
            for step in steps:
                self.log(f"  [DRY RUN]  {step.description}", "info")
                self.log(
                    f"  [DRY RUN]  → target X={step.target_x:.3f}  "
                    f"Y={step.target_y:.3f}  Z={step.target_z:.3f} mm", "info"
                )
            self.log(f"[DRY RUN] No stage movement performed for {label}.", "warn")
            return

        self._set_move_buttons_enabled(False)
        self._align_worker = SpotAlignmentWorker(self.motion_service, steps)
        self._align_worker.step_done.connect(
            lambda desc: self.log(f"  ✓ {desc}", "info")
        )
        self._align_worker.finished.connect(
            lambda: self._on_align_finished(label)
        )
        self._align_worker.error.connect(self._on_align_error)
        self._align_worker.start()

    def _on_align_finished(self, label: str) -> None:
        self._set_move_buttons_enabled(True)
        self._at_spot = True
        self.log(f"Arrived at {label}.", "info")

    def _on_align_error(self, msg: str) -> None:
        self._set_move_buttons_enabled(True)
        self.log(f"Alignment move error: {msg}", "error")
        QMessageBox.critical(self, "Alignment Error", msg)

    # ------------------------------------------------------------------
    # Move to single spot
    # ------------------------------------------------------------------

    def on_move_to_spot_clicked(self) -> None:
        if not self._check_alignment_ready():
            return

        spot_label = self.combo_move_spot.currentText()
        if not spot_label:
            QMessageBox.warning(self, "No Spot Selected",
                "No spots loaded yet. Run Manual Spot Detect first.")
            return

        base_x = self.spin_base_x.value()
        base_y = self.spin_base_y.value()

        aligner = self._build_aligner()
        try:
            aligner.load_spots(self._manual_reference, self._manual_spots)
            result = aligner.compute_alignment(spot_label)
        except ValueError as exc:
            QMessageBox.warning(self, "Alignment Error", str(exc))
            return

        target_x, target_y = aligner.stage_target(result, base_x, base_y)

        self.log(f"--- Computing alignment for {spot_label} ---", "info")
        self._log_alignment(result)
        self.log(f"  Stage target: X={target_x:.3f}  Y={target_y:.3f} mm", "info")

        try:
            current = self.motion_service.get_current_position()
        except Exception as exc:
            self.log(f"Cannot read stage position: {exc}", "error")
            return

        # Safety limit check
        import math
        move_dist = math.hypot(target_x - current.x, target_y - current.y)
        max_move  = self.spin_max_move.value()
        if move_dist > max_move:
            reply = QMessageBox.warning(
                self, "Safety Limit Exceeded",
                f"Computed XY move distance: {move_dist:.2f} mm\n"
                f"Safety limit: {max_move:.1f} mm\n\n"
                "This may indicate a bad calibration.\n"
                "Proceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.log(f"Move to {spot_label} cancelled (safety limit).", "warn")
                return

        # Confirm dialog — show computed offsets before moving
        mx, my = result.stage_move_mm
        reply = QMessageBox.question(
            self, f"Confirm Move → {spot_label}",
            f"Spot:          {spot_label}\n"
            f"Stage ΔX:      {mx:+.3f} mm\n"
            f"Stage ΔY:      {my:+.3f} mm\n"
            f"Target X:      {target_x:.3f} mm\n"
            f"Target Y:      {target_y:.3f} mm\n"
            f"Move distance: {move_dist:.2f} mm\n\n"
            "Move the stage?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.log(f"Move to {spot_label} cancelled by user.", "warn")
            return

        self.log(f"--- Moving to {spot_label} ---", "info")

        if self._at_spot:
            steps = aligner.between_spot_sequence(
                target_x, target_y,
                current.x, current.y, current.z,
                label=spot_label,
            )
        else:
            steps = aligner.first_spot_sequence(
                target_x, target_y,
                current.x, current.y, current.z,
                label=spot_label,
            )

        self._run_steps(steps, spot_label)

    # ------------------------------------------------------------------
    # Move Next Spot — supervised one-step-at-a-time traversal
    # ------------------------------------------------------------------

    def on_move_next_spot_clicked(self) -> None:
        """Move to the next spot in sequence, one at a time.

        Each press advances _current_spot_idx by one so the user must
        review each step before the stage continues.
        """
        if not self._check_alignment_ready():
            return

        if not self._manual_spots:
            QMessageBox.warning(self, "No Spots", "No spots loaded yet.")
            return

        if self._current_spot_idx >= len(self._manual_spots):
            reply = QMessageBox.question(
                self, "All Spots Visited",
                f"All {len(self._manual_spots)} spot(s) have been visited.\n\n"
                "Reset to start from S1 again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._current_spot_idx = 0
                self._at_spot = False
                self._update_next_spot_label()
            return

        spot       = self._manual_spots[self._current_spot_idx]
        spot_label = spot["label"]
        base_x     = self.spin_base_x.value()
        base_y     = self.spin_base_y.value()

        aligner = self._build_aligner()
        try:
            aligner.load_spots(self._manual_reference, self._manual_spots)
            result = aligner.compute_alignment(spot_label)
        except ValueError as exc:
            QMessageBox.warning(self, "Alignment Error", str(exc))
            return

        target_x, target_y = aligner.stage_target(result, base_x, base_y)

        self.log(
            f"--- Next Spot ({self._current_spot_idx + 1}/{len(self._manual_spots)}): "
            f"{spot_label} ---", "info"
        )
        self._log_alignment(result)
        self.log(f"  Stage target: X={target_x:.3f}  Y={target_y:.3f} mm", "info")

        try:
            current = self.motion_service.get_current_position()
        except Exception as exc:
            self.log(f"Cannot read stage position: {exc}", "error")
            return

        # Safety limit check
        import math
        move_dist = math.hypot(target_x - current.x, target_y - current.y)
        max_move  = self.spin_max_move.value()
        if move_dist > max_move:
            reply = QMessageBox.warning(
                self, "Safety Limit Exceeded",
                f"Computed XY move distance: {move_dist:.2f} mm\n"
                f"Safety limit: {max_move:.1f} mm\n\n"
                "This may indicate a bad calibration.\n"
                "Proceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.log(f"Move Next ({spot_label}) cancelled (safety limit).", "warn")
                return

        # Confirm dialog
        mx, my = result.stage_move_mm
        remaining = len(self._manual_spots) - self._current_spot_idx - 1
        reply = QMessageBox.question(
            self, f"Confirm Move → {spot_label}",
            f"Spot:            {spot_label}  "
            f"({self._current_spot_idx + 1} of {len(self._manual_spots)})\n"
            f"Stage ΔX:        {mx:+.3f} mm\n"
            f"Stage ΔY:        {my:+.3f} mm\n"
            f"Target X:        {target_x:.3f} mm\n"
            f"Target Y:        {target_y:.3f} mm\n"
            f"Move distance:   {move_dist:.2f} mm\n"
            f"Remaining after: {remaining} spot(s)\n\n"
            "Move the stage?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.log(f"Move Next ({spot_label}) cancelled by user.", "warn")
            return

        self.log(f"--- Moving to {spot_label} ---", "info")

        if self._at_spot:
            steps = aligner.between_spot_sequence(
                target_x, target_y,
                current.x, current.y, current.z,
                label=spot_label,
            )
        else:
            steps = aligner.first_spot_sequence(
                target_x, target_y,
                current.x, current.y, current.z,
                label=spot_label,
            )

        self._current_spot_idx += 1
        self._update_next_spot_label()
        self._run_steps(steps, spot_label)

    # ================================================================
    # Camera settings handlers
    # ================================================================

    def on_set_exposure(self) -> None:
        if not self.camera.is_connected:
            self.log("Camera not connected.", "warn")
            return
        try:
            ms = self.spin_exposure.value()
            self.camera.set_exposure(ms / 1000.0)
            self.log(f"Exposure set to {ms:.1f} ms.", "info")
        except Exception as exc:
            self.log(f"Set exposure error: {exc}", "error")

    def on_set_gain(self) -> None:
        if not self.camera.is_connected:
            self.log("Camera not connected.", "warn")
            return
        try:
            gain = self.spin_gain.value()
            self.camera.set_gain(gain)
            self.log(f"Gain set to {gain:.1f} dB.", "info")
        except Exception as exc:
            self.log(f"Set gain error: {exc}", "error")

    def on_wb_preset_changed(self, preset: str) -> None:
        presets = {
            "Default":    (1.0, 1.0, 1.0),
            "Warm":       (1.0, 0.9, 0.7),
            "Cool":       (0.9, 1.0, 1.2),
            "Reduce NIR": (0.6, 0.8, 1.0),
        }
        if preset in presets:
            r, g, b = presets[preset]
            self.spin_wb_r.setValue(r)
            self.spin_wb_g.setValue(g)
            self.spin_wb_b.setValue(b)
            self.on_apply_white_balance()

    def on_apply_white_balance(self) -> None:
        try:
            r, g, b = self.spin_wb_r.value(), self.spin_wb_g.value(), self.spin_wb_b.value()
            self.camera.set_white_balance(r, g, b)
            self.log(f"White balance: R={r:.2f} G={g:.2f} B={b:.2f}", "info")
        except Exception as exc:
            self.log(f"Set white balance error: {exc}", "error")

    # ================================================================
    # Stage control handlers
    # ================================================================

    def on_refresh_position(self) -> None:
        if not self._is_stage_ready():
            self.log("Cannot get position: stage not initialized.", "warn")
            return
        try:
            pos = self.motion_service.get_current_position()
            self.pos_label.setText(f"Position: X={pos.x:.2f}  Y={pos.y:.2f}  Z={pos.z:.2f}")
            self.spin_goto_x.setValue(pos.x)
            self.spin_goto_y.setValue(pos.y)
            self.spin_goto_z.setValue(pos.z)
            self.log(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}", "info")
        except Exception as exc:
            self.log(f"Get position error: {exc}", "error")

    def on_jog_axis(self, axis: Axis, direction: int) -> None:
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            step = self.spin_step.value() * direction
            self.log(f"Jogging {axis.value} by {step:+.1f} mm...", "info")
            self.motion_service.move_axis_relative(axis, step).result(timeout=30)
            self.on_refresh_position()
        except Exception as exc:
            self.log(f"Jog {axis.value} error: {exc}", "error")

    def on_goto_position(self) -> None:
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            target = Position(
                x=self.spin_goto_x.value(),
                y=self.spin_goto_y.value(),
                z=self.spin_goto_z.value(),
            )
            self.log(f"Moving to X={target.x:.2f} Y={target.y:.2f} Z={target.z:.2f}...", "info")
            self.motion_service.move_to_position_safe_z(target).result(timeout=60)
            self.on_refresh_position()
            self.log("Move complete.", "info")
        except Exception as exc:
            self.log(f"Go to position error: {exc}", "error")

    # ================================================================
    # Live view
    # ================================================================

    def _update_live_view(self) -> None:
        try:
            frame = self.camera.grab_frame()
            self._show_image(frame)
        except Exception as exc:
            self.log(f"Live view error: {exc}", "error")
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("Camera")

    # ================================================================
    # Shutdown
    # ================================================================

    def closeEvent(self, event) -> None:
        self.log("Closing - disconnecting hardware...", "info")

        if self.live_running:
            self.live_timer.stop()
            self.live_running = False

        if self._we_worker and self._we_worker.isRunning():
            self._we_worker.quit()
            self._we_worker.wait(3000)

        try:
            if self.camera.is_connected:
                self.camera.disconnect()
        except Exception as exc:
            print(f"Camera disconnect error: {exc}")

        try:
            self.connection_service.shutdown()
        except Exception as exc:
            print(f"Stage disconnect error: {exc}")

        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app    = QApplication(sys.argv)
    window = SimpleStageApp(use_mock=False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
