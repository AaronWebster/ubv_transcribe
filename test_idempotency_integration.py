#!/usr/bin/env python3
"""
Integration test to verify idempotent behavior of the download scheduler.

This test simulates the scenario where chunks are already processed in markdown
and verifies that re-running does not re-download/re-transcode/re-transcribe them.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytz

# Import the modules we're testing
import download_scheduler
import transcript_merger


def create_mock_transcript_file(transcripts_dir, camera_name, start_dt, end_dt):
    """Create a mock transcript file with a chunk marker."""
    # Get the daily transcript path
    daily_path = transcript_merger.get_daily_transcript_path(
        transcripts_dir, camera_name, start_dt
    )
    
    # Generate chunk identifier
    chunk_id = transcript_merger.get_chunk_identifier(camera_name, start_dt)
    
    # Append the chunk to the file
    transcript_merger.append_transcript_chunk(
        transcript_path=daily_path,
        chunk_id=chunk_id,
        camera_name=camera_name,
        start_dt=start_dt,
        end_dt=end_dt,
        transcript_text="Mock transcript content for testing.",
    )
    
    return daily_path


def test_idempotent_behavior():
    """Test that already-processed chunks are skipped."""
    print("=" * 70)
    print("IDEMPOTENCY INTEGRATION TEST")
    print("=" * 70)
    print()
    
    # Create temporary directories
    temp_base = tempfile.mkdtemp()
    transcripts_dir = Path(temp_base) / "transcripts"
    videos_dir = Path(temp_base) / "videos"
    transcripts_dir.mkdir(parents=True)
    videos_dir.mkdir(parents=True)
    
    try:
        # Setup test data
        tz = pytz.timezone('US/Pacific')
        cameras = [
            {'id': 'cam1', 'name': 'Front Door'},
            {'id': 'cam2', 'name': 'Back Door'},
        ]
        start_date = tz.localize(datetime(2024, 1, 15, 0, 0, 0))
        end_date = tz.localize(datetime(2024, 1, 15, 3, 0, 0))  # 3 hours
        
        # Pre-populate transcripts for some chunks (simulating prior run)
        print("Setting up mock transcripts for already-processed chunks...")
        print()
        
        # Camera 1, hour 0-1 (already processed)
        start_dt_0 = tz.localize(datetime(2024, 1, 15, 0, 0, 0))
        end_dt_0 = tz.localize(datetime(2024, 1, 15, 1, 0, 0))
        create_mock_transcript_file(transcripts_dir, 'Front Door', start_dt_0, end_dt_0)
        print(f"✓ Created mock transcript for Front Door, 00:00-01:00")
        
        # Camera 1, hour 2-3 (already processed)
        start_dt_2 = tz.localize(datetime(2024, 1, 15, 2, 0, 0))
        end_dt_2 = tz.localize(datetime(2024, 1, 15, 3, 0, 0))
        create_mock_transcript_file(transcripts_dir, 'Front Door', start_dt_2, end_dt_2)
        print(f"✓ Created mock transcript for Front Door, 02:00-03:00")
        
        # Camera 2, hour 1-2 (already processed)
        start_dt_1 = tz.localize(datetime(2024, 1, 15, 1, 0, 0))
        end_dt_1_cam2 = tz.localize(datetime(2024, 1, 15, 2, 0, 0))
        create_mock_transcript_file(transcripts_dir, 'Back Door', start_dt_1, end_dt_1_cam2)
        print(f"✓ Created mock transcript for Back Door, 01:00-02:00")
        
        print()
        print("Mock transcripts created. 3 out of 6 chunks are already processed.")
        print()
        print("-" * 70)
        print()
        
        # Mock the download/transcode/transcribe functions
        with patch('download_scheduler.downloader_adapter.download_chunk') as mock_download, \
             patch('download_scheduler.transcoder.transcode_to_wav') as mock_transcode, \
             patch('download_scheduler.transcoder.run_whisper') as mock_whisper:
            
            # Setup mock return values
            mock_download.return_value = "/path/to/video.mp4"
            mock_transcode.return_value = "/path/to/audio.wav"
            mock_whisper.return_value = "/path/to/transcript.txt"
            
            # Track which chunks were actually processed
            processed_chunks = []
            
            def track_download(*args, **kwargs):
                processed_chunks.append((kwargs['camera_id'], kwargs['start_dt']))
                return "/path/to/video.mp4"
            
            mock_download.side_effect = track_download
            
            print("Running download_footage_sequential with idempotency enabled...")
            print()
            
            # Run the download scheduler
            result = download_scheduler.download_footage_sequential(
                cameras=cameras,
                start_date=start_date,
                end_date=end_date,
                out_path=str(videos_dir),
                address='https://test.local',
                username='test',
                password='test',
                transcripts_dir=transcripts_dir,
            )
            
            print()
            print("-" * 70)
            print()
            print("RESULTS:")
            print(f"  Total chunks: {result['total_chunks']}")
            print(f"  Successful chunks: {result['successful_chunks']}")
            print(f"  Failed chunks: {result['failed_chunks']}")
            print()
            
            # Calculate expected behavior
            total_chunks = len(cameras) * 3  # 2 cameras × 3 hours = 6 chunks
            already_processed = 3  # We pre-populated 3 chunks
            expected_downloads = total_chunks - already_processed  # Should only download 3
            
            print("VERIFICATION:")
            print(f"  Expected total chunks: {total_chunks}")
            print(f"  Already processed: {already_processed}")
            print(f"  Expected new downloads: {expected_downloads}")
            print(f"  Actual download calls: {mock_download.call_count}")
            print()
            
            # Verify idempotent behavior
            success = True
            
            if mock_download.call_count != expected_downloads:
                print(f"✗ FAIL: Expected {expected_downloads} downloads, got {mock_download.call_count}")
                success = False
            else:
                print(f"✓ PASS: Correct number of downloads ({expected_downloads})")
            
            if mock_transcode.call_count != expected_downloads:
                print(f"✗ FAIL: Expected {expected_downloads} transcodes, got {mock_transcode.call_count}")
                success = False
            else:
                print(f"✓ PASS: Correct number of transcodes ({expected_downloads})")
            
            if mock_whisper.call_count != expected_downloads:
                print(f"✗ FAIL: Expected {expected_downloads} transcriptions, got {mock_whisper.call_count}")
                success = False
            else:
                print(f"✓ PASS: Correct number of transcriptions ({expected_downloads})")
            
            print()
            print("=" * 70)
            if success:
                print("✓ INTEGRATION TEST PASSED")
                print()
                print("Idempotency is working correctly:")
                print("  - Already-processed chunks were skipped")
                print("  - New chunks were processed normally")
                print("  - No re-downloading, re-transcoding, or re-transcribing occurred")
            else:
                print("✗ INTEGRATION TEST FAILED")
            print("=" * 70)
            
            return success
            
    finally:
        # Cleanup
        shutil.rmtree(temp_base)


if __name__ == '__main__':
    success = test_idempotent_behavior()
    sys.exit(0 if success else 1)
