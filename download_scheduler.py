#!/usr/bin/env python3
"""
Download scheduler module for UniFi Protect footage.

This module provides functionality to download full days in 1-hour chunks
with a single concurrent download stream and robust retry/backoff logic.
It also transcodes downloaded video chunks to audio-only WAV format.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import downloader_adapter
import transcoder


# Keywords used to detect rate limiting errors
RATE_LIMIT_KEYWORDS = ['429', 'too many requests', 'rate limit', 'throttle']


def generate_hourly_chunks(
    start_date: datetime,
    end_date: datetime,
) -> List[Tuple[datetime, datetime]]:
    """
    Generate hourly time chunks between start and end dates.
    
    Args:
        start_date: Start datetime (timezone-aware)
        end_date: End datetime (timezone-aware)
        
    Returns:
        List of (start_time, end_time) tuples representing hourly chunks.
        Gaps are allowed - the function generates all hourly intervals.
        
    Example:
        >>> from datetime import datetime, timedelta
        >>> import pytz
        >>> tz = pytz.timezone('US/Pacific')
        >>> start = tz.localize(datetime(2024, 1, 1, 0, 0, 0))
        >>> end = tz.localize(datetime(2024, 1, 1, 3, 0, 0))
        >>> chunks = generate_hourly_chunks(start, end)
        >>> len(chunks)
        3
    """
    if start_date >= end_date:
        logging.warning("Start date must be before end date")
        return []
    
    chunks = []
    current = start_date
    
    while current < end_date:
        # Calculate the end of this chunk (1 hour later or end_date, whichever is earlier)
        chunk_end = min(current + timedelta(hours=1), end_date)
        chunks.append((current, chunk_end))
        current = chunk_end
    
    logging.info(f"Generated {len(chunks)} hourly chunks from {start_date} to {end_date}")
    return chunks


def download_with_retry(
    camera_id: str,
    camera_name: str,
    start_dt: datetime,
    end_dt: datetime,
    out_path: str,
    address: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
    skip_existing_files: bool = True,
    max_retries: int = 5,
    initial_backoff: float = 1.0,
    max_backoff: float = 300.0,
) -> Optional[str]:
    """
    Download a video chunk with retry logic and exponential backoff, then transcode to WAV.
    
    Handles transient failures including rate limiting (429-style errors)
    without crashing the entire download process. After successful download,
    transcodes the video to audio-only WAV format (16kHz, mono, pcm_s16le).
    
    Args:
        camera_id: ID of the camera to download from
        camera_name: Name of the camera (for logging)
        start_dt: Start datetime for the video chunk
        end_dt: End datetime for the video chunk
        out_path: Directory path where the video file will be saved
        address: UniFi Protect address
        username: UniFi Protect username
        password: UniFi Protect password
        verify_ssl: Whether to verify SSL certificates
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system
        skip_existing_files: Whether to skip downloading if file already exists
        max_retries: Maximum number of retry attempts (default: 5)
        initial_backoff: Initial backoff delay in seconds (default: 1.0)
        max_backoff: Maximum backoff delay in seconds (default: 300.0)
        
    Returns:
        Path to the transcoded WAV file, or None if download/transcode failed after all retries
    """
    backoff = initial_backoff
    
    for attempt in range(max_retries + 1):
        try:
            logging.info(
                f"Downloading chunk for {camera_name} "
                f"({start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')})"
                + (f" - Attempt {attempt + 1}/{max_retries + 1}" if attempt > 0 else "")
            )
            
            file_path = downloader_adapter.download_chunk(
                camera_id=camera_id,
                start_dt=start_dt,
                end_dt=end_dt,
                out_path=out_path,
                address=address,
                username=username,
                password=password,
                verify_ssl=verify_ssl,
                not_unifi_os=not_unifi_os,
                skip_existing_files=skip_existing_files,
            )
            
            logging.info(f"Successfully downloaded chunk to: {file_path}")
            
            # Transcode the video to WAV format
            try:
                wav_path = transcoder.transcode_to_wav(file_path)
                logging.info(f"Successfully transcoded to WAV: {wav_path}")
                return wav_path
            except Exception as transcode_error:
                logging.error(f"Failed to transcode video to WAV: {transcode_error}")
                # Consider transcoding failure as a chunk failure
                raise transcode_error
            
        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = any(
                keyword in error_msg
                for keyword in RATE_LIMIT_KEYWORDS
            )
            
            if attempt < max_retries:
                # Apply exponential backoff
                if is_rate_limit:
                    # For rate limiting, use longer backoff
                    wait_time = min(backoff * 2, max_backoff)
                    logging.warning(
                        f"Rate limit detected for {camera_name} chunk "
                        f"({start_dt.strftime('%Y-%m-%d %H:%M')}). "
                        f"Retrying in {wait_time:.1f} seconds..."
                    )
                else:
                    # For other errors, use normal backoff
                    wait_time = min(backoff, max_backoff)
                    logging.warning(
                        f"Error downloading chunk for {camera_name}: {e}. "
                        f"Retrying in {wait_time:.1f} seconds..."
                    )
                
                time.sleep(wait_time)
                backoff *= 2  # Exponential backoff
            else:
                # Max retries reached
                logging.error(
                    f"Failed to download chunk for {camera_name} "
                    f"({start_dt.strftime('%Y-%m-%d %H:%M')}) after {max_retries + 1} attempts: {e}"
                )
                return None
    
    return None


def download_footage_sequential(
    cameras: List[Dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    out_path: str,
    address: str,
    username: str,
    password: str,
    verify_ssl: bool = False,
    not_unifi_os: bool = False,
    skip_existing_files: bool = True,
    max_retries: int = 5,
    initial_backoff: float = 1.0,
    max_backoff: float = 300.0,
) -> Dict[str, Any]:
    """
    Download footage for multiple cameras sequentially in hourly chunks.
    
    This is the main "download worker" that processes chunks one at a time
    with no parallel downloads. Each day is partitioned into hourly intervals.
    
    Args:
        cameras: List of camera dictionaries with 'id' and 'name' keys
        start_date: Start datetime (timezone-aware)
        end_date: End datetime (timezone-aware)
        out_path: Directory path where video files will be saved
        address: UniFi Protect address
        username: UniFi Protect username
        password: UniFi Protect password
        verify_ssl: Whether to verify SSL certificates
        not_unifi_os: Whether this is a legacy (non-UniFi OS) system
        skip_existing_files: Whether to skip downloading if file already exists
        max_retries: Maximum number of retry attempts per chunk
        initial_backoff: Initial backoff delay in seconds
        max_backoff: Maximum backoff delay in seconds
        
    Returns:
        Dictionary with download statistics:
        - total_chunks: Total number of chunks attempted
        - successful_chunks: Number of successfully downloaded chunks
        - failed_chunks: Number of failed chunks
        - cameras_processed: Number of cameras processed
    """
    logging.info(f"Starting sequential download for {len(cameras)} camera(s)")
    logging.info(f"Date range: {start_date} to {end_date}")
    logging.info(f"Output directory: {out_path}")
    
    # Ensure output directory exists
    Path(out_path).mkdir(parents=True, exist_ok=True)
    
    # Generate hourly chunks for the date range
    chunks = generate_hourly_chunks(start_date, end_date)
    
    total_chunks = len(cameras) * len(chunks)
    successful_chunks = 0
    failed_chunks = 0
    
    logging.info(
        f"Processing {total_chunks} total chunks "
        f"({len(cameras)} cameras × {len(chunks)} time intervals)"
    )
    
    # Process each camera sequentially
    for camera_idx, camera in enumerate(cameras, 1):
        camera_id = camera['id']
        camera_name = camera['name']
        
        logging.info(
            f"Processing camera {camera_idx}/{len(cameras)}: {camera_name} ({camera_id})"
        )
        
        # Process each chunk for this camera sequentially
        for chunk_idx, (chunk_start, chunk_end) in enumerate(chunks, 1):
            logging.debug(
                f"Chunk {chunk_idx}/{len(chunks)} for {camera_name}: "
                f"{chunk_start} to {chunk_end}"
            )
            
            result = download_with_retry(
                camera_id=camera_id,
                camera_name=camera_name,
                start_dt=chunk_start,
                end_dt=chunk_end,
                out_path=out_path,
                address=address,
                username=username,
                password=password,
                verify_ssl=verify_ssl,
                not_unifi_os=not_unifi_os,
                skip_existing_files=skip_existing_files,
                max_retries=max_retries,
                initial_backoff=initial_backoff,
                max_backoff=max_backoff,
            )
            
            if result:
                successful_chunks += 1
            else:
                failed_chunks += 1
                # Continue with next chunk despite failure
    
    logging.info("=" * 60)
    logging.info("DOWNLOAD SUMMARY")
    logging.info("=" * 60)
    logging.info(f"Total chunks attempted: {total_chunks}")
    logging.info(f"Successful downloads: {successful_chunks}")
    logging.info(f"Failed downloads: {failed_chunks}")
    if total_chunks > 0:
        logging.info(f"Success rate: {100 * successful_chunks / total_chunks:.1f}%")
    else:
        logging.info("Success rate: N/A (no chunks to download)")
    logging.info("=" * 60)
    
    return {
        'total_chunks': total_chunks,
        'successful_chunks': successful_chunks,
        'failed_chunks': failed_chunks,
        'cameras_processed': len(cameras),
    }
