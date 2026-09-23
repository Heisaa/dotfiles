"""Verify shared model provisioning without downloading weights or running sandboxd."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('voice_cache', ROOT / 'kits/pi/prepare-voice-model.py')
voice = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(voice)


class VoiceCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / 'cache with spaces'

    def download(self, args, **kwargs):
        archive = Path(args[args.index('--output') + 1])
        with tarfile.open(archive, 'w:bz2') as tar:
            for name in (*voice.FILES, 'base-encoder.onnx'):
                info = tarfile.TarInfo('sherpa-onnx-whisper-base/' + name)
                info.size = 7
                tar.addfile(info, io.BytesIO(b'fixture'))

    def test_extracts_only_required_files_and_reuses_cache(self):
        with patch.object(voice.subprocess, 'run', side_effect=self.download) as download:
            self.assertEqual(voice.prepare(self.cache), self.cache)
            self.assertEqual(voice.prepare(self.cache), self.cache)
            download.assert_called_once()
        model = self.cache / 'whisper-base'
        self.assertEqual({p.name for p in model.iterdir()}, {*voice.FILES, '.download-complete'})
        self.assertEqual(list(self.cache.glob('.download-*')), [])

    def test_failed_download_preserves_old_cache_and_retry_repairs(self):
        model = self.cache / 'whisper-base'
        model.mkdir(parents=True)
        (model / 'old').write_text('keep until success')
        with patch.object(voice.subprocess, 'run', side_effect=subprocess.CalledProcessError(22, 'curl')):
            with self.assertRaises(subprocess.CalledProcessError):
                voice.prepare(self.cache)
        self.assertEqual((model / 'old').read_text(), 'keep until success')
        self.assertFalse((model / '.download-complete').exists())
        self.assertEqual(list(self.cache.glob('.download-*')), [])
        with patch.object(voice.subprocess, 'run', side_effect=self.download):
            voice.prepare(self.cache)
        self.assertTrue(voice.complete(model))

    def test_incomplete_archive_is_not_published(self):
        def incomplete(args, **kwargs):
            archive = Path(args[args.index('--output') + 1])
            with tarfile.open(archive, 'w:bz2') as tar:
                info = tarfile.TarInfo('sherpa-onnx-whisper-base/base-tokens.txt')
                info.size = 7
                tar.addfile(info, io.BytesIO(b'fixture'))
        with patch.object(voice.subprocess, 'run', side_effect=incomplete):
            with self.assertRaises(ValueError):
                voice.prepare(self.cache)
        self.assertFalse((self.cache / 'whisper-base').exists())
        self.assertEqual(list(self.cache.glob('.download-*')), [])

    def test_startup_links_cache_and_preserves_conflicting_local_model(self):
        with patch.object(voice.subprocess, 'run', side_effect=self.download):
            voice.prepare(self.cache)
        spec = (ROOT / 'kits/pi/spec.yaml').read_text()
        block = spec.split('        - |\n', 1)[1].split('    - description:', 1)[0]
        script = '\n'.join(line[10:] for line in block.splitlines())
        home = Path(self.tmp.name) / 'sandbox-home'
        env = dict(os.environ, HOME=str(home), SBX_PI_VOICE_CACHE=str(self.cache))
        def run():
            return subprocess.run(['node', '-e', script], env=env, text=True, capture_output=True)
        self.assertEqual(run().returncode, 0)
        self.assertEqual(run().returncode, 0)
        target = home / '.pi/models/whisper-base'
        self.assertEqual(target.resolve(), self.cache / 'whisper-base')
        target.unlink()
        target.mkdir()
        (target / 'local').write_text('preserve')
        self.assertNotEqual(run().returncode, 0)
        self.assertEqual((target / 'local').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
