#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Configuration file for PI Stage Control System
Contains all hardware-specific parameters and settings
"""

# Hardware Configuration - Controller Settings
CONTROLLER_CONFIG = {
    'X': {
        'port': 'COM5',
        'baud': 115200,
        'stage': '62309260',
        'refmode': 'FPL',
        'serialnum': '025550131'
    },
    'Y': {
        'port': 'COM3',
        'baud': 115200,
        'stage': '62309260',
        'refmode': 'FPL',
        'serialnum': '025550143'
    },
    'Z': {
        'port': 'COM4',
        'baud': 115200,
        'stage': '62309260',
        'refmode': 'FPL',
        'serialnum': '025550149'
    },
}

# Referencing Order (Z first for safety)
REFERENCE_ORDER = ['Z', 'X', 'Y']

# Safe Travel Ranges (in mm)
AXIS_TRAVEL_RANGES = {
    'X': {'min': 5.0, 'max': 200.0},
    'Y': {'min': 0.0, 'max': 200.0},
    'Z': {'min': 15.0, 'max': 200.0},
}

# Motion Parameters
DEFAULT_VELOCITY = 10.0  # mm/s
MAX_VELOCITY = 20.0      # mm/s (VT-80 limit)
DEFAULT_PARK_POSITION = 200.0  # mm

# GUI Settings
DEFAULT_STEP_SIZE = 1.0  # mm for manual control
POSITION_UPDATE_INTERVAL = 100  # ms (10 Hz update rate)

# Default Waypoints (for demonstration)
DEFAULT_WAYPOINTS = [
    {'X': 10.0, 'Y': 5.0, 'Z': 20.0, 'holdTime': 1.0},
    {'X': 25.0, 'Y': 15.0, 'Z': 30.0, 'holdTime': 2.0},
]

# Color Scheme for Modern GUI
COLOR_SCHEME = {
    'bg_gradient_start': '#0D1D55',
    'bg_gradient_end': '#38688C',
    'primary': '#63B3C2',
    'primary_hover': '#B1D9D0',
    'secondary': '#38688C',
    'text_primary': '#FFFFDD',
    'text_secondary': '#FFFFEC',
    'accent_green': '#38a169',
    'accent_red': '#e53e3e',
    'accent_cyan': '#00d4aa',
}
