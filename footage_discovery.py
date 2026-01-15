#!/usr/bin/env python3
"""
Footage discovery module for UniFi Protect cameras.

This module provides functionality to discover the available date range of footage
by iterating backward from today until no footage is found for any camera.
"""

import logging
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional, Tuple
import pytz

import downloader_adapter


def get_timezone(timezone_str: Optional[str] = None) -> pytz.tzinfo.BaseTzInfo:
    """
    Get a timezone object, defaulting to US/Pacific if not specified.
    
    Args:
        timezone_str: Optional timezone string (e.g., 'US/Pacific', 'America/New_York').
                     If None or invalid, defaults to US/Pacific.
    
    Returns:
        pytz timezone object
    """
    default_tz = 'US/Pacific'
    
    if timezone_str is None:
        logging.info(f"No timezone specified, using default: {default_tz}")
        return pytz.timezone(default_tz)
    
    try:
        tz = pytz.timezone(timezone_str)
        logging.info(f"Using timezone: {timezone_str}")
        return tz
    except pytz.exceptions.UnknownTimeZoneError:
        logging.warning(f"Unknown timezone '{timezone_str}', using default: {default_tz}")
        return pytz.timezone(default_tz)


def check_footage_exists(
    camera_id: str,
    camera_name: str,
    check_date: datetime,
    address: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
) -> bool:
    """
    Check if any footage exists for a camera on a given date.
    
    This function attempts to verify footage availability by checking the camera's
    recording_start time against the requested date.
    
    Args:
        camera_id: ID of the camera to check
        camera_name: Name of the camera (for logging)
        check_date: Date to check (timezone-aware datetime at start of day)
        address: UniFi Protect address
        username: UniFi Protect username
        password: UniFi Protect password
        verify_ssl: Whether to verify SSL certificates
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system
        
    Returns:
        True if footage exists for this date, False otherwise
    """
    # Get camera list to access recording_start information
    try:
        cameras = downloader_adapter.list_cameras(
            address=address,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            not_unifi_os=not_unifi_os,
        )
        
        # Find the specific camera
        camera = None
        for cam in cameras:
            if cam['id'] == camera_id:
                camera = cam
                break
        
        if camera is None:
            logging.warning(f"Camera {camera_name} ({camera_id}) not found")
            return False
        
        recording_start = camera['recording_start']
        
        # If recording_start is datetime.min, camera has no recordings
        if recording_start == datetime.min:
            logging.debug(f"Camera {camera_name} has no recording history")
            return False
        
        # Check if the recording started before or during the check date
        # check_date is at the start of the day, so we check if recording_start
        # is before the end of that day
        check_date_end = check_date + timedelta(days=1)
        
        # Convert recording_start to the same timezone as check_date for comparison
        if recording_start.tzinfo is None:
            # recording_start is naive UTC, make it aware
            recording_start = pytz.utc.localize(recording_start)
        
        # Convert to check_date's timezone for comparison
        recording_start_local = recording_start.astimezone(check_date.tzinfo)
        
        has_footage = recording_start_local < check_date_end
        
        if has_footage:
            logging.debug(
                f"Camera {camera_name} has footage on {check_date.date()} "
                f"(recording started: {recording_start_local.date()})"
            )
        else:
            logging.debug(
                f"Camera {camera_name} has NO footage on {check_date.date()} "
                f"(recording started: {recording_start_local.date()})"
            )
        
        return has_footage
        
    except Exception as e:
        logging.error(f"Error checking footage for camera {camera_name}: {e}")
        return False


def discover_footage_range(
    address: str,
    username: str,
    password: str,
    timezone_str: Optional[str] = None,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
    max_days_back: int = 365,
) -> Dict[str, Any]:
    """
    Discover the available footage date range across all cameras.
    
    Starts from today and iterates backward day by day until no footage is found
    for any camera. This accounts for cameras having different recording start dates.
    
    Args:
        address: UniFi Protect address
        username: UniFi Protect username
        password: UniFi Protect password
        timezone_str: Timezone string (e.g., 'US/Pacific'). Defaults to US/Pacific.
        verify_ssl: Whether to verify SSL certificates
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system
        max_days_back: Maximum number of days to check backward (safety limit)
        
    Returns:
        Dictionary containing:
        - cameras: List of camera info dictionaries
        - earliest_date: The earliest date with footage (timezone-aware)
        - latest_date: The latest date checked (today, timezone-aware)
        - days_with_footage: Number of days with footage found
        - timezone: Timezone string used
        - per_camera_ranges: Dictionary mapping camera_id to (start_date, end_date)
    """
    logging.info("Starting footage discovery...")
    
    # Get timezone
    tz = get_timezone(timezone_str)
    logging.info(f"Using timezone: {tz.zone}")
    
    # Get camera list
    logging.info("Retrieving camera list...")
    cameras = downloader_adapter.list_cameras(
        address=address,
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        not_unifi_os=not_unifi_os,
    )
    
    if not cameras:
        logging.warning("No cameras found")
        return {
            'cameras': [],
            'earliest_date': None,
            'latest_date': None,
            'days_with_footage': 0,
            'timezone': tz.zone,
            'per_camera_ranges': {},
        }
    
    logging.info(f"Found {len(cameras)} camera(s):")
    for camera in cameras:
        logging.info(f"  - {camera['name']} (ID: {camera['id']})")
    
    # Start from today at midnight in the specified timezone
    now = datetime.now(tz)
    current_date = tz.localize(datetime.combine(now.date(), time.min))
    latest_date = current_date
    
    logging.info(f"Starting from: {current_date.date()}")
    
    # Track per-camera earliest date
    per_camera_ranges = {}
    for camera in cameras:
        per_camera_ranges[camera['id']] = {
            'camera_name': camera['name'],
            'earliest_date': None,
            'latest_date': None,
        }
    
    # Iterate backward until no camera has footage
    days_checked = 0
    earliest_date = None
    
    while days_checked < max_days_back:
        # Check if any camera has footage on this date
        any_footage_found = False
        
        for camera in cameras:
            has_footage = check_footage_exists(
                camera_id=camera['id'],
                camera_name=camera['name'],
                check_date=current_date,
                address=address,
                username=username,
                password=password,
                verify_ssl=verify_ssl,
                not_unifi_os=not_unifi_os,
            )
            
            if has_footage:
                any_footage_found = True
                
                # Update per-camera range
                if per_camera_ranges[camera['id']]['latest_date'] is None:
                    per_camera_ranges[camera['id']]['latest_date'] = current_date
                per_camera_ranges[camera['id']]['earliest_date'] = current_date
        
        if any_footage_found:
            earliest_date = current_date
            logging.info(f"Footage found on {current_date.date()}")
        else:
            # No footage found on this date for any camera
            logging.info(f"No footage found on {current_date.date()} - stopping")
            break
        
        # Move to previous day
        current_date = current_date - timedelta(days=1)
        days_checked += 1
    
    if days_checked >= max_days_back:
        logging.warning(f"Reached maximum days limit ({max_days_back})")
    
    # Calculate days with footage
    days_with_footage = 0
    if earliest_date:
        days_with_footage = (latest_date - earliest_date).days + 1
    
    logging.info(f"Footage discovery complete:")
    logging.info(f"  - Earliest date: {earliest_date.date() if earliest_date else 'None'}")
    logging.info(f"  - Latest date: {latest_date.date()}")
    logging.info(f"  - Days with footage: {days_with_footage}")
    
    # Log per-camera ranges
    logging.info("Per-camera footage ranges:")
    for camera_id, range_info in per_camera_ranges.items():
        if range_info['earliest_date']:
            logging.info(
                f"  - {range_info['camera_name']}: "
                f"{range_info['earliest_date'].date()} to {range_info['latest_date'].date()}"
            )
        else:
            logging.info(f"  - {range_info['camera_name']}: No footage found")
    
    return {
        'cameras': cameras,
        'earliest_date': earliest_date,
        'latest_date': latest_date,
        'days_with_footage': days_with_footage,
        'timezone': tz.zone,
        'per_camera_ranges': per_camera_ranges,
    }
