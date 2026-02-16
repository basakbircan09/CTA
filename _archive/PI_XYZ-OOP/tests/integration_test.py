#!/usr/bin/env python
"""
Integration test for full workflow with mock hardware.

Verifies end-to-end workflow:
1. Connect to hardware
2. Initialize (reference) axes
3. Manual jog movements
4. Sequence execution (optional)
5. Park all axes
6. Disconnect

This can be run with mock hardware (default) or real hardware (--real flag).

Usage:
    python tests/integration_test.py              # Use mock hardware
    python tests/integration_test.py --real       # Use real hardware (requires PI equipment)
"""

import sys
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PI_Control_System.config.loader import load_config
from PI_Control_System.core.models import Axis, ConnectionState, Waypoint
from PI_Control_System.services.event_bus import EventBus, EventType
from PI_Control_System.hardware.pi_manager import PIControllerManager
from PI_Control_System.services.connection_service import ConnectionService
from PI_Control_System.services.motion_service import MotionService


class IntegrationTest:
    """Integration test runner."""

    def __init__(self, use_mock: bool = True):
        """Initialize test.

        Args:
            use_mock: If True, use mock hardware
        """
        self.use_mock = use_mock
        self.config = load_config()
        self.event_bus = EventBus()
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Create hardware manager
        if use_mock:
            print("Using MOCK hardware controllers")
            from PI_Control_System.hardware.mock_controller import MockAxisController
            controllers = {
                Axis.X: MockAxisController(self.config.axis_configs[Axis.X]),
                Axis.Y: MockAxisController(self.config.axis_configs[Axis.Y]),
                Axis.Z: MockAxisController(self.config.axis_configs[Axis.Z]),
            }
        else:
            print("Using REAL hardware controllers")
            from PI_Control_System.hardware.pi_controller import PIAxisController
            controllers = {
                Axis.X: PIAxisController(self.config.axis_configs[Axis.X]),
                Axis.Y: PIAxisController(self.config.axis_configs[Axis.Y]),
                Axis.Z: PIAxisController(self.config.axis_configs[Axis.Z]),
            }

        self.manager = PIControllerManager(controllers=controllers)

        # Create services
        self.connection_service = ConnectionService(
            manager=self.manager,
            event_bus=self.event_bus,
            executor=self.executor
        )

        self.motion_service = MotionService(
            controller_manager=self.manager,
            event_bus=self.event_bus,
            executor=self.executor,
            connection_service=self.connection_service
        )

        # Subscribe to events for logging
        self.event_bus.subscribe(EventType.CONNECTION_STARTED, self._log_event)
        self.event_bus.subscribe(EventType.CONNECTION_SUCCEEDED, self._log_event)
        self.event_bus.subscribe(EventType.CONNECTION_FAILED, self._log_event)
        self.event_bus.subscribe(EventType.INITIALIZATION_STARTED, self._log_event)
        self.event_bus.subscribe(EventType.INITIALIZATION_PROGRESS, self._log_event)
        self.event_bus.subscribe(EventType.INITIALIZATION_SUCCEEDED, self._log_event)
        self.event_bus.subscribe(EventType.INITIALIZATION_FAILED, self._log_event)
        self.event_bus.subscribe(EventType.MOTION_STARTED, self._log_event)
        self.event_bus.subscribe(EventType.MOTION_COMPLETED, self._log_event)
        self.event_bus.subscribe(EventType.MOTION_FAILED, self._log_event)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._log_event)

    def _log_event(self, event):
        """Log event to console."""
        print(f"  [EVENT] {event.event_type.value}: {event.data}")

    def run(self):
        """Run full integration test workflow."""
        print("\n" + "=" * 60)
        print("INTEGRATION TEST - Full Workflow")
        print("=" * 60)

        try:
            # Step 1: Connect
            print("\n[STEP 1] Connecting to hardware...")
            self.connection_service.connect().result(timeout=10)
            assert self.connection_service.state.connection == ConnectionState.CONNECTED
            print("[OK] Connected successfully")

            # Step 2: Initialize
            print("\n[STEP 2] Initializing axes (referencing)...")
            self.connection_service.initialize().result(timeout=30)
            assert self.connection_service.state.connection == ConnectionState.READY
            print("[OK] Initialization complete")

            # Step 3: Get current positions
            print("\n[STEP 3] Reading current positions...")
            position = self.manager.get_position_snapshot()
            print(f"  X: {position.x:.3f} mm")
            print(f"  Y: {position.y:.3f} mm")
            print(f"  Z: {position.z:.3f} mm")
            print("[OK] Position read successful")

            # Step 4: Manual jog movements
            print("\n[STEP 4] Testing manual jog movements...")
            print("  Jogging X +5mm...")
            self.motion_service.move_axis_relative(Axis.X, 5.0).result(timeout=10)
            print("  Jogging Y -3mm...")
            self.motion_service.move_axis_relative(Axis.Y, -3.0).result(timeout=10)
            print("  Jogging Z +2mm...")
            self.motion_service.move_axis_relative(Axis.Z, 2.0).result(timeout=10)

            new_position = self.manager.get_position_snapshot()
            print(f"  New position: X={new_position.x:.3f}, Y={new_position.y:.3f}, Z={new_position.z:.3f}")
            print("[OK] Jog movements completed")

            # Step 5: Sequence execution (optional - using default waypoints)
            if self.config.default_waypoints:
                print("\n[STEP 5] Testing waypoint sequence...")
                print(f"  Executing {len(self.config.default_waypoints)} waypoints...")
                # Note: execute_sequence not yet implemented in MotionService
                # This is a placeholder for when sequence execution is added
                print("  (Sequence execution skipped - not yet implemented)")
            else:
                print("\n[STEP 5] Skipping sequence test (no default waypoints)")

            # Step 6: Park all axes
            print("\n[STEP 6] Parking all axes...")
            self.motion_service.park_all(self.config.park_position).result(timeout=30)
            park_position = self.manager.get_position_snapshot()
            print(f"  Parked at: X={park_position.x:.3f}, Y={park_position.y:.3f}, Z={park_position.z:.3f}")
            print("[OK] Park completed")

            # Step 7: Disconnect
            print("\n[STEP 7] Disconnecting from hardware...")
            self.connection_service.disconnect()
            time.sleep(0.5)  # Allow disconnect to complete
            assert self.connection_service.state.connection == ConnectionState.DISCONNECTED
            print("[OK] Disconnected successfully")

            print("\n" + "=" * 60)
            print("[PASS] ALL TESTS PASSED")
            print("=" * 60)
            return True

        except Exception as e:
            print(f"\n[FAIL] TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Cleanup
            try:
                if self.connection_service.state.connection != ConnectionState.DISCONNECTED:
                    self.connection_service.disconnect()
            except:
                pass
            self.executor.shutdown(wait=True)


def main():
    """Run integration test."""
    parser = argparse.ArgumentParser(description="Integration test for PI Control System")
    parser.add_argument(
        '--real',
        action='store_true',
        help='Use real hardware (requires PI equipment and drivers)'
    )
    args = parser.parse_args()

    test = IntegrationTest(use_mock=not args.real)
    success = test.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
