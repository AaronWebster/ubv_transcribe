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
import transcript_merger


# Keywords used to detect rate limiting errors
RATE_LIMIT_KEYWORDS = ['429', 'too many requests', 'rate limit', 'throttle']

# Sentinel value to indicate a chunk was skipped due to idempotency
CHUNK_SKIPPED = "skipped"


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
    transcripts_dir: Optional[Path] = None,
    whisper_bin: Optional[str] = None,
    model_path: Optional[str] = None,
) -> Optional[str]:
    """
    Download a video chunk with retry logic and exponential backoff, then transcode to WAV,
    transcribe with Whisper, and optionally merge into daily transcript.
    
    Handles transient failures including rate limiting (429-style errors)
    without crashing the entire download process. After successful download,
    transcodes the video to audio-only WAV format (16kHz, mono, pcm_s16le),
    transcribes it with Whisper, and optionally merges the transcript into a 
    daily markdown file if transcripts_dir is provided.
    
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
        transcripts_dir: Directory for merged transcripts (optional). If not provided,
                        transcripts will not be merged into daily files.
        whisper_bin: Path to whisper-cli binary (optional)
        model_path: Path to whisper model (optional)
        
    Returns:
        Path to the transcript text file on success, CHUNK_SKIPPED sentinel value if the 
        chunk was already processed (idempotency), or None if download/transcode/transcribe 
        failed after all retries. Note that merging failures are logged but do not cause 
        the function to return None - the transcript file path is still returned.
    """
    # Check if chunk is already processed (idempotency check)
    if transcripts_dir and transcript_merger.is_chunk_already_processed(
        transcripts_dir=transcripts_dir,
        camera_name=camera_name,
        start_dt=start_dt,
    ):
        logging.info(
            f"Skipping already-processed chunk for {camera_name} "
            f"({start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')})"
        )
        return CHUNK_SKIPPED  # Return sentinel value to indicate skip
    
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
            except Exception as transcode_error:
                logging.error(f"Failed to transcode video to WAV: {transcode_error}")
                # Consider transcoding failure as a chunk failure
                raise transcode_error
            
            # Transcribe the WAV file with Whisper
            try:
                # Generate output base path for whisper (without extension)
                wav_file = Path(wav_path)
                output_base = str(wav_file.parent / wav_file.stem)
                
                transcript_path = transcoder.run_whisper(
                    wav_path=wav_path,
                    output_base=output_base,
                    whisper_bin=whisper_bin,
                    model_path=model_path,
                )
                logging.info(f"Successfully transcribed to: {transcript_path}")
            except Exception as transcribe_error:
                logging.error(f"Failed to transcribe WAV file: {transcribe_error}")
                # Consider transcription failure as a chunk failure
                raise transcribe_error
            
            # Merge transcript into daily markdown file if transcripts_dir is provided
            if transcripts_dir:
                try:
                    merged = transcript_merger.merge_transcript_chunk(
                        transcripts_dir=transcripts_dir,
                        camera_name=camera_name,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        transcript_file=transcript_path,
                    )
                    if merged:
                        logging.info(f"Successfully merged transcript into daily file")
                    else:
                        logging.info(f"Transcript already merged (skipped duplicate)")
                except Exception as merge_error:
                    logging.error(f"Failed to merge transcript: {merge_error}")
                    # Log error but don't fail the chunk - we have the transcript file
            
            return transcript_path
            
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
    transcripts_dir: Optional[Path] = None,
    whisper_bin: Optional[str] = None,
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download footage for multiple cameras sequentially in hourly chunks.
    
    This is the main "download worker" that processes chunks one at a time
    with no parallel downloads. Each day is partitioned into hourly intervals.
    After downloading and transcoding, optionally transcribes with Whisper and
    merges transcripts into daily markdown files.
    
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
        transcripts_dir: Directory for merged transcripts (optional)
        whisper_bin: Path to whisper-cli binary (optional)
        model_path: Path to whisper model (optional)
        
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
                transcripts_dir=transcripts_dir,
                whisper_bin=whisper_bin,
                model_path=model_path,
            )
            
            # Count skipped chunks as successful (work already done)
            # Count None as failure, anything else (transcript path or "skipped") as success
            if result is not None:
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
