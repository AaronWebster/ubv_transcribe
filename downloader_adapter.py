#!/usr/bin/env python3
"""
Adapter layer for the unifi-protect-video-downloader submodule.

This module provides a simple interface for the rest of the application to:
- List available cameras from UniFi Protect
- Download video chunks for specific time ranges

The adapter wraps the protect_archiver client from the submodule and
provides a cleaner API for our use case.
"""

import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _validate_submodule() -> Path:
    """
    Validate that the unifi-protect-video-downloader submodule is initialized.
    
    Returns:
        Path: Path to the submodule directory
        
    Raises:
        SystemExit: If the submodule is not initialized with instructions
    """
    script_dir = Path(__file__).parent.absolute()
    submodule_path = script_dir / 'unifi-protect-video-downloader'
    
    if not submodule_path.exists():
        logging.error("Submodule 'unifi-protect-video-downloader' directory does not exist.")
        logging.error("Please initialize the submodule with:")
        logging.error("  git submodule update --init --recursive")
        sys.exit(1)
    
    if not submodule_path.is_dir():
        logging.error("Submodule 'unifi-protect-video-downloader' path is not a directory.")
        logging.error("Please initialize the submodule with:")
        logging.error("  git submodule update --init --recursive")
        sys.exit(1)
    
    # Check if submodule is empty (not initialized)
    try:
        if not any(submodule_path.iterdir()):
            logging.error("Submodule 'unifi-protect-video-downloader' is not initialized.")
            logging.error("Please initialize the submodule with:")
            logging.error("  git submodule update --init --recursive")
            sys.exit(1)
    except (PermissionError, OSError) as e:
        logging.error(f"Unable to access submodule directory: {e}")
        logging.error("Please initialize the submodule with:")
        logging.error("  git submodule update --init --recursive")
        sys.exit(1)
    
    logging.debug(f"Submodule validated at: {submodule_path}")
    return submodule_path


def _ensure_submodule_in_path() -> Path:
    """
    Validate submodule and ensure it's in sys.path for imports.
    
    Returns:
        Path: Path to the submodule directory
        
    Raises:
        SystemExit: If the submodule is not initialized
    """
    submodule_path = _validate_submodule()
    
    # Add submodule to Python path if not already there
    if str(submodule_path) not in sys.path:
        sys.path.insert(0, str(submodule_path))
    
    return submodule_path


def _get_protect_client(
    address: str,
    username: str,
    password: str,
    destination_path: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
) -> Any:
    """
    Create and return a ProtectClient instance.
    
    Args:
        address: UniFi Protect address (e.g., "https://192.168.1.1")
        username: UniFi Protect username
        password: UniFi Protect password
        destination_path: Path where downloaded videos will be saved
        verify_ssl: Whether to verify SSL certificates (default: False)
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system (default: False)
        
    Returns:
        ProtectClient instance
        
    Raises:
        ImportError: If the submodule is not properly initialized
    """
    # Validate submodule and ensure it's in sys.path
    _ensure_submodule_in_path()
    
    try:
        from protect_archiver.client import ProtectClient
    except ImportError as e:
        logging.error(f"Failed to import ProtectClient from submodule: {e}")
        logging.error("Please ensure the submodule is properly initialized with:")
        logging.error("  git submodule update --init --recursive")
        sys.exit(1)
    
    # Create and return the client
    client = ProtectClient(
        address=address,
        username=username,
        password=password,
        destination_path=destination_path,
        verify_ssl=verify_ssl,
        not_unifi_os=not_unifi_os,
    )
    
    return client


def list_cameras(
    address: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
) -> List[Dict[str, Any]]:
    """
    List all cameras available in UniFi Protect.
    
    Args:
        address: UniFi Protect address (e.g., "https://192.168.1.1")
        username: UniFi Protect username
        password: UniFi Protect password
        verify_ssl: Whether to verify SSL certificates (default: False)
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system (default: False)
        
    Returns:
        List of dictionaries containing camera information with keys:
        - id: Camera ID
        - name: Camera name
        - recording_start: Datetime when recording started (or datetime.min if not recording)
        
    Example:
        >>> cameras = list_cameras("https://192.168.1.1", "admin", "password")
        >>> for camera in cameras:
        ...     print(f"{camera['name']} (ID: {camera['id']})")
    """
    # Create a temporary destination path (not used for listing cameras)
    temp_path = tempfile.gettempdir()
    
    client = _get_protect_client(
        address=address,
        username=username,
        password=password,
        destination_path=temp_path,
        verify_ssl=verify_ssl,
        not_unifi_os=not_unifi_os,
    )
    
    # Get camera list from the client
    camera_list = client.get_camera_list()
    
    # Convert Camera dataclass instances to dictionaries
    cameras = []
    for camera in camera_list:
        cameras.append({
            'id': camera.id,
            'name': camera.name,
            'recording_start': camera.recording_start,
        })
    
    logging.info(f"Found {len(cameras)} camera(s)")
    return cameras


def download_chunk(
    camera_id: str,
    start_dt: datetime,
    end_dt: datetime,
    out_path: str,
    address: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
    skip_existing_files: bool = True,
) -> str:
    """
    Download a video chunk for a specific camera and time range.
    
    Args:
        camera_id: ID of the camera to download from
        start_dt: Start datetime for the video chunk
        end_dt: End datetime for the video chunk
        out_path: Directory path where the video file will be saved
        address: UniFi Protect address (e.g., "https://192.168.1.1")
        username: UniFi Protect username
        password: UniFi Protect password
        verify_ssl: Whether to verify SSL certificates (default: False)
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system (default: False)
        skip_existing_files: Whether to skip downloading if file already exists (default: True)
        
    Returns:
        Path to the downloaded video file
        
    Example:
        >>> from datetime import datetime, timedelta
        >>> now = datetime.now()
        >>> start = now - timedelta(hours=1)
        >>> path = download_chunk(
        ...     camera_id="abc123",
        ...     start_dt=start,
        ...     end_dt=now,
        ...     out_path="/tmp/videos",
        ...     address="https://192.168.1.1",
        ...     username="admin",
        ...     password="password"
        ... )
        >>> print(f"Video downloaded to: {path}")
    """
    # Validate output path
    out_dir = Path(out_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    client = _get_protect_client(
        address=address,
        username=username,
        password=password,
        destination_path=str(out_dir),
        verify_ssl=verify_ssl,
        not_unifi_os=not_unifi_os,
    )
    
    # Configure skip_existing_files option
    client.skip_existing_files = skip_existing_files
    
    # Get the camera object
    camera_list = client.get_camera_list()
    camera = None
    for cam in camera_list:
        if cam.id == camera_id:
            camera = cam
            break
    
    if camera is None:
        raise ValueError(f"Camera with ID '{camera_id}' not found")
    
    logging.info(f"Downloading video from camera '{camera.name}' ({camera_id})")
    logging.info(f"Time range: {start_dt} to {end_dt}")
    
    # Ensure submodule is in path and import required modules
    _ensure_submodule_in_path()
    
    from protect_archiver.downloader import Downloader
    from protect_archiver.utils import make_camera_name_fs_safe
    
    # Download the footage
    # The downloader handles file creation and naming internally
    Downloader.download_footage(
        client=client,
        start=start_dt,
        end=end_dt,
        camera=camera,
    )
    
    # Construct the expected file path based on the downloader's naming convention
    # The downloader creates files with format: "CameraName - YYYY-MM-DD - HH.MM.SS+ZZZZ.mp4"
    camera_name_fs_safe = make_camera_name_fs_safe(camera)
    
    # The file will be in the destination_path with the camera name and timestamp
    filename_timestamp = start_dt.strftime("%Y-%m-%d - %H.%M.%S%z")
    expected_filename = f"{camera_name_fs_safe} - {filename_timestamp}.mp4"
    expected_path = out_dir / expected_filename
    
    # Verify the file was actually created
    if not expected_path.exists():
        raise FileNotFoundError(
            f"Expected video file was not created: {expected_path}. "
            "The download may have failed."
        )
    
    logging.info(f"Video downloaded to: {expected_path}")
    return str(expected_path)
