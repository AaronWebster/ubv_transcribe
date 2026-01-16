#!/usr/bin/env python3
"""
Integration test for cleanup functionality.

This test simulates the full workflow to verify that only markdown files
remain after processing.
"""

import unittest
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytz

import download_scheduler
import transcript_merger


class TestCleanupIntegration(unittest.TestCase):
    """Integration test for complete cleanup workflow."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / 'transcripts'
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir = Path(self.temp_dir) / 'videos'
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        
        self.tz = pytz.timezone('US/Pacific')
        self.start_dt = self.tz.localize(datetime(2026, 1, 16, 14, 0, 0))
        self.end_dt = self.tz.localize(datetime(2026, 1, 16, 15, 0, 0))
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_only_markdown_remains_after_success(self):
        """Test that only markdown files remain after successful processing."""
        # Create mock files that simulate the workflow
        video_file = self.videos_dir / "camera_2026-01-16_14.00.mp4"
        wav_file = Path(tempfile.gettempdir()) / "ubv_transcribe_wav" / "camera_2026-01-16_14.00.wav"
        transcript_file = wav_file.parent / "camera_2026-01-16_14.00.txt"
        
        # Create directories and files
        wav_file.parent.mkdir(parents=True, exist_ok=True)
        video_file.touch()
        wav_file.touch()
        transcript_file.write_text("Test transcript content")
        
        # Create markdown file that should remain
        year_dir = self.transcripts_dir / '2026'
        year_dir.mkdir(parents=True, exist_ok=True)
        markdown_file = year_dir / "2026-01-16_Test Camera.md"
        
        # Use transcript merger to create the markdown (simulating real workflow)
        transcript_merger.append_transcript_chunk(
            transcript_path=markdown_file,
            chunk_id="Test Camera_2026-01-16_14:00:00",
            camera_name="Test Camera",
            start_dt=self.start_dt,
            end_dt=self.end_dt,
            transcript_text="Test transcript content"
        )
        
        # Verify markdown was created
        self.assertTrue(markdown_file.exists())
        
        # Simulate cleanup by calling the helper functions
        download_scheduler._cleanup_file(str(video_file))
        download_scheduler._cleanup_file(str(wav_file))
        download_scheduler._cleanup_file(str(transcript_file))
        
        # Verify intermediate files are gone
        self.assertFalse(video_file.exists())
        self.assertFalse(wav_file.exists())
        self.assertFalse(transcript_file.exists())
        
        # Verify markdown file remains
        self.assertTrue(markdown_file.exists())
        
        # Verify markdown content is correct
        content = markdown_file.read_text()
        self.assertIn("Test transcript content", content)
        self.assertIn("Test Camera", content)
    
    def test_non_markdown_files_removed_from_transcripts(self):
        """Test that non-markdown files are removed from transcripts directory."""
        # Create markdown file that should remain
        markdown_file = self.transcripts_dir / "transcript.md"
        markdown_file.write_text("# Transcript")
        
        # Create files that should be removed
        wav_file = self.transcripts_dir / "audio.wav"
        txt_file = self.transcripts_dir / "temp.txt"
        mp4_file = self.transcripts_dir / "video.mp4"
        
        wav_file.touch()
        txt_file.touch()
        mp4_file.touch()
        
        # Verify all files exist
        self.assertTrue(markdown_file.exists())
        self.assertTrue(wav_file.exists())
        self.assertTrue(txt_file.exists())
        self.assertTrue(mp4_file.exists())
        
        # Import and call cleanup function
        import ubv_transcribe
        ubv_transcribe._cleanup_transcripts_directory(self.transcripts_dir)
        
        # Verify only markdown remains
        self.assertTrue(markdown_file.exists())
        self.assertFalse(wav_file.exists())
        self.assertFalse(txt_file.exists())
        self.assertFalse(mp4_file.exists())


if __name__ == '__main__':
    unittest.main()
