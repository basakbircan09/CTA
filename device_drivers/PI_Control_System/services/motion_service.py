"""
Motion service orchestrates motion commands across axes.

Responsibilities:
- Absolute and relative single-axis moves
- Coordinated multi-axis moves (Position targets)
- Waypoint sequence execution
- Park sequence delegation
- Position polling helpers
- Cancellation and stop handling

Sources:
- legacy/PI_Control_GUI/main_gui.py:381-722 (manual/automated logic)
- legacy/PI_Control_GUI/hardware_controller.py:152-328 (motions + park)
- docs/architecture/INTERFACES.md §4.3
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional

from ..core.errors import InitializationError, MotionError
from ..core.hardware.interfaces import AxisControllerManager
from ..core.models import Axis, Position, SequenceConfig, Waypoint
from .event_bus import Event, EventBus, EventType
from .connection_service import ConnectionService


class MotionService:
    """
    Provides high-level motion APIs backed by AxisControllerManager.

    All blocking operations run in the background executor.
    Emits events to notify GUI of progress and errors.
    """

    def __init__(
        self,
        controller_manager: AxisControllerManager,
        event_bus: EventBus,
        executor: ThreadPoolExecutor,
        connection_service: ConnectionService,
    ) -> None:
        self._controllers = controller_manager
        self._events = event_bus
        self._executor = executor
        self._connection_service = connection_service

        # Cancellation flag for sequence execution
        self._cancel_event = threading.Event()
        self._sequence_lock = threading.Lock()
        self._sequence_running = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def move_to_position_safe_z(self, target: Position) -> Future[None]:
        """
        Move to target position with Z ordered for safety:

        - If current Z < target Z: move Z first, then X/Y together.
        - If current Z > target Z: move X/Y together, then Z last.
        - If equal: same as regular move_to_position.
        """
        def work():
            current = self._controllers.get_position_snapshot()
            current_z = current[Axis.Z]
            target_z = target[Axis.Z]

            if current_z < target_z:
                # Going up: Z first, then X/Y
                self._move_axis_absolute_sync(Axis.Z, target_z)
                self._move_axes_xy_sync(target)
            elif current_z > target_z:
                # Going down: X/Y first, then Z
                self._move_axes_xy_sync(target)
                self._move_axis_absolute_sync(Axis.Z, target_z)
            else:
                # Same Z: just move all axes together
                self._move_to_position_sync(target, wait=True)

        return self._submit_motion(
            EventType.MOTION_STARTED,
            work,
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_COMPLETED, f"Reached (safe Z) {target}")
            ),
            description=f"Move (safe Z) to {target}",
        )

    def move_axis_absolute(self, axis: Axis, position: float) -> Future[None]:
        """
        Move a single axis to an absolute position.

        Args:
            axis: Axis to move
            position: Target position in mm (unclamped)
        """
        return self._submit_motion(
            EventType.MOTION_STARTED,
            lambda: self._move_axis_absolute_sync(axis, position),
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_PROGRESS, f"{axis.value} → {position:.3f}")
            ),
            description=f"Move axis {axis.value} absolute",
        )

    def move_axis_relative(self, axis: Axis, distance: float) -> Future[None]:
        """
        Move a single axis by a relative distance.
        """
        return self._submit_motion(
            EventType.MOTION_STARTED,
            lambda: self._move_axis_relative_sync(axis, distance),
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_PROGRESS, f"{axis.value} += {distance:.3f}")
            ),
            description=f"Move axis {axis.value} relative",
        )

    def move_to_position(self, position: Position, wait: bool = True) -> Future[None]:
        """
        Move all axes to the target position simultaneously.
        """
        return self._submit_motion(
            EventType.MOTION_STARTED,
            lambda: self._move_to_position_sync(position, wait),
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_COMPLETED, f"Reached {position}")
            ),
            description=f"Move to position {position}",
        )

    def execute_sequence(self, config: SequenceConfig) -> Future[None]:
        """
        Execute a waypoint sequence.
        """
        return self._submit_motion(
            EventType.MOTION_STARTED,
            lambda: self._execute_sequence_sync(config),
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_COMPLETED, "Sequence complete")
            ),
            description="Execute waypoint sequence",
        )

    def cancel_motion(self) -> None:
        """
        Cancel current motion/sequence if running.
        """
        self._cancel_event.set()
        try:
            self._controllers.get_controller(Axis.X).stop()
        except Exception:
            pass
        try:
            self._controllers.get_controller(Axis.Y).stop()
        except Exception:
            pass
        try:
            self._controllers.get_controller(Axis.Z).stop()
        except Exception:
            pass
        self._events.publish(Event(EventType.MOTION_FAILED, "Motion cancelled"))

    def park_all(self, park_position: float) -> Future[None]:
        """
        Delegate to controller manager to park all axes.
        """
        return self._submit_motion(
            EventType.MOTION_STARTED,
            lambda: self._controllers.park_all(park_position),
            on_success=lambda: self._events.publish(
                Event(EventType.MOTION_COMPLETED, f"Parked at {park_position}")
            ),
            description=f"Park all at {park_position}",
        )

    def get_current_position(self) -> Position:
        """
        Get snapshot of current positions.
        """
        return self._controllers.get_position_snapshot()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _move_axis_absolute_sync(self, axis: Axis, position: float) -> None:
        controller = self._controllers.get_controller(axis)
        controller.move_absolute(position)
        controller.wait_for_target()

    def _move_axis_relative_sync(self, axis: Axis, distance: float) -> None:
        controller = self._controllers.get_controller(axis)
        controller.move_relative(distance)
        controller.wait_for_target()

    def _move_axes_xy_sync(self, target: Position) -> None:
        """Move X and Y to their targets simultaneously and wait."""
        for axis in [Axis.X, Axis.Y]:
            controller = self._controllers.get_controller(axis)
            controller.move_absolute(target[axis])

        for axis in [Axis.X, Axis.Y]:
            controller = self._controllers.get_controller(axis)
            controller.wait_for_target()

    def _move_to_position_sync(self, position: Position, wait: bool) -> None:
        # Command all axes first
        for axis in [Axis.X, Axis.Y, Axis.Z]:
            controller = self._controllers.get_controller(axis)
            controller.move_absolute(position[axis])

        if wait:
            for axis in [Axis.X, Axis.Y, Axis.Z]:
                controller = self._controllers.get_controller(axis)
                controller.wait_for_target()

    def _execute_sequence_sync(self, config: SequenceConfig) -> None:
        with self._sequence_lock:
            if self._sequence_running:
                raise MotionError("Sequence already running")
            self._sequence_running = True
            self._cancel_event.clear()

        try:
            self._events.publish(
                Event(EventType.STATE_CHANGED, "Sequence Started")
            )
            for index, waypoint in enumerate(config.waypoints):
                if self._cancel_event.is_set():
                    raise MotionError("Sequence cancelled")

                self._events.publish(
                    Event(EventType.MOTION_PROGRESS, f"Waypoint {index + 1}")
                )
                self._move_to_position_sync(waypoint.position, wait=True)

                if self._cancel_event.is_set():
                    raise MotionError("Sequence cancelled")

                if waypoint.hold_time > 0:
                    self._sleep_with_cancel(waypoint.hold_time)

            if config.park_when_complete:
                self._controllers.park_all(config.park_position)

        finally:
            with self._sequence_lock:
                self._sequence_running = False
                self._cancel_event.clear()

    def _sleep_with_cancel(self, duration: float) -> None:
        """
        Sleep in small increments, checking cancellation flag.
        """
        end_time = time.time() + duration
        while time.time() < end_time:
            if self._cancel_event.is_set():
                raise MotionError("Sequence cancelled")
            time.sleep(0.05)

    def _submit_motion(
        self,
        start_event: EventType,
        work: Callable[[], None],
        on_success: Optional[Callable[[], None]] = None,
        description: str = "",
    ) -> Future[None]:
        """
        Helper to submit motion work to executor with consistent event handling.
        """
        def job() -> None:
            self._events.publish(Event(start_event, description))
            try:
                work()
                if on_success:
                    on_success()
            except (MotionError, InitializationError) as exc:
                self._events.publish(
                    Event(EventType.ERROR_OCCURRED, str(exc))
                )
                raise
            except Exception as exc:
                self._events.publish(
                    Event(EventType.ERROR_OCCURRED, f"Unexpected motion error: {exc}")
                )
                raise MotionError(str(exc)) from exc

        return self._executor.submit(job)
