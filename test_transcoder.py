#!/usr/bin/env python3
"""
Unit tests for transcoder module.

Tests the transcoding functionality without requiring actual video files
where possible, and with mock video files for integration testing.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import transcoder


class TestGetTempWavDirectory(unittest.TestCase):
    """Test temporary WAV directory management."""
    
    def setUp(self):
        """Reset the global temp directory before each test."""
        transcoder._temp_wav_dir = None
    
    def tearDown(self):
        """Cleanup after each test."""
        if transcoder._temp_wav_dir and transcoder._temp_wav_dir.exists():
            import shutil
            shutil.rmtree(transcoder._temp_wav_dir)
        transcoder._temp_wav_dir = None
    
    def test_directory_creation(self):
        """Test that temp directory is created."""
        temp_dir = transcoder.get_temp_wav_directory()
        
        self.assertIsNotNone(temp_dir)
        self.assertTrue(temp_dir.exists())
        self.assertTrue(temp_dir.is_dir())
        self.assertIn('ubv_transcribe_wav', str(temp_dir))
    
    def test_directory_reuse(self):
        """Test that the same directory is reused on subsequent calls."""
        temp_dir1 = transcoder.get_temp_wav_directory()
        temp_dir2 = transcoder.get_temp_wav_directory()
        
        self.assertEqual(temp_dir1, temp_dir2)
    
    def test_cleanup_function(self):
        """Test that cleanup function removes the directory."""
        temp_dir = transcoder.get_temp_wav_directory()
        self.assertTrue(temp_dir.exists())
        
        transcoder._cleanup_temp_wav_dir()
        
        self.assertFalse(temp_dir.exists())
        self.assertIsNone(transcoder._temp_wav_dir)


class TestTranscodeToWav(unittest.TestCase):
    """Test transcoding functionality."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_video_path = os.path.join(self.temp_dir, 'test_video.mp4')
        
        # Create a dummy video file for testing
        with open(self.test_video_path, 'w') as f:
            f.write('dummy video content')
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Cleanup transcoder temp directory
        if transcoder._temp_wav_dir and transcoder._temp_wav_dir.exists():
            shutil.rmtree(transcoder._temp_wav_dir)
        transcoder._temp_wav_dir = None
    
    def test_file_not_found(self):
        """Test error handling when input video doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            transcoder.transcode_to_wav('/nonexistent/video.mp4')
    
    @patch('transcoder.ffmpeg')
    def test_successful_transcode(self, mock_ffmpeg):
        """Test successful transcoding with correct parameters."""
        # Setup mock
        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_ffmpeg.output.return_value = mock_stream
        mock_stream.run = MagicMock()
        
        # Call transcode
        output_path = os.path.join(self.temp_dir, 'output.wav')
        result = transcoder.transcode_to_wav(self.test_video_path, output_path)
        
        # Verify ffmpeg was called with correct parameters
        mock_ffmpeg.input.assert_called_once_with(self.test_video_path)
        mock_ffmpeg.output.assert_called_once()
        
        # Check that output was called with correct audio parameters
        output_call = mock_ffmpeg.output.call_args
        self.assertEqual(output_call[0][1], output_path)
        self.assertEqual(output_call[1]['acodec'], 'pcm_s16le')
        self.assertEqual(output_call[1]['ar'], 16000)
        self.assertEqual(output_call[1]['ac'], 1)
        self.assertEqual(output_call[1]['format'], 'wav')
        
        # Verify result
        self.assertEqual(result, output_path)
    
    @patch('transcoder.ffmpeg')
    def test_automatic_output_path(self, mock_ffmpeg):
        """Test that output path is automatically generated when not provided."""
        # Setup mock
        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_ffmpeg.output.return_value = mock_stream
        mock_stream.run = MagicMock()
        
        # Call transcode without output path
        result = transcoder.transcode_to_wav(self.test_video_path)
        
        # Verify output path was generated
        self.assertTrue(result.endswith('.wav'))
        self.assertIn('test_video', result)
        self.assertIn('ubv_transcribe_wav', result)
    
    @patch('transcoder.ffmpeg')
    def test_ffmpeg_error_handling(self, mock_ffmpeg):
        """Test error handling when ffmpeg fails."""
        # Setup mock to raise an error
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_ffmpeg.input.return_value = mock_input
        mock_ffmpeg.output.return_value = mock_output
        
        # Create a mock ffmpeg.Error
        class FFmpegError(Exception):
            def __init__(self):
                self.stderr = b"Error details"
        
        mock_ffmpeg.Error = FFmpegError
        mock_ffmpeg.run.side_effect = FFmpegError()
        
        # Verify that RuntimeError is raised
        with self.assertRaises(RuntimeError) as context:
            transcoder.transcode_to_wav(self.test_video_path)
        
        self.assertIn('FFmpeg transcoding failed', str(context.exception))
    
    @patch('transcoder.ffmpeg')
    def test_overwrite_output(self, mock_ffmpeg):
        """Test that existing output files are overwritten."""
        # Setup mock
        mock_input = MagicMock()
        mock_output = MagicMock()
        mock_ffmpeg.input.return_value = mock_input
        mock_ffmpeg.output.return_value = mock_output
        
        # Create existing output file
        output_path = os.path.join(self.temp_dir, 'existing.wav')
        with open(output_path, 'w') as f:
            f.write('existing content')
        
        # Call transcode
        transcoder.transcode_to_wav(self.test_video_path, output_path)
        
        # Verify run was called with overwrite_output=True
        mock_ffmpeg.run.assert_called_once()
        call_kwargs = mock_ffmpeg.run.call_args[1]
        self.assertTrue(call_kwargs.get('overwrite_output'))


class TestCleanupTempFiles(unittest.TestCase):
    """Test manual cleanup functionality."""
    
    def setUp(self):
        """Reset the global temp directory before each test."""
        transcoder._temp_wav_dir = None
    
    def tearDown(self):
        """Cleanup after each test."""
        if transcoder._temp_wav_dir and transcoder._temp_wav_dir.exists():
            import shutil
            shutil.rmtree(transcoder._temp_wav_dir)
        transcoder._temp_wav_dir = None
    
    def test_manual_cleanup(self):
        """Test manual cleanup of temporary files."""
        # Create temp directory
        temp_dir = transcoder.get_temp_wav_directory()
        self.assertTrue(temp_dir.exists())
        
        # Call manual cleanup
        transcoder.cleanup_temp_files()
        
        # Verify directory is removed
        self.assertFalse(temp_dir.exists())


if __name__ == '__main__':
    unittest.main()
