#!/usr/bin/env python3
"""
Transcoder module for converting video files to audio WAV format.

This module provides functionality to convert downloaded video chunks
to audio-only WAV files with specific format requirements:
- Codec: pcm_s16le (16-bit PCM)
- Sample rate: 16000 Hz
- Channels: 1 (mono)

All transcoded files are stored in a temporary directory and cleaned up
on program termination.
"""

import logging
import tempfile
import atexit
import shutil
from pathlib import Path
from typing import Optional

import ffmpeg


# Global temp directory for transcoded WAV files
_temp_wav_dir: Optional[Path] = None


def _cleanup_temp_wav_dir():
    """
    Cleanup function to remove temporary WAV directory on program exit.
    Registered with atexit to ensure cleanup happens even on unexpected termination.
    """
    global _temp_wav_dir
    if _temp_wav_dir and _temp_wav_dir.exists():
        try:
            shutil.rmtree(_temp_wav_dir)
            logging.info(f"Cleaned up temporary WAV directory: {_temp_wav_dir}")
        except Exception as e:
            logging.warning(f"Failed to cleanup temporary WAV directory: {e}")
        _temp_wav_dir = None


def get_temp_wav_directory() -> Path:
    """
    Get or create the temporary directory for transcoded WAV files.
    
    The directory is created once and reused for all transcoding operations.
    It will be automatically cleaned up on program termination.
    
    Returns:
        Path: Path object pointing to the temporary WAV directory
    """
    global _temp_wav_dir
    
    if _temp_wav_dir is None or not _temp_wav_dir.exists():
        # Create a temporary directory for WAV files
        base_temp = Path(tempfile.gettempdir())
        _temp_wav_dir = base_temp / 'ubv_transcribe_wav'
        _temp_wav_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        # Register cleanup function
        atexit.register(_cleanup_temp_wav_dir)
        
        logging.info(f"Created temporary WAV directory: {_temp_wav_dir}")
    
    return _temp_wav_dir


def transcode_to_wav(
    video_path: str,
    output_wav_path: Optional[str] = None,
) -> str:
    """
    Transcode a video file to audio-only WAV format.
    
    Converts the video to a WAV file with the following specifications:
    - Codec: pcm_s16le (16-bit PCM)
    - Sample rate: 16000 Hz
    - Channels: 1 (mono)
    
    Args:
        video_path: Path to the input video file
        output_wav_path: Optional path for the output WAV file.
                        If None, generates a filename in the temp directory.
    
    Returns:
        Path to the transcoded WAV file
        
    Raises:
        FileNotFoundError: If the input video file does not exist
        RuntimeError: If ffmpeg transcoding fails
        
    Example:
        >>> wav_path = transcode_to_wav("/path/to/video.mp4")
        >>> print(f"WAV file created: {wav_path}")
    """
    video_file = Path(video_path)
    
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Determine output path
    if output_wav_path is None:
        temp_dir = get_temp_wav_directory()
        # Use the same base name but with .wav extension
        output_wav_path = str(temp_dir / f"{video_file.stem}.wav")
    
    output_file = Path(output_wav_path)
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Transcoding video to WAV: {video_path}")
    logging.debug(f"Output WAV path: {output_wav_path}")
    
    try:
        # Use ffmpeg-python to transcode
        # Input: video file
        # Output: WAV with pcm_s16le codec, 16kHz sample rate, mono channel
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            output_wav_path,
            acodec='pcm_s16le',  # 16-bit PCM codec
            ar=16000,            # Sample rate: 16000 Hz
            ac=1,                # Channels: 1 (mono)
            format='wav',        # Output format: WAV
        )
        
        # Run the ffmpeg command, overwriting output file if it exists
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        logging.info(f"Successfully transcoded to WAV: {output_wav_path}")
        
    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf-8') if e.stderr else "No error output"
        error_msg = f"FFmpeg transcoding failed for {video_path}: {stderr}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from e
    
    return str(output_file)


def cleanup_temp_files():
    """
    Manually trigger cleanup of temporary WAV files.
    
    This is useful for explicit cleanup during testing or when you want
    to free up space before program termination.
    
    Note: This function is automatically called on program exit via atexit.
    """
    _cleanup_temp_wav_dir()
