"""Regression tests for settings preservation, readiness, and pinned Node downloads."""

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('readiness', ROOT / 'lib/wait-startup.py')
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


def inline_js(kit):
    # First literal command block; no third-party test dependencies required.
    source = (ROOT / 'kits' / kit / 'spec.yaml').read_text().split('        - |\n')[1]
    return textwrap.dedent(source.split('    - description:')[0])


class SettingsTest(unittest.TestCase):
    def run_setup(self, kit, contents):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            target = home / '.claude/settings.json'
            target.parent.mkdir()
            if contents is not None:
                target.write_text(contents)
            defaults = home / '.local/share/sbx/claude-defaults/settings.json'
            defaults.parent.mkdir(parents=True)
            defaults.write_text('{"model":"default", "outputStyle":"Concise"}')
            result = subprocess.run(['node', '-e', inline_js(kit)],
                                    env=dict(os.environ, HOME=directory), capture_output=True, text=True)
            return result, target.read_text() if target.exists() else None

    def test_invalid_settings_are_preserved(self):
        for kit in ('claude-defaults', 'claude-statusline'):
            for source in ('{bad json', '[]', 'null', '"string"'):
                with self.subTest(kit=kit, source=source):
                    result, after = self.run_setup(kit, source)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(after, source)

    def test_missing_file_gets_defaults(self):
        for kit in ('claude-defaults', 'claude-statusline'):
            result, after = self.run_setup(kit, None)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(after))

    def test_existing_preferences_survive(self):
        original = {'model': None, 'custom': {'key': 'value'},
                    'statusLine': {'type': 'command', 'command': 'my-status'}}
        for kit in ('claude-defaults', 'claude-statusline'):
            result, after = self.run_setup(kit, json.dumps(original))
            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = json.loads(after)
            for key, value in original.items():
                self.assertEqual(parsed[key], value)


class ReadinessTest(unittest.TestCase):
    START = int(datetime(2026, 9, 16, tzinfo=timezone.utc).timestamp())
    OLD = '=== dispatcher run 2026-09-15T00:00:00Z ===\n'
    NEW = '=== dispatcher run 2026-09-16T00:00:00Z ===\n'
    COMPLETE = '=== dispatcher complete ===\n'

    def test_stale_completion_is_not_ready(self):
        self.assertIsNone(readiness.state(self.OLD + self.COMPLETE, self.START))

    def test_latest_run_controls_readiness(self):
        self.assertEqual(readiness.state(self.NEW + self.COMPLETE, self.START), 'complete')
        self.assertEqual(readiness.state(self.NEW + self.COMPLETE + self.NEW, self.START), 'running')
        self.assertEqual(readiness.state(self.NEW + 'fail step exit=1\n', self.START), 'failed')
        self.assertIsNone(readiness.state('', self.START))
        self.assertIsNone(readiness.state('=== dispatcher run invalid ===\n' + self.COMPLETE, self.START))

    def test_failure_cannot_be_overridden_by_completion(self):
        self.assertEqual(readiness.state(self.NEW + 'fail step\n' + self.COMPLETE, self.START), 'failed')

    def test_container_start_is_not_in_the_future(self):
        import time
        self.assertLessEqual(readiness.container_started(), time.time())


class FastResetTest(unittest.TestCase):
    def test_only_fast_settings_are_removed_and_failures_preserve_file(self):
        script = ROOT / 'kits/codex-defaults/files/home/.local/share/sbx/codex-defaults/reset-fast.py'
        cases = [
            ('service_tier = "fast"\n# keep\n[profiles.work]\nservice_tier = "flex"\n',
             '# keep\n[profiles.work]\nservice_tier = "flex"\n', 0),
            ('message = """\nservice_tier = "fast"\n"""\n', None, 0),
            ('profiles = {work = {service_tier = "fast"}}\n', None, 1),
            ('invalid = [\n', None, 1),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            for source, expected, code in cases:
                with self.subTest(source=source):
                    path.write_text(source)
                    result = subprocess.run(['python3', '-B', str(script)],
                                            env=dict(os.environ, CODEX_HOME=directory), capture_output=True)
                    self.assertEqual(result.returncode, code)
                    self.assertEqual(path.read_text(), source if expected is None else expected)


class NodeVersionTest(unittest.TestCase):
    def test_exact_version_uses_versioned_urls_and_checks_checksum(self):
        setup = (ROOT / 'kits/node-toolchain/files/home/.local/share/sbx/node-toolchain/setup.sh').read_text()
        function = setup[setup.index('install_node() {'):setup.index('\napt_install ${APT_PACKAGES')]
        # Stop deliberately at checksum validation, before installation. Network
        # and checksum tools are shell functions; no real downloads or /opt writes.
        with tempfile.TemporaryDirectory() as directory:
            calls = Path(directory) / 'calls'
            harness = '''
set -euo pipefail
log() { printf '%s\\n' "$*"; }
uname() { echo x86_64; }
curl() {
  printf '%s\\n' "$*" >> "$CALLS"
  if [[ "$*" == *SHASUMS256.txt ]]; then
    echo 'invalid-checksum  node-v99.88.77-linux-x64.tar.gz'
  fi
}
sha256sum() { return 1; }
DIST=https://nodejs.org/dist
''' + function + '\ninstall_node "$REQUESTED"\n'
            env = dict(os.environ, CALLS=str(calls), REQUESTED='99.88.77')
            result = subprocess.run(['bash', '-c', harness], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('checksum mismatch', result.stderr)
            self.assertIn('/v99.88.77/SHASUMS256.txt', calls.read_text())
            self.assertIn('/v99.88.77/node-v99.88.77-linux-x64.tar.gz', calls.read_text())
            self.assertNotIn('latest-', calls.read_text())
            calls.unlink()
            env['REQUESTED'] = 'bad;command'
            result = subprocess.run(['bash', '-c', harness], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(calls.exists())


class PinnedBuildTest(unittest.TestCase):
    def test_pinned_build_requires_digest_and_exact_release(self):
        dockerfile = (ROOT / 'Dockerfile.codex').read_text()
        guard = dockerfile.split('RUN case ', 1)[1].split('\n\n', 1)[0]
        command = 'case ' + guard.replace('\\\n', '')
        for mode, image, release, success in [
            ('rolling', 'image:latest', 'latest', True),
            ('pinned', 'image:latest', '0.154.0', False),
            ('pinned', 'image@sha256:' + 'a' * 64, 'latest', False),
            ('pinned', 'image@sha256:' + 'a' * 64, '0.154.0', True),
            ('typo', 'image:latest', 'latest', False),
        ]:
            with self.subTest(mode=mode, image=image, release=release):
                result = subprocess.run(['bash', '-c', command], capture_output=True,
                                        env=dict(os.environ, RELEASE_MODE=mode,
                                                 BASE_IMAGE=image, CODEX_RELEASE=release))
                self.assertEqual(result.returncode == 0, success, result.stderr)


if __name__ == '__main__':
    unittest.main()
