#!/usr/bin/env python3
"""
Transcript merger module for combining hourly transcripts into daily Markdown files.

This module provides functionality to:
- Track which video chunks have been transcribed
- Merge transcripts from hourly chunks into per-day Markdown files
- Include timestamps for auditability
- Prevent duplication by tracking processed chunks
"""

import logging
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Set


def get_chunk_identifier(camera_name: str, start_dt: datetime) -> str:
    """
    Generate a unique identifier for a video chunk.
    
    Args:
        camera_name: Name of the camera
        start_dt: Start datetime of the chunk
        
    Returns:
        Unique identifier string for the chunk
        
    Example:
        >>> from datetime import datetime
        >>> import pytz
        >>> tz = pytz.timezone('US/Pacific')
        >>> dt = tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        >>> get_chunk_identifier("Front Door", dt)
        'Front Door_2024-01-15_14:00:00'
    """
    timestamp = start_dt.strftime('%Y-%m-%d_%H:%M:%S')
    return f"{camera_name}_{timestamp}"


def get_daily_transcript_path(
    transcripts_dir: Path,
    camera_name: str,
    date: datetime,
) -> Path:
    """
    Get the path for a daily transcript markdown file.
    
    Creates the year directory if it doesn't exist.
    
    Args:
        transcripts_dir: Base transcripts directory
        camera_name: Name of the camera
        date: Date for the transcript
        
    Returns:
        Path to the daily transcript markdown file
        
    Example:
        >>> from pathlib import Path
        >>> from datetime import datetime
        >>> get_daily_transcript_path(Path("/transcripts"), "Front Door", datetime(2024, 1, 15))
        PosixPath('/transcripts/2024/2024-01-15_Front Door.md')
    """
    year = date.strftime('%Y')
    date_str = date.strftime('%Y-%m-%d')
    
    # Create year directory if it doesn't exist
    year_dir = transcripts_dir / year
    year_dir.mkdir(parents=True, exist_ok=True)
    
    # Filename format: YYYY-MM-DD_CAMERANAME.md
    filename = f"{date_str}_{camera_name}.md"
    return year_dir / filename


def load_processed_chunks(transcript_path: Path) -> Set[str]:
    """
    Load the set of already-processed chunk identifiers from a transcript file.
    
    Scans the transcript file for chunk metadata markers to determine
    which chunks have already been merged.
    
    Args:
        transcript_path: Path to the daily transcript markdown file
        
    Returns:
        Set of chunk identifiers that have been processed
        
    Example:
        >>> from pathlib import Path
        >>> processed = load_processed_chunks(Path("/path/to/transcript.md"))
        >>> "Front Door_2024-01-15_14:00:00" in processed
        True
    """
    if not transcript_path.exists():
        return set()
    
    processed = set()
    
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Look for chunk metadata markers: <!-- CHUNK: identifier -->
                if line.strip().startswith('<!-- CHUNK:') and line.strip().endswith('-->'):
                    # Extract identifier from: <!-- CHUNK: identifier -->
                    chunk_id = line.strip().removeprefix('<!-- CHUNK:').removesuffix('-->').strip()
                    processed.add(chunk_id)
    except Exception as e:
        logging.warning(f"Error loading processed chunks from {transcript_path}: {e}")
        return set()
    
    return processed


def is_chunk_already_processed(
    transcripts_dir: Path,
    camera_name: str,
    start_dt: datetime,
) -> bool:
    """
    Check if a chunk has already been processed and is in the daily transcript.
    
    This enables idempotent operation by checking the markdown state before
    downloading/transcoding/transcribing a chunk.
    
    Args:
        transcripts_dir: Base transcripts directory
        camera_name: Name of the camera
        start_dt: Start datetime of the chunk
        
    Returns:
        True if the chunk is already in the daily transcript, False otherwise
        
    Example:
        >>> from pathlib import Path
        >>> from datetime import datetime
        >>> import pytz
        >>> tz = pytz.timezone('US/Pacific')
        >>> dt = tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        >>> is_chunk_already_processed(Path("/transcripts"), "Front Door", dt)
        False
    """
    # Generate chunk identifier
    chunk_id = get_chunk_identifier(camera_name, start_dt)
    
    # Get the daily transcript path
    transcript_path = get_daily_transcript_path(transcripts_dir, camera_name, start_dt)
    
    # Load processed chunks
    processed_chunks = load_processed_chunks(transcript_path)
    
    return chunk_id in processed_chunks


def append_transcript_chunk(
    transcript_path: Path,
    chunk_id: str,
    camera_name: str,
    start_dt: datetime,
    end_dt: datetime,
    transcript_text: str,
) -> None:
    """
    Append a transcript chunk to a daily markdown file using atomic writes.
    
    Creates the file with a header if it doesn't exist, otherwise appends.
    Includes chunk metadata (timestamps) for auditability.
    Uses atomic write strategy (write to temp file then rename) to prevent
    corruption if the process is interrupted.
    
    Args:
        transcript_path: Path to the daily transcript markdown file
        chunk_id: Unique identifier for the chunk
        camera_name: Name of the camera
        start_dt: Start datetime of the chunk
        end_dt: End datetime of the chunk
        transcript_text: Transcript text to append
        
    Example:
        >>> from pathlib import Path
        >>> from datetime import datetime
        >>> append_transcript_chunk(
        ...     Path("/path/to/transcript.md"),
        ...     "Front Door_2024-01-15_14:00:00",
        ...     "Front Door",
        ...     datetime(2024, 1, 15, 14, 0),
        ...     datetime(2024, 1, 15, 15, 0),
        ...     "This is the transcript text"
        ... )
    """
    # Ensure parent directory exists
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists to determine if we need to write a header
    file_exists = transcript_path.exists()
    
    # Initialize variables for cleanup
    temp_fd = None
    temp_path = None
    
    try:
        # Create temporary file in the same directory as the target file
        # This ensures the temp file is on the same filesystem for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=transcript_path.parent,
            prefix='.tmp_transcript_',
            suffix='.md',
            text=True
        )
        
        # If the file already exists, copy its contents to the temp file first
        if file_exists:
            with open(transcript_path, 'r', encoding='utf-8') as src:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as dst:
                    shutil.copyfileobj(src, dst)
                    # temp_fd is now closed, open temp_path for appending
                    temp_fd = None
        else:
            # Close the file descriptor since we'll open the file normally
            os.close(temp_fd)
            temp_fd = None
        
        # Append new chunk content to the temp file
        with open(temp_path, 'a', encoding='utf-8') as f:
            # Write header if this is a new file
            if not file_exists:
                date_str = start_dt.strftime('%Y-%m-%d')
                f.write(f"# {date_str} - {camera_name}\n\n")
                f.write(f"Transcript for camera **{camera_name}** on {date_str}.\n\n")
                f.write("---\n\n")
            
            # Write chunk metadata (hidden HTML comment for tracking)
            f.write(f"<!-- CHUNK: {chunk_id} -->\n\n")
            
            # Write chunk header with timestamps
            start_time_str = start_dt.strftime('%H:%M:%S')
            end_time_str = end_dt.strftime('%H:%M:%S')
            f.write(f"## {start_time_str} - {end_time_str}\n\n")
            
            # Write the transcript text
            f.write(transcript_text.strip())
            f.write("\n\n")
            f.write("---\n\n")
        
        # Atomic rename - this is the key to preventing corruption
        # On Unix, os.replace() is atomic and will overwrite the destination
        os.replace(temp_path, transcript_path)
        
    except Exception as e:
        # Clean up temp file if something went wrong
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except Exception:
                pass
        if temp_path is not None and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise e


def merge_transcript_chunk(
    transcripts_dir: Path,
    camera_name: str,
    start_dt: datetime,
    end_dt: datetime,
    transcript_file: str,
) -> bool:
    """
    Merge a transcript chunk into the daily markdown file.
    
    Reads the transcript from the provided file, checks for duplication,
    and appends to the daily markdown file if not already processed.
    
    Args:
        transcripts_dir: Base transcripts directory
        camera_name: Name of the camera
        start_dt: Start datetime of the chunk
        end_dt: End datetime of the chunk
        transcript_file: Path to the transcript text file
        
    Returns:
        True if the chunk was merged, False if it was skipped (duplicate)
        
    Raises:
        FileNotFoundError: If the transcript file doesn't exist
        
    Example:
        >>> from pathlib import Path
        >>> from datetime import datetime
        >>> merge_transcript_chunk(
        ...     Path("/transcripts"),
        ...     "Front Door",
        ...     datetime(2024, 1, 15, 14, 0),
        ...     datetime(2024, 1, 15, 15, 0),
        ...     "/path/to/transcript.txt"
        ... )
        True
    """
    # Validate transcript file exists
    if not os.path.exists(transcript_file):
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")
    
    # Generate chunk identifier
    chunk_id = get_chunk_identifier(camera_name, start_dt)
    
    # Get the daily transcript path
    transcript_path = get_daily_transcript_path(transcripts_dir, camera_name, start_dt)
    
    # Check if this chunk has already been processed
    processed_chunks = load_processed_chunks(transcript_path)
    if chunk_id in processed_chunks:
        logging.info(
            f"Skipping duplicate chunk for {camera_name} "
            f"({start_dt.strftime('%Y-%m-%d %H:%M')})"
        )
        return False
    
    # Read the transcript text
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript_text = f.read()
    except Exception as e:
        logging.error(f"Failed to read transcript file {transcript_file}: {e}")
        raise
    
    # Append the chunk to the daily transcript
    logging.info(
        f"Merging transcript chunk for {camera_name} "
        f"({start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}) "
        f"into {transcript_path}"
    )
    
    append_transcript_chunk(
        transcript_path=transcript_path,
        chunk_id=chunk_id,
        camera_name=camera_name,
        start_dt=start_dt,
        end_dt=end_dt,
        transcript_text=transcript_text,
    )
    
    return True
