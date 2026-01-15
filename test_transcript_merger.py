#!/usr/bin/env python3
"""
Unit tests for transcript_merger module.

Tests the functionality for merging hourly transcript chunks into daily
Markdown files with deduplication and timestamp tracking.
"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path
from datetime import datetime
import pytz

import transcript_merger


class TestGetChunkIdentifier(unittest.TestCase):
    """Test chunk identifier generation."""
    
    def test_identifier_format(self):
        """Test that identifier has correct format."""
        tz = pytz.timezone('US/Pacific')
        dt = tz.localize(datetime(2024, 1, 15, 14, 30, 0))
        
        chunk_id = transcript_merger.get_chunk_identifier("Front Door", dt)
        
        self.assertEqual(chunk_id, "Front Door_2024-01-15_14:30:00")
    
    def test_identifier_uniqueness(self):
        """Test that different times produce different identifiers."""
        tz = pytz.timezone('US/Pacific')
        dt1 = tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        dt2 = tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        id1 = transcript_merger.get_chunk_identifier("Front Door", dt1)
        id2 = transcript_merger.get_chunk_identifier("Front Door", dt2)
        
        self.assertNotEqual(id1, id2)
    
    def test_identifier_same_for_same_input(self):
        """Test that same inputs produce same identifier."""
        tz = pytz.timezone('US/Pacific')
        dt = tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        
        id1 = transcript_merger.get_chunk_identifier("Front Door", dt)
        id2 = transcript_merger.get_chunk_identifier("Front Door", dt)
        
        self.assertEqual(id1, id2)


class TestGetDailyTranscriptPath(unittest.TestCase):
    """Test daily transcript path generation."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_path_format(self):
        """Test that path has correct format."""
        dt = datetime(2024, 1, 15)
        
        path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            dt
        )
        
        self.assertEqual(path.name, "2024-01-15_Front Door.md")
        self.assertEqual(path.parent.name, "2024")
    
    def test_creates_year_directory(self):
        """Test that year directory is created."""
        dt = datetime(2024, 1, 15)
        
        path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            dt
        )
        
        self.assertTrue(path.parent.exists())
        self.assertTrue(path.parent.is_dir())
    
    def test_different_years(self):
        """Test that different years create different directories."""
        dt1 = datetime(2024, 1, 15)
        dt2 = datetime(2025, 1, 15)
        
        path1 = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            dt1
        )
        path2 = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            dt2
        )
        
        self.assertNotEqual(path1.parent, path2.parent)
        self.assertEqual(path1.parent.name, "2024")
        self.assertEqual(path2.parent.name, "2025")


class TestLoadProcessedChunks(unittest.TestCase):
    """Test loading processed chunks from transcript files."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcript_path = Path(self.temp_dir) / "transcript.md"
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_nonexistent_file(self):
        """Test that nonexistent file returns empty set."""
        processed = transcript_merger.load_processed_chunks(self.transcript_path)
        
        self.assertEqual(len(processed), 0)
    
    def test_file_with_chunks(self):
        """Test loading chunks from file."""
        # Create a transcript file with chunk markers
        with open(self.transcript_path, 'w', encoding='utf-8') as f:
            f.write("# 2024-01-15 - Front Door\n\n")
            f.write("<!-- CHUNK: Front Door_2024-01-15_14:00:00 -->\n\n")
            f.write("## 14:00:00 - 15:00:00\n\n")
            f.write("Some transcript text\n\n")
            f.write("<!-- CHUNK: Front Door_2024-01-15_15:00:00 -->\n\n")
            f.write("## 15:00:00 - 16:00:00\n\n")
            f.write("More transcript text\n\n")
        
        processed = transcript_merger.load_processed_chunks(self.transcript_path)
        
        self.assertEqual(len(processed), 2)
        self.assertIn("Front Door_2024-01-15_14:00:00", processed)
        self.assertIn("Front Door_2024-01-15_15:00:00", processed)
    
    def test_file_without_chunks(self):
        """Test file with no chunk markers."""
        with open(self.transcript_path, 'w', encoding='utf-8') as f:
            f.write("# 2024-01-15 - Front Door\n\n")
            f.write("Some text without chunk markers\n\n")
        
        processed = transcript_merger.load_processed_chunks(self.transcript_path)
        
        self.assertEqual(len(processed), 0)


class TestAppendTranscriptChunk(unittest.TestCase):
    """Test appending transcript chunks to daily files."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcript_path = Path(self.temp_dir) / "transcript.md"
        self.tz = pytz.timezone('US/Pacific')
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_creates_new_file_with_header(self):
        """Test that new file is created with proper header."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        transcript_merger.append_transcript_chunk(
            transcript_path=self.transcript_path,
            chunk_id="Front Door_2024-01-15_14:00:00",
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_text="Test transcript",
        )
        
        self.assertTrue(self.transcript_path.exists())
        
        with open(self.transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("# 2024-01-15 - Front Door", content)
        self.assertIn("## 14:00:00 - 15:00:00", content)
        self.assertIn("Test transcript", content)
        self.assertIn("<!-- CHUNK: Front Door_2024-01-15_14:00:00 -->", content)
    
    def test_appends_to_existing_file(self):
        """Test that chunk is appended to existing file."""
        start_dt1 = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt1 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        start_dt2 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        end_dt2 = self.tz.localize(datetime(2024, 1, 15, 16, 0, 0))
        
        # Append first chunk
        transcript_merger.append_transcript_chunk(
            transcript_path=self.transcript_path,
            chunk_id="Front Door_2024-01-15_14:00:00",
            camera_name="Front Door",
            start_dt=start_dt1,
            end_dt=end_dt1,
            transcript_text="First chunk",
        )
        
        # Append second chunk
        transcript_merger.append_transcript_chunk(
            transcript_path=self.transcript_path,
            chunk_id="Front Door_2024-01-15_15:00:00",
            camera_name="Front Door",
            start_dt=start_dt2,
            end_dt=end_dt2,
            transcript_text="Second chunk",
        )
        
        with open(self.transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check that both chunks are present
        self.assertIn("First chunk", content)
        self.assertIn("Second chunk", content)
        
        # Check that header appears only once
        self.assertEqual(content.count("# 2024-01-15 - Front Door"), 1)
    
    def test_chunk_metadata_marker(self):
        """Test that chunk metadata is properly formatted."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        transcript_merger.append_transcript_chunk(
            transcript_path=self.transcript_path,
            chunk_id="Front Door_2024-01-15_14:00:00",
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_text="Test",
        )
        
        with open(self.transcript_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the chunk metadata line
        chunk_line = [l for l in lines if 'CHUNK:' in l][0]
        
        # Verify it's a proper HTML comment
        self.assertTrue(chunk_line.strip().startswith('<!--'))
        self.assertTrue(chunk_line.strip().endswith('-->'))


class TestMergeTranscriptChunk(unittest.TestCase):
    """Test merging transcript chunks into daily files."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / "transcripts"
        self.transcripts_dir.mkdir()
        
        # Create a test transcript file
        self.transcript_file = Path(self.temp_dir) / "test_transcript.txt"
        with open(self.transcript_file, 'w', encoding='utf-8') as f:
            f.write("This is a test transcript.")
        
        self.tz = pytz.timezone('US/Pacific')
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_successful_merge(self):
        """Test successful merge of a new chunk."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        result = transcript_merger.merge_transcript_chunk(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_file=str(self.transcript_file),
        )
        
        self.assertTrue(result)
        
        # Verify the daily transcript was created
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        self.assertTrue(daily_path.exists())
        
        # Verify content
        with open(daily_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("This is a test transcript", content)
        self.assertIn("Front Door", content)
    
    def test_duplicate_chunk_skipped(self):
        """Test that duplicate chunks are skipped."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        # Merge first time
        result1 = transcript_merger.merge_transcript_chunk(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_file=str(self.transcript_file),
        )
        
        # Merge second time (should be skipped)
        result2 = transcript_merger.merge_transcript_chunk(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_file=str(self.transcript_file),
        )
        
        self.assertTrue(result1)
        self.assertFalse(result2)
        
        # Verify content appears only once
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        
        with open(daily_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count occurrences of chunk marker
        self.assertEqual(content.count("Front Door_2024-01-15_14:00:00"), 1)
    
    def test_missing_transcript_file(self):
        """Test error handling when transcript file doesn't exist."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        with self.assertRaises(FileNotFoundError):
            transcript_merger.merge_transcript_chunk(
                transcripts_dir=self.transcripts_dir,
                camera_name="Front Door",
                start_dt=start_dt,
                end_dt=end_dt,
                transcript_file="/nonexistent/file.txt",
            )
    
    def test_multiple_chunks_chronological(self):
        """Test that multiple chunks are appended in order."""
        chunks = [
            (14, 15, "First hour"),
            (15, 16, "Second hour"),
            (16, 17, "Third hour"),
        ]
        
        for start_hour, end_hour, text in chunks:
            # Update transcript file content
            with open(self.transcript_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            start_dt = self.tz.localize(datetime(2024, 1, 15, start_hour, 0, 0))
            end_dt = self.tz.localize(datetime(2024, 1, 15, end_hour, 0, 0))
            
            transcript_merger.merge_transcript_chunk(
                transcripts_dir=self.transcripts_dir,
                camera_name="Front Door",
                start_dt=start_dt,
                end_dt=end_dt,
                transcript_file=str(self.transcript_file),
            )
        
        # Verify all chunks are present in order
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            self.tz.localize(datetime(2024, 1, 15)),
        )
        
        with open(daily_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check content order
        first_pos = content.find("First hour")
        second_pos = content.find("Second hour")
        third_pos = content.find("Third hour")
        
        self.assertLess(first_pos, second_pos)
        self.assertLess(second_pos, third_pos)


class TestIsChunkAlreadyProcessed(unittest.TestCase):
    """Test checking if a chunk has already been processed."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / "transcripts"
        self.transcripts_dir.mkdir()
        self.tz = pytz.timezone('US/Pacific')
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_chunk_not_processed_no_file(self):
        """Test that chunk is not processed when transcript file doesn't exist."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        
        result = transcript_merger.is_chunk_already_processed(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
        )
        
        self.assertFalse(result)
    
    def test_chunk_not_processed_empty_file(self):
        """Test that chunk is not processed when transcript file is empty."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        
        # Create empty transcript file
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        daily_path.touch()
        
        result = transcript_merger.is_chunk_already_processed(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
        )
        
        self.assertFalse(result)
    
    def test_chunk_is_processed(self):
        """Test that chunk is detected when it exists in transcript."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        # Create transcript with the chunk
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        
        chunk_id = transcript_merger.get_chunk_identifier("Front Door", start_dt)
        transcript_merger.append_transcript_chunk(
            transcript_path=daily_path,
            chunk_id=chunk_id,
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_text="Test transcript",
        )
        
        result = transcript_merger.is_chunk_already_processed(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt,
        )
        
        self.assertTrue(result)
    
    def test_different_chunk_not_processed(self):
        """Test that a different chunk is not detected as processed."""
        start_dt1 = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt1 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        start_dt2 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        # Create transcript with first chunk only
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt1,
        )
        
        chunk_id1 = transcript_merger.get_chunk_identifier("Front Door", start_dt1)
        transcript_merger.append_transcript_chunk(
            transcript_path=daily_path,
            chunk_id=chunk_id1,
            camera_name="Front Door",
            start_dt=start_dt1,
            end_dt=end_dt1,
            transcript_text="Test transcript",
        )
        
        # Check if second chunk is processed (should be False)
        result = transcript_merger.is_chunk_already_processed(
            transcripts_dir=self.transcripts_dir,
            camera_name="Front Door",
            start_dt=start_dt2,
        )
        
        self.assertFalse(result)
    
    def test_multiple_chunks_selective_detection(self):
        """Test that only specific chunks are detected as processed."""
        chunks = [
            (14, 15, True),   # This chunk will be added
            (15, 16, False),  # This chunk will NOT be added
            (16, 17, True),   # This chunk will be added
        ]
        
        for start_hour, end_hour, should_add in chunks:
            start_dt = self.tz.localize(datetime(2024, 1, 15, start_hour, 0, 0))
            end_dt = self.tz.localize(datetime(2024, 1, 15, end_hour, 0, 0))
            
            if should_add:
                daily_path = transcript_merger.get_daily_transcript_path(
                    self.transcripts_dir,
                    "Front Door",
                    start_dt,
                )
                chunk_id = transcript_merger.get_chunk_identifier("Front Door", start_dt)
                transcript_merger.append_transcript_chunk(
                    transcript_path=daily_path,
                    chunk_id=chunk_id,
                    camera_name="Front Door",
                    start_dt=start_dt,
                    end_dt=end_dt,
                    transcript_text=f"Chunk {start_hour}:00",
                )
        
        # Verify detection
        for start_hour, end_hour, expected_processed in chunks:
            start_dt = self.tz.localize(datetime(2024, 1, 15, start_hour, 0, 0))
            result = transcript_merger.is_chunk_already_processed(
                transcripts_dir=self.transcripts_dir,
                camera_name="Front Door",
                start_dt=start_dt,
            )
            self.assertEqual(result, expected_processed, 
                           f"Chunk at {start_hour}:00 should be {'processed' if expected_processed else 'not processed'}")


class TestAtomicWrites(unittest.TestCase):
    """Test atomic write behavior for transcript chunks."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.transcripts_dir = Path(self.temp_dir) / "transcripts"
        self.transcripts_dir.mkdir()
        self.tz = pytz.timezone('US/Pacific')
    
    def tearDown(self):
        """Cleanup test files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_atomic_write_creates_no_temp_files_on_success(self):
        """Test that no temporary files are left after successful write."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        
        chunk_id = transcript_merger.get_chunk_identifier("Front Door", start_dt)
        transcript_merger.append_transcript_chunk(
            transcript_path=daily_path,
            chunk_id=chunk_id,
            camera_name="Front Door",
            start_dt=start_dt,
            end_dt=end_dt,
            transcript_text="Test transcript",
        )
        
        # Check that the final file exists
        self.assertTrue(daily_path.exists())
        
        # Check that no temporary files are left in the directory
        temp_files = list(daily_path.parent.glob('.tmp_transcript_*'))
        self.assertEqual(len(temp_files), 0, 
                        f"Found {len(temp_files)} temporary files: {temp_files}")
    
    def test_atomic_write_preserves_existing_content(self):
        """Test that atomic write preserves existing file content when appending."""
        start_dt1 = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt1 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        start_dt2 = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        end_dt2 = self.tz.localize(datetime(2024, 1, 15, 16, 0, 0))
        
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt1,
        )
        
        # Write first chunk
        chunk_id1 = transcript_merger.get_chunk_identifier("Front Door", start_dt1)
        transcript_merger.append_transcript_chunk(
            transcript_path=daily_path,
            chunk_id=chunk_id1,
            camera_name="Front Door",
            start_dt=start_dt1,
            end_dt=end_dt1,
            transcript_text="First chunk content",
        )
        
        # Read content after first write
        with open(daily_path, 'r', encoding='utf-8') as f:
            content_after_first = f.read()
        
        # Write second chunk
        chunk_id2 = transcript_merger.get_chunk_identifier("Front Door", start_dt2)
        transcript_merger.append_transcript_chunk(
            transcript_path=daily_path,
            chunk_id=chunk_id2,
            camera_name="Front Door",
            start_dt=start_dt2,
            end_dt=end_dt2,
            transcript_text="Second chunk content",
        )
        
        # Read content after second write
        with open(daily_path, 'r', encoding='utf-8') as f:
            content_after_second = f.read()
        
        # Verify first chunk content is preserved
        self.assertIn("First chunk content", content_after_second)
        self.assertIn("Second chunk content", content_after_second)
        
        # Verify both chunk markers are present
        self.assertIn(chunk_id1, content_after_second)
        self.assertIn(chunk_id2, content_after_second)
    
    def test_atomic_write_multiple_appends(self):
        """Test that multiple atomic appends work correctly."""
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            self.tz.localize(datetime(2024, 1, 15, 0, 0, 0)),
        )
        
        # Append multiple chunks
        for hour in range(14, 18):
            start_dt = self.tz.localize(datetime(2024, 1, 15, hour, 0, 0))
            end_dt = self.tz.localize(datetime(2024, 1, 15, hour + 1, 0, 0))
            chunk_id = transcript_merger.get_chunk_identifier("Front Door", start_dt)
            
            transcript_merger.append_transcript_chunk(
                transcript_path=daily_path,
                chunk_id=chunk_id,
                camera_name="Front Door",
                start_dt=start_dt,
                end_dt=end_dt,
                transcript_text=f"Chunk for hour {hour}",
            )
        
        # Verify all chunks are present
        with open(daily_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for hour in range(14, 18):
            self.assertIn(f"Chunk for hour {hour}", content)
            chunk_id = f"Front Door_2024-01-15_{hour:02d}:00:00"
            self.assertIn(chunk_id, content)
        
        # Verify no temp files remain
        temp_files = list(daily_path.parent.glob('.tmp_transcript_*'))
        self.assertEqual(len(temp_files), 0)
    
    def test_atomic_write_error_cleanup(self):
        """Test that temporary files are cleaned up on error."""
        start_dt = self.tz.localize(datetime(2024, 1, 15, 14, 0, 0))
        end_dt = self.tz.localize(datetime(2024, 1, 15, 15, 0, 0))
        
        daily_path = transcript_merger.get_daily_transcript_path(
            self.transcripts_dir,
            "Front Door",
            start_dt,
        )
        
        chunk_id = transcript_merger.get_chunk_identifier("Front Door", start_dt)
        
        # Force an error during write by making the parent directory read-only
        # This test is platform-specific, so we'll simulate differently
        # Instead, we'll patch os.replace to raise an error
        import unittest.mock
        with unittest.mock.patch('os.replace', side_effect=OSError("Simulated error")):
            with self.assertRaises(OSError):
                transcript_merger.append_transcript_chunk(
                    transcript_path=daily_path,
                    chunk_id=chunk_id,
                    camera_name="Front Door",
                    start_dt=start_dt,
                    end_dt=end_dt,
                    transcript_text="Test transcript",
                )
        
        # Verify no temporary files are left after error
        if daily_path.parent.exists():
            temp_files = list(daily_path.parent.glob('.tmp_transcript_*'))
            self.assertEqual(len(temp_files), 0,
                           f"Temporary files not cleaned up: {temp_files}")


if __name__ == '__main__':
    unittest.main()
