#!/usr/bin/env python3
"""
Unit tests for cleanup functionality.

Tests that intermediate files are properly cleaned up after processing.
"""

import unittest
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytz
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import download_scheduler
import ubv_transcribe


class TestCleanupFile(unittest.TestCase):
    """Test the _cleanup_file helper function."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_cleanup_existing_file(self):
        """Test that existing files are deleted."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, 'test.mp4')
        with open(test_file, 'w') as f:
            f.write('test content')
        
        self.assertTrue(os.path.exists(test_file))
        
        # Clean up the file
        download_scheduler._cleanup_file(test_file)
        
        # Verify file is deleted
        self.assertFalse(os.path.exists(test_file))
    
    def test_cleanup_nonexistent_file(self):
        """Test that cleanup handles non-existent files gracefully."""
        nonexistent_file = '/nonexistent/path/file.mp4'
        
        # Should not raise an exception
        download_scheduler._cleanup_file(nonexistent_file)
    
    def test_cleanup_none_path(self):
        """Test that cleanup handles None path gracefully."""
        # Should not raise an exception
        download_scheduler._cleanup_file(None)


class TestCleanupTranscriptsDirectory(unittest.TestCase):
    """Test cleanup of non-markdown files from transcripts directory."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / 'transcripts'
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_removes_non_markdown_files(self):
        """Test that non-markdown files are removed from transcripts directory."""
        # Create various file types
        (self.transcripts_dir / 'transcript.md').touch()
        (self.transcripts_dir / 'audio.wav').touch()
        (self.transcripts_dir / 'video.mp4').touch()
        (self.transcripts_dir / 'temp.txt').touch()
        
        # Create subdirectory with files
        year_dir = self.transcripts_dir / '2024'
        year_dir.mkdir()
        (year_dir / 'transcript.md').touch()
        (year_dir / 'temp.wav').touch()
        
        # Run cleanup
        ubv_transcribe._cleanup_transcripts_directory(self.transcripts_dir)
        
        # Verify only .md files remain
        self.assertTrue((self.transcripts_dir / 'transcript.md').exists())
        self.assertFalse((self.transcripts_dir / 'audio.wav').exists())
        self.assertFalse((self.transcripts_dir / 'video.mp4').exists())
        self.assertFalse((self.transcripts_dir / 'temp.txt').exists())
        
        # Verify subdirectory cleanup
        self.assertTrue((year_dir / 'transcript.md').exists())
        self.assertFalse((year_dir / 'temp.wav').exists())
    
    def test_handles_empty_directory(self):
        """Test that cleanup handles empty directory gracefully."""
        # Should not raise an exception
        ubv_transcribe._cleanup_transcripts_directory(self.transcripts_dir)
    
    def test_handles_nonexistent_directory(self):
        """Test that cleanup handles non-existent directory gracefully."""
        nonexistent_dir = Path('/nonexistent/transcripts')
        
        # Should not raise an exception
        ubv_transcribe._cleanup_transcripts_directory(nonexistent_dir)


class TestDownloadWithRetryCleanup(unittest.TestCase):
    """Test cleanup behavior in download_with_retry function."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / 'transcripts'
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        self.tz = pytz.timezone('US/Pacific')
        self.start_dt = self.tz.localize(datetime(2026, 1, 16, 14, 0, 0))
        self.end_dt = self.tz.localize(datetime(2026, 1, 16, 15, 0, 0))
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('download_scheduler._cleanup_file')
    @patch('download_scheduler.transcript_merger.merge_transcript_chunk')
    @patch('download_scheduler.transcoder.run_whisper')
    @patch('download_scheduler.transcoder.transcode_to_wav')
    @patch('download_scheduler.downloader_adapter.download_chunk')
    def test_cleanup_on_success(self, mock_download, mock_transcode, mock_whisper, mock_merge, mock_cleanup):
        """Test that files are cleaned up after successful processing."""
        # Setup mocks
        video_path = "/path/to/video.mp4"
        wav_path = "/path/to/audio.wav"
        transcript_path = "/path/to/transcript.txt"
        
        mock_download.return_value = video_path
        mock_transcode.return_value = wav_path
        mock_whisper.return_value = transcript_path
        mock_merge.return_value = True
        
        # Call the function
        result = download_scheduler.download_with_retry(
            camera_id="test_camera_id",
            camera_name="Test Camera",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            out_path=self.temp_dir,
            address="https://test.local",
            username="test_user",
            password="test_pass",
            transcripts_dir=self.transcripts_dir,
        )
        
        # Verify cleanup was called for all intermediate files
        self.assertEqual(mock_cleanup.call_count, 3)
        mock_cleanup.assert_any_call(video_path)
        mock_cleanup.assert_any_call(wav_path)
        mock_cleanup.assert_any_call(transcript_path)
        
        # Verify result is the transcript path
        self.assertEqual(result, transcript_path)
    
    @patch('download_scheduler._cleanup_file')
    @patch('download_scheduler.transcoder.transcode_to_wav')
    @patch('download_scheduler.downloader_adapter.download_chunk')
    def test_cleanup_on_transcode_failure(self, mock_download, mock_transcode, mock_cleanup):
        """Test that video file is cleaned up when transcoding fails."""
        # Setup mocks
        video_path = "/path/to/video.mp4"
        mock_download.return_value = video_path
        mock_transcode.side_effect = RuntimeError("Transcoding failed")
        
        # Call the function - should fail after max retries
        result = download_scheduler.download_with_retry(
            camera_id="test_camera_id",
            camera_name="Test Camera",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            out_path=self.temp_dir,
            address="https://test.local",
            username="test_user",
            password="test_pass",
            max_retries=0,  # Fail immediately
        )
        
        # Verify cleanup was called for the video file
        mock_cleanup.assert_any_call(video_path)
        
        # Verify function returns None on failure
        self.assertIsNone(result)
    
    @patch('download_scheduler._cleanup_file')
    @patch('download_scheduler.transcoder.run_whisper')
    @patch('download_scheduler.transcoder.transcode_to_wav')
    @patch('download_scheduler.downloader_adapter.download_chunk')
    def test_cleanup_on_whisper_failure(self, mock_download, mock_transcode, mock_whisper, mock_cleanup):
        """Test that video and WAV files are cleaned up when Whisper fails."""
        # Setup mocks
        video_path = "/path/to/video.mp4"
        wav_path = "/path/to/audio.wav"
        mock_download.return_value = video_path
        mock_transcode.return_value = wav_path
        mock_whisper.side_effect = RuntimeError("Whisper failed")
        
        # Call the function - should fail after max retries
        result = download_scheduler.download_with_retry(
            camera_id="test_camera_id",
            camera_name="Test Camera",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            out_path=self.temp_dir,
            address="https://test.local",
            username="test_user",
            password="test_pass",
            max_retries=0,  # Fail immediately
        )
        
        # Verify cleanup was called for video and WAV files
        mock_cleanup.assert_any_call(video_path)
        mock_cleanup.assert_any_call(wav_path)
        
        # Verify function returns None on failure
        self.assertIsNone(result)
    
    @patch('download_scheduler._cleanup_file')
    @patch('download_scheduler.transcript_merger.merge_transcript_chunk')
    @patch('download_scheduler.transcoder.run_whisper')
    @patch('download_scheduler.transcoder.transcode_to_wav')
    @patch('download_scheduler.downloader_adapter.download_chunk')
    def test_cleanup_on_merge_failure(self, mock_download, mock_transcode, mock_whisper, mock_merge, mock_cleanup):
        """Test that all files are cleaned up when merge fails."""
        # Setup mocks
        video_path = "/path/to/video.mp4"
        wav_path = "/path/to/audio.wav"
        transcript_path = "/path/to/transcript.txt"
        
        mock_download.return_value = video_path
        mock_transcode.return_value = wav_path
        mock_whisper.return_value = transcript_path
        mock_merge.side_effect = RuntimeError("Merge failed")
        
        # Call the function
        result = download_scheduler.download_with_retry(
            camera_id="test_camera_id",
            camera_name="Test Camera",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            out_path=self.temp_dir,
            address="https://test.local",
            username="test_user",
            password="test_pass",
            transcripts_dir=self.transcripts_dir,
        )
        
        # Verify cleanup was called for all files
        mock_cleanup.assert_any_call(video_path)
        mock_cleanup.assert_any_call(wav_path)
        mock_cleanup.assert_any_call(transcript_path)
        
        # Verify function still returns transcript path (merge failure is non-fatal)
        self.assertEqual(result, transcript_path)


if __name__ == '__main__':
    unittest.main()
