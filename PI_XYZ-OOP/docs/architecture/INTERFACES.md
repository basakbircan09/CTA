# OOP Refactor - Interface Contracts

This document defines the public APIs for each layer. Signatures describe behaviour, failure modes, and the master-branch references that motivate the design.

## 1. Models (`PI_Control_System/core/models.py`)

| Entity | Fields | Notes | Source |
| --- | --- | --- | --- |
| `Axis` (`Enum`) | `X`, `Y`, `Z` | Axis identifiers | `config.py:11-35` |
| `TravelRange` | `min: float`, `max: float`, `clamp(value) -> float` | Encodes `origintools.safe_range` logic | `origintools.py:16-33` |
| `AxisConfig` | `axis: Axis`, `serial: str`, `port: str`, `baud: int`, `stage: str`, `refmode: str`, `range: TravelRange`, `default_velocity: float`, `max_velocity: float` | Consolidates hardware parameters | `config.py:11-56` |
| `AxisState` | `axis: Axis`, `position: float`, `velocity: float`, `is_connected: bool`, `is_initialized: bool` | Mirrors cache in `hardware_controller.py:30-43` |
| `Position` | `x: float`, `y: float`, `z: float`, `__getitem__` | Based on waypoint usage | `main_gui.py:666-687` |
| `Waypoint` | `position: Position`, `hold_time: float` | Waypoint table row | `main_gui.py:666-687` |
| `SequenceConfig` | `waypoints: list[Waypoint]`, `park_when_complete: bool`, `park_position: float` | Sequence execution options | `origintools.py:42-96` |
| `SystemState` | `connection: ConnectionState`, `initialization: InitializationState`, `is_sequence_running: bool` | Supports GUI binding | `main_gui.py:520-573` |
| `ConnectionState` (`Enum`) | `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `INITIALIZING`, `READY`, `ERROR` | Reflects button enable/disable logic | `main_gui.py:520-613` |
| `ErrorDetail` | `origin: Axis | Literal["system"]`, `message: str`, `exc: Exception | None` | Published via error events |

## 2. Exceptions (`PI_Control_System/core/errors.py`)

| Exception | Description | When Raised |
| --- | --- | --- |
| `ConfigurationError` | Invalid or missing configuration data | During config load |
| `ConnectionError` | Hardware connection failure | `AxisController.connect` |
| `InitializationError` | Reference sequence failure | `AxisController.initialize` |
| `MotionError` | Move command failure or range violation | `AxisController.move_*` |

## 3. Hardware Interfaces (`PI_Control_System/core/hardware/interfaces.py`)

```python
class AxisController(ABC):
    axis: Axis
    config: AxisConfig

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def move_absolute(self, position: float) -> None: ...

    @abstractmethod
    def move_relative(self, distance: float) -> None: ...

    @abstractmethod
    def set_velocity(self, velocity: float) -> None: ...

    @abstractmethod
    def get_position(self) -> float: ...

    @abstractmethod
    def is_on_target(self) -> bool: ...

    @abstractmethod
    def wait_for_target(self, timeout: float | None = None) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @property
    @abstractmethod
    def is_initialized(self) -> bool: ...
```

Motivation: `hardware_controller.py` responsibilities (lines 35-247).

```python
class AxisControllerManager(ABC):
    @abstractmethod
    def connect_all(self) -> None: ...

    @abstractmethod
    def disconnect_all(self) -> None: ...

    @abstractmethod
    def initialize_all(self) -> None: ...

    @abstractmethod
    def get_controller(self, axis: Axis) -> AxisController: ...

    @abstractmethod
    def get_position_snapshot(self) -> Position: ...

    @abstractmethod
    def park_all(self, position: float) -> None: ...
```

Motivation: multi-axis flows in `hardware_controller.py:71-235` and `origintools.reset`.

## 4. Services

### 4.1 Event Bus (`PI_Control_System/services/event_bus.py`)

| Member | Signature | Notes |
| --- | --- | --- |
| `EventType` | Enum values: `CONNECTION_STARTED`, `CONNECTION_SUCCEEDED`, `CONNECTION_FAILED`, `INITIALIZATION_STARTED`, `INITIALIZATION_PROGRESS`, `INITIALIZATION_SUCCEEDED`, `INITIALIZATION_FAILED`, `MOTION_STARTED`, `MOTION_PROGRESS`, `MOTION_COMPLETED`, `MOTION_FAILED`, `POSITION_UPDATED`, `STATE_CHANGED`, `ERROR_OCCURRED` | Derived from UI status messaging |
| `Event` | `event_type: EventType`, `data: Any` | Generic payload wrapper |
| `subscribe` | `(event_type, callback) -> SubscriptionToken` | Returns token for safe removal |
| `unsubscribe` | `(token) -> None` | Allows widget teardown |
| `publish` | `(event: Event) -> None` | Executes callbacks synchronously in publisher thread |

### 4.2 ConnectionService (`PI_Control_System/services/connection_service.py`)

| Method | Signature | Side Effects | Failure Handling |
| --- | --- | --- | --- |
| `connect()` | `-> Future[None]` | Publishes `CONNECTION_STARTED`, schedules `AxisController.connect` for each axis | Publishes `CONNECTION_FAILED` with `ErrorDetail` |
| `initialize()` | `-> Future[None]` | Publishes `INITIALIZATION_STARTED`, steps through reference order | Publishes `INITIALIZATION_FAILED`, `ERROR_OCCURRED` |
| `disconnect()` | `-> None` | Calls `disconnect_all`, publishes `STATE_CHANGED` (`DISCONNECTED`) | Logs errors but continues |
| `state` | property returning `SystemState` | Read-only snapshot | n/a |

### 4.3 MotionService (`PI_Control_System/services/motion_service.py`)

| Method | Signature | Notes |
| --- | --- | --- |
| `move_axis_absolute(axis, position)` | `-> Future[None]` | Clamps via `TravelRange`, publishes `MOTION_PROGRESS` |
| `move_axis_relative(axis, distance)` | `-> Future[None]` | Delegates to `move_axis_absolute` |
| `execute_sequence(config)` | `-> Future[None]` | Runs in worker thread, honours `hold_time`, cancellation token |
| `cancel_motion()` | `-> None` | Sets cancellation flag, calls `stop()` on all controllers |
| `park_all(position)` | `-> Future[None]` | Delegates to controller manager |
| `get_position()` | `-> Position` | Returns snapshot from controller manager |

### 4.4 PositionService (`PI_Control_System/services/position_service.py`)

| Method | Signature | Notes |
| --- | --- | --- |
| `start(interval_ms)` | `-> None` | Launches polling loop on executor, publishes `POSITION_UPDATED` |
| `stop()` | `-> None` | Cancels poller |

All service methods rely on a shared `ThreadPoolExecutor(max_workers=4)` (see spike instructions in `IMPLEMENTATION_PLAN.md`).

## 5. GUI Contracts (`PI_Control_System/gui`)

| Component | Responsibility | Inputs | Outputs |
| --- | --- | --- | --- |
| `ConnectionPanel` | Render connect/initialise/disconnect controls | Service events | Qt signals `connect_requested`, `initialize_requested`, `disconnect_requested` |
| `PositionDisplayWidget` | Display live positions and connectivity | Subscribes to `POSITION_UPDATED`, `STATE_CHANGED` | None |
| `VelocityPanel` | Provide per-axis velocity controls | Qt signals to services | Emits `velocity_changed(axis, value)` |
| `ManualJogWidget` | Relative jog buttons | Uses axis configs | Emits `jog_requested(axis, distance)` |
| `SequenceTableWidget` | Waypoint editing and playback | Accepts `SequenceConfig` | Emits `sequence_requested(config)` |
| `SystemLogWidget` | Render chronological log | Subscribes to EventBus | None |
| `MainWindowController` | Glue between widgets and services | Service instances, EventBus | Connects Qt signals to service calls, marshals callbacks via `QMetaObject.invokeMethod` |

## 6. Configuration Loader (`PI_Control_System/config/loader.py`)

| Function | Signature | Behaviour |
| --- | --- | --- |
| `load_config(base_path: Path | None = None) -> ConfigBundle` | Loads `defaults.json`, merges optional `local.overrides.json`, applies file path from `PI_STAGE_CONFIG_PATH` if set | Raises `ConfigurationError` on invalid schema |
| `write_local_override(data: dict) -> None` | Persists machine-specific values | Used by provisioning CLI |
| `resolve_axis_config(axis: Axis) -> AxisConfig` | Convenience accessor | |

Merge order: defaults -> local overrides -> external override file -> runtime overrides.

## 7. State Machines

### 7.1 Connection
```
DISCONNECTED
  connect() -> CONNECTING --success--> CONNECTED --initialize()--> INITIALIZING
                                     --failure--> ERROR
INITIALIZING --success--> READY
INITIALIZING --failure--> ERROR (still connected)
ERROR --disconnect()--> DISCONNECTED
```

### 7.2 Motion Sequence
```
IDLE --execute_sequence()--> RUNNING --cancel--> CANCELLING --> IDLE
RUNNING --success--> COMPLETED --> (optional park) --> IDLE
RUNNING --failure--> ERROR --> IDLE (after stop_all)
```

Transitions emit `STATE_CHANGED` or `MOTION_*` events for GUI synchronisation.

## 8. Testing Hooks
- `MockAxisController` implements `AxisController` for deterministic unit tests.
- `EventBus` returns subscription tokens to simplify teardown in tests.
- Services accept optional executor and polling interval for fast-running tests.

Consult `IMPLEMENTATION_PLAN.md` for the test cases required in each phase.
