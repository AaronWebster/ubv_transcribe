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
    
    @patch('transcoder.ffmpeg.run')
    @patch('transcoder.ffmpeg.output')
    @patch('transcoder.ffmpeg.input')
    def test_successful_transcode(self, mock_input, mock_output, mock_run):
        """Test successful transcoding with correct parameters."""
        # Setup mock chain
        mock_stream_in = MagicMock()
        mock_stream_out = MagicMock()
        mock_input.return_value = mock_stream_in
        mock_output.return_value = mock_stream_out
        
        # Call transcode
        output_path = os.path.join(self.temp_dir, 'output.wav')
        result = transcoder.transcode_to_wav(self.test_video_path, output_path)
        
        # Verify ffmpeg was called with correct parameters
        mock_input.assert_called_once_with(self.test_video_path)
        mock_output.assert_called_once()
        
        # Check that output was called with correct audio parameters
        output_call = mock_output.call_args
        self.assertEqual(output_call[0][1], output_path)
        self.assertEqual(output_call[1]['acodec'], 'pcm_s16le')
        self.assertEqual(output_call[1]['ar'], 16000)
        self.assertEqual(output_call[1]['ac'], 1)
        self.assertEqual(output_call[1]['format'], 'wav')
        
        # Verify run was called
        mock_run.assert_called_once()
        
        # Verify result
        self.assertEqual(result, output_path)
    
    @patch('transcoder.ffmpeg.run')
    @patch('transcoder.ffmpeg.output')
    @patch('transcoder.ffmpeg.input')
    def test_automatic_output_path(self, mock_input, mock_output, mock_run):
        """Test that output path is automatically generated when not provided."""
        # Setup mock chain
        mock_stream_in = MagicMock()
        mock_stream_out = MagicMock()
        mock_input.return_value = mock_stream_in
        mock_output.return_value = mock_stream_out
        
        # Call transcode without output path
        result = transcoder.transcode_to_wav(self.test_video_path)
        
        # Verify output path was generated
        self.assertTrue(result.endswith('.wav'))
        self.assertIn('test_video', result)
        self.assertIn('ubv_transcribe_wav', result)
    
    @patch('transcoder.ffmpeg.run')
    @patch('transcoder.ffmpeg.output')
    @patch('transcoder.ffmpeg.input')
    def test_ffmpeg_error_handling(self, mock_input, mock_output, mock_run):
        """Test error handling when ffmpeg fails."""
        # Setup mock to raise an error
        mock_stream_in = MagicMock()
        mock_stream_out = MagicMock()
        mock_input.return_value = mock_stream_in
        mock_output.return_value = mock_stream_out
        
        # Import the real ffmpeg module to use its Error class
        import ffmpeg
        
        # Create an ffmpeg.Error instance with stderr
        error = ffmpeg.Error('ffmpeg', b'stdout', b'Error details')
        mock_run.side_effect = error
        
        # Verify that RuntimeError is raised
        with self.assertRaises(RuntimeError) as context:
            transcoder.transcode_to_wav(self.test_video_path)
        
        self.assertIn('FFmpeg transcoding failed', str(context.exception))
    
    @patch('transcoder.ffmpeg.run')
    @patch('transcoder.ffmpeg.output')
    @patch('transcoder.ffmpeg.input')
    def test_overwrite_output(self, mock_input, mock_output, mock_run):
        """Test that existing output files are overwritten."""
        # Setup mock chain
        mock_stream_in = MagicMock()
        mock_stream_out = MagicMock()
        mock_input.return_value = mock_stream_in
        mock_output.return_value = mock_stream_out
        
        # Create existing output file
        output_path = os.path.join(self.temp_dir, 'existing.wav')
        with open(output_path, 'w') as f:
            f.write('existing content')
        
        # Call transcode
        transcoder.transcode_to_wav(self.test_video_path, output_path)
        
        # Verify run was called with overwrite_output=True
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
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


class TestRunWhisper(unittest.TestCase):
    """Test whisper transcription functionality."""
    
    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_wav_path = os.path.join(self.temp_dir, 'test_audio.wav')
        self.output_base = os.path.join(self.temp_dir, 'output')
        self.expected_output = f"{self.output_base}.txt"
        
        # Create a dummy WAV file for testing
        with open(self.test_wav_path, 'w') as f:
            f.write('dummy wav content')
    
    def tearDown(self):
        """Cleanup test files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_missing_wav_file(self):
        """Test error handling when input WAV doesn't exist."""
        nonexistent_wav = '/nonexistent/audio.wav'
        
        # Create fake binary and model files that exist
        fake_bin = os.path.join(self.temp_dir, 'whisper-cli')
        fake_model = os.path.join(self.temp_dir, 'model.bin')
        with open(fake_bin, 'w') as f:
            f.write('fake binary')
        with open(fake_model, 'w') as f:
            f.write('fake model')
        
        with self.assertRaises(FileNotFoundError) as context:
            transcoder.run_whisper(
                nonexistent_wav,
                self.output_base,
                whisper_bin=fake_bin,
                model_path=fake_model,
            )
        
        self.assertIn('Input WAV file not found', str(context.exception))
    
    def test_missing_whisper_binary(self):
        """Test error handling when whisper-cli binary doesn't exist."""
        fake_bin = '/nonexistent/whisper-cli'
        
        with self.assertRaises(FileNotFoundError) as context:
            transcoder.run_whisper(
                self.test_wav_path,
                self.output_base,
                whisper_bin=fake_bin,
            )
        
        self.assertIn('whisper-cli binary not found', str(context.exception))
    
    def test_missing_model_file(self):
        """Test error handling when model file doesn't exist."""
        # Create a fake binary file that exists
        fake_bin = os.path.join(self.temp_dir, 'whisper-cli')
        with open(fake_bin, 'w') as f:
            f.write('fake binary')
        
        fake_model = '/nonexistent/model.bin'
        
        with self.assertRaises(FileNotFoundError) as context:
            transcoder.run_whisper(
                self.test_wav_path,
                self.output_base,
                whisper_bin=fake_bin,
                model_path=fake_model,
            )
        
        self.assertIn('Whisper model not found', str(context.exception))
    
    @patch('transcoder.subprocess.run')
    @patch('transcoder.os.path.exists')
    def test_successful_transcription(self, mock_exists, mock_run):
        """Test successful whisper transcription."""
        # Setup mocks for file existence checks
        def exists_side_effect(path):
            # Return True for binary, model, wav, and output txt
            return True
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock successful subprocess run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Transcription complete'
        mock_result.stderr = ''
        mock_run.return_value = mock_result
        
        # Call run_whisper
        result = transcoder.run_whisper(
            self.test_wav_path,
            self.output_base,
            whisper_bin='/fake/bin/whisper-cli',
            model_path='/fake/models/model.bin',
        )
        
        # Verify result
        self.assertEqual(result, self.expected_output)
        
        # Verify subprocess.run was called
        mock_run.assert_called_once()
        
        # Verify the command arguments
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], '/fake/bin/whisper-cli')
        self.assertIn('--model', cmd)
        self.assertIn('/fake/models/model.bin', cmd)
        self.assertIn('--language', cmd)
        self.assertIn('en', cmd)
        self.assertIn('--threads', cmd)
        self.assertIn('6', cmd)
        self.assertIn('--processors', cmd)
        self.assertIn('1', cmd)
        self.assertIn('--max-context', cmd)
        self.assertIn('0', cmd)
        self.assertIn('--beam-size', cmd)
        self.assertIn('1', cmd)
        self.assertIn('--best-of', cmd)
        self.assertIn('1', cmd)
        self.assertIn('--temperature', cmd)
        self.assertIn('0.0', cmd)
        self.assertIn('--output-txt', cmd)
        self.assertIn('--output-file', cmd)
        self.assertIn(self.output_base, cmd)
        self.assertIn('--file', cmd)
        self.assertIn(self.test_wav_path, cmd)
    
    @patch('transcoder.subprocess.run')
    @patch('transcoder.os.path.exists')
    def test_command_structure(self, mock_exists, mock_run):
        """Test that the command is built with exact arguments from the issue."""
        # Setup mocks
        mock_exists.return_value = True
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ''
        mock_result.stderr = ''
        mock_run.return_value = mock_result
        
        # Call run_whisper
        transcoder.run_whisper(
            self.test_wav_path,
            self.output_base,
            whisper_bin='/fake/bin/whisper-cli',
            model_path='/fake/models/model.bin',
        )
        
        # Get the command that was executed
        cmd = mock_run.call_args[0][0]
        
        # Verify exact command structure
        expected_structure = [
            '/fake/bin/whisper-cli',
            '--model', '/fake/models/model.bin',
            '--language', 'en',
            '--threads', '6',
            '--processors', '1',
            '--max-context', '0',
            '--beam-size', '1',
            '--best-of', '1',
            '--temperature', '0.0',
            '--output-txt',
            '--output-file', self.output_base,
            '--file', self.test_wav_path,
        ]
        
        self.assertEqual(cmd, expected_structure)
    
    @patch('transcoder.subprocess.run')
    @patch('transcoder.os.path.exists')
    def test_subprocess_error_handling(self, mock_exists, mock_run):
        """Test error handling when whisper-cli subprocess fails."""
        # Setup mocks for file existence
        def exists_side_effect(path):
            # Return True for binary, model, and wav, but False for output
            if path.endswith('.txt'):
                return False
            return True
        
        mock_exists.side_effect = exists_side_effect
        
        # Mock subprocess failure
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=['whisper-cli'],
            output='stdout output',
            stderr='error details',
        )
        
        # Verify that RuntimeError is raised
        with self.assertRaises(RuntimeError) as context:
            transcoder.run_whisper(
                self.test_wav_path,
                self.output_base,
                whisper_bin='/fake/bin/whisper-cli',
                model_path='/fake/models/model.bin',
            )
        
        self.assertIn('Whisper transcription failed', str(context.exception))
    
    @patch('transcoder.subprocess.run')
    @patch('transcoder.os.path.exists')
    def test_default_paths(self, mock_exists, mock_run):
        """Test that default paths are used when not specified."""
        # Setup mocks
        mock_exists.return_value = True
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ''
        mock_result.stderr = ''
        mock_run.return_value = mock_result
        
        # Call without specifying binary or model paths
        transcoder.run_whisper(self.test_wav_path, self.output_base)
        
        # Verify subprocess.run was called
        mock_run.assert_called_once()
        
        # Get the command
        cmd = mock_run.call_args[0][0]
        
        # Verify default paths are used (expanded from ~)
        home = os.path.expanduser('~')
        expected_bin = os.path.join(home, 'whisper.cpp/build/bin/whisper-cli')
        expected_model = os.path.join(home, 'whisper.cpp/models/ggml-large-v3.bin')
        
        self.assertEqual(cmd[0], expected_bin)
        self.assertIn(expected_model, cmd)


if __name__ == '__main__':
    unittest.main()
