"""Test host launcher paths and sandbox provisioning without a host sbx daemon."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "kits/codex-clipboard/files/home/.local/share/sbx/codex-clipboard"
MOCK = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
from unittest.mock import patch
args = sys.argv[1:]
with open(os.environ['SBX_TEST_CALLS'], 'a') as calls:
    calls.write(json.dumps(args) + '\n')
if args[:2] == ['ls', '-q']:
    if os.environ.get('SBX_TEST_FAIL_LS'): sys.exit(7)
    if os.environ['SBX_TEST_EXISTING'] == 'yes':
        print(os.environ['SBX_TEST_NAME'])
elif args[0] == 'kit':
    assert Path(args[2], 'spec.yaml').is_file(), args
elif args[:2] == ['skills', 'import']:
    if os.environ.get('SBX_TEST_FAIL_SKILLS_IMPORT'): sys.exit(8)
elif args[0] == 'exec':
    if args[1:3] == ['-u', 'root']:
        command = args[4:]
    else:
        command = args[2:]
    if command == ['codex', 'login', 'status']:
        if os.environ.get('SBX_TEST_NO_LOGIN'):
            print('Not logged in', file=sys.stderr)
            sys.exit(1)
        print('Logged in using ChatGPT', file=sys.stderr)
    elif command == ['codex', 'remote-control', 'start']:
        if os.environ.get('SBX_TEST_FAIL_REMOTE'):
            print('test: remote control failed', file=sys.stderr)
            sys.exit(1)
    elif command[:2] == ['python3', '-c'] and 'def container_started():' in command[2]:
        if os.environ.get('SBX_TEST_FAIL_STARTUP'):
            print('Startup kit failed', file=sys.stderr)
            sys.exit(1)
        if os.environ.get('SBX_TEST_STALE_STARTUP') and not Path(os.environ['SBX_TEST_REPLAYED']).exists():
            print('Startup dispatcher did not run for the current container start.', file=sys.stderr)
            sys.exit(75)
    elif command == ['/etc/durable-startup.d/run.sh']:
        Path(os.environ['SBX_TEST_REPLAYED']).touch()
    elif command[:2] == ['sh', '-c'] and 'exec update-codex-native' in command[2]:
        if os.environ.get('SBX_TEST_FAIL_UPDATE'): sys.exit(1)
    elif command[:2] == ['python3', '-c']:
        sys.argv = ['-c', *command[3:]]
        with patch.object(Path, 'home', return_value=Path(os.environ['SBX_TEST_DEST'])):
            exec(compile(command[2], '<sandbox provisioning>', 'exec'))
    elif command[:1] == ['bash']:
        assert command[1] == '/home/agent/.local/share/sbx/codex-clipboard/setup.sh'
        if os.environ.get('SBX_TEST_FAIL_SETUP'):
            print('test: sandbox installer failed', file=sys.stderr)
            sys.exit(1)
    else:
        print('0.154.0')
elif args[0] == 'run':
    Path(os.environ['SBX_TEST_LOG']).write_text(json.dumps({
        'args': args, 'herdr': os.environ.get('HERDR_AGENT'),
    }))
'''


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sbx-launcher-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.project = self.root / "work"
        self.project.mkdir()
        self.dest = self.root / "sandbox-home"
        self.dest.mkdir()
        self.host_home = self.root / "host-home"
        self.host_home.mkdir()
        (self.bin / "sbx").write_text(MOCK)
        (self.bin / "sbx").chmod(0o755)
        self.log = self.root / "run.json"
        self.env = dict(os.environ, HOME=str(self.host_home),
                        PATH=str(self.bin) + ":" + os.environ["PATH"],
                        SBX_TEST_DEST=str(self.dest), SBX_TEST_LOG=str(self.log),
                        SBX_TEST_CALLS=str(self.root / 'calls.jsonl'),
                        SBX_TEST_REPLAYED=str(self.root / 'startup-replayed'),
                        SBX_TEST_EXISTING="yes")
        self.env.pop('CODEX_HOME', None)
        for key in list(self.env):
            if key.startswith('SBX_') and not key.startswith('SBX_TEST_'):
                del self.env[key]

    def launch(self, launcher=ROOT / "sbx-agent", agent="codex"):
        checksum = subprocess.check_output(["cksum"], input=str(self.project).encode()).split()[0].decode()
        self.env["SBX_TEST_NAME"] = f"{agent}-work-{checksum}"
        if (self.project / '.git').is_file():
            self.env['SBX_TEST_NAME'] += '-wt'
        if self.env.get('SBX_PRESET') == 'minimal':
            self.env['SBX_TEST_NAME'] += '-minimal'
        if self.env.get('SBX_RELEASE_MODE') == 'pinned':
            template = self.env['SBX_CODEX_TEMPLATE']
            pin = subprocess.check_output(['cksum'], input=template.encode()).split()[0].decode()
            self.env['SBX_TEST_NAME'] += '-pinned-' + pin
        result = subprocess.run([str(launcher), agent, "resume", "literal $() argument"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        call = json.loads(self.log.read_text())
        self.assertEqual(call["herdr"], agent)
        self.assertIn("--", call["args"])
        self.assertEqual(call["args"][-2:], ["resume", "literal $() argument"])
        return result, call["args"]

    def assert_payload(self):
        for filename in ("bridge.py", "setup.sh"):
            copied = self.dest / ".local/share/sbx/codex-clipboard" / filename
            self.assertEqual(copied.read_text(), (PAYLOAD / filename).read_text().rstrip("\n"))

    def test_existing_sandbox_from_another_project(self):
        config = self.dest / '.codex/config.toml'
        config.parent.mkdir()
        config.write_text('forced_login_method = "api"\nmodel_provider = "sandboxd"\n'
                          '[model_providers.sandboxd]\nrequires_openai_auth = false\n')
        _, args = self.launch()
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed['forced_login_method'], 'chatgpt')
        self.assertEqual(parsed['model_provider'], 'openai')
        self.assertFalse(parsed['model_providers']['sandboxd']['requires_openai_auth'])
        first = config.read_text()
        self.launch()
        self.assertEqual(config.read_text(), first)
        self.assertIn("DISPLAY=:0", args)
        self.assert_payload()

    def test_symlink_chain(self):
        (self.root / "launcher").symlink_to(ROOT / "sbx-agent")
        linked = self.bin / "sbx-agent"
        linked.symlink_to("../launcher")
        _, args = self.launch(linked)
        self.assertIn("DISPLAY=:0", args)
        self.assert_payload()

    def test_new_sandbox(self):
        self.env["SBX_TEST_EXISTING"] = "no"
        _, args = self.launch()
        self.assertIn("DISPLAY=:0", args)
        self.assert_payload()
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        create = next(call for call in calls if call[0] == 'create')
        self.assertEqual(create[create.index('--template') + 1], 'docker.io/local/codex-native:latest')
        self.assertIn('--skills=readonly', create)
        self.assertNotIn(str(ROOT / 'kits/shared-skills'), create)
        self.assertIn(['skills', 'import', '--force'], calls)
        host_skills = self.host_home / '.agents/skills'
        for name in ('feature-planning', 'write-commit', 'write-pr'):
            self.assertTrue((host_skills / name).is_symlink())
            self.assertEqual((host_skills / name).resolve(),
                             ROOT / 'kits/shared-skills/files/home/.agents/skills' / name)

    def test_linked_worktree_mounts_its_common_git_directory(self):
        main = self.root / 'main'
        subprocess.run(['git', 'init', str(main)], check=True, capture_output=True)
        (main / 'README').write_text('test\n')
        subprocess.run(['git', '-C', str(main), 'add', 'README'], check=True)
        subprocess.run(['git', '-C', str(main), '-c', 'user.name=test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-m', 'initial'],
                       check=True, capture_output=True)
        self.project.rmdir()
        subprocess.run(['git', '-C', str(main), 'worktree', 'add', '-b', 'feature/test',
                        str(self.project)], check=True, capture_output=True)
        self.env['SBX_TEST_EXISTING'] = 'no'

        result, _ = self.launch()
        create = next(c for c in self.calls() if c[0] == 'create')
        self.assertEqual(create[-2:], [str(self.project), str(main / '.git')])
        self.assertIn('-wt', self.env['SBX_TEST_NAME'])
        self.assertIn('Mounting shared Git directory', result.stdout)

    def test_failed_skills_import_does_not_create_or_launch(self):
        self.env['SBX_TEST_EXISTING'] = 'no'
        self.env['SBX_TEST_FAIL_SKILLS_IMPORT'] = '1'
        result = self.raw('codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot import shared agent skills', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse(any(call[0] == 'create' for call in self.calls()))

    def test_codex_search_and_native_updates(self):
        _, args = self.launch()
        self.assertIn('--search', args)
        self.assertIn('standalone_web_search', args)
        self.assertIn('forced_login_method=chatgpt', args)
        self.assertIn('model_provider=openai', args)
        self.assertIn('suppress_unstable_features_warning=true', args)
        calls = (self.root / 'calls.jsonl').read_text()
        self.assertIn('exec update-codex-native', calls)
        self.assertNotIn('npm', calls)

    def test_missing_host_payload_still_launches(self):
        isolated = self.root / "sbx-agent"
        shutil.copy2(ROOT / "sbx-agent", isolated)
        shutil.copytree(ROOT / "lib", self.root / "lib")
        shutil.copytree(ROOT / 'kits/codex-defaults', self.root / 'kits/codex-defaults')
        shutil.copytree(ROOT / 'kits/shared-skills', self.root / 'kits/shared-skills')
        result, args = self.launch(isolated)
        self.assertIn("Clipboard source missing on host:", result.stderr)
        self.assertNotIn("DISPLAY=:0", args)

    def test_remote_control_starts_before_launch(self):
        self.launch()
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        remote = next(i for i, call in enumerate(calls) if call[2:] == ['codex', 'remote-control', 'start'])
        launch = next(i for i, call in enumerate(calls) if call[0] == 'run')
        self.assertLess(remote, launch)
        self.assertFalse(any('restart' in call or 'pair' in call for call in calls))

    def test_no_login_skips_remote_control(self):
        self.env['SBX_TEST_NO_LOGIN'] = 'yes'
        result, _ = self.launch()
        self.assertIn('codex login --device-auth', result.stdout)
        calls = (self.root / 'calls.jsonl').read_text()
        self.assertNotIn('remote-control', calls)

    def test_remote_control_failure_still_launches(self):
        self.env['SBX_TEST_FAIL_REMOTE'] = 'yes'
        result, _ = self.launch()
        self.assertIn('Remote control could not start', result.stderr)

    def test_failed_sandbox_install_still_launches(self):
        self.env["SBX_TEST_FAIL_SETUP"] = "yes"
        result, args = self.launch()
        self.assertIn("sandbox installer failed", result.stderr)
        self.assertNotIn("DISPLAY=:0", args)

    def test_claude_does_not_install_clipboard(self):
        _, args = self.launch(agent="claude")
        self.assertNotIn("DISPLAY=:0", args)
        self.assertEqual(list(self.dest.iterdir()), [])
        self.assertNotIn('--search', args)
        self.assertNotIn('remote-control', (self.root / 'calls.jsonl').read_text())

    def raw(self, *args):
        return subprocess.run([str(ROOT / 'sbx-agent'), *args], cwd=self.project,
                              env=self.env, capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]

    def test_ls_failure_does_not_create(self):
        self.env['SBX_TEST_FAIL_LS'] = '1'
        result = self.raw('codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Cannot list sandboxes', result.stderr)
        self.assertEqual(self.calls(), [['ls', '-q']])

    def test_failed_existing_startup_never_launches_or_updates(self):
        self.launch()  # Establish an existing sandbox name.
        self.log.unlink()
        (self.root / 'calls.jsonl').write_text('')
        self.env['SBX_TEST_FAIL_STARTUP'] = '1'
        result = self.raw('codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Startup kit failed', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(len(self.calls()), 3)  # list, skills import, readiness

    def test_stale_startup_is_replayed_before_launch(self):
        self.env['SBX_TEST_STALE_STARTUP'] = '1'
        result, _ = self.launch()
        self.assertIn('Replaying sandbox startup kits', result.stdout)
        calls = self.calls()
        replay = next(i for i, call in enumerate(calls)
                      if call == ['exec', '-u', 'root', self.env['SBX_TEST_NAME'],
                                  '/etc/durable-startup.d/run.sh'])
        readiness = [i for i, call in enumerate(calls)
                     if call[:2] == ['exec', self.env['SBX_TEST_NAME']]
                     and call[2:4] == ['python3', '-c']
                     and 'def container_started():' in call[4]]
        launch = next(i for i, call in enumerate(calls) if call[0] == 'run')
        self.assertEqual(len(readiness), 2)
        self.assertLess(readiness[0], replay)
        self.assertLess(replay, readiness[1])
        self.assertLess(readiness[1], launch)

    def test_fast_reset_on_every_agent_launch(self):
        self.launch()
        config = self.dest / '.codex/config.toml'
        config.write_text(config.read_text() + '\n[profiles.work]\nservice_tier = "fast"\nmodel = "keep"\n')
        self.launch()
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed['profiles']['work'], {'model': 'keep'})

    def test_minimal_preserves_configuration(self):
        self.env['SBX_PRESET'] = 'minimal'
        self.env['SBX_TEST_EXISTING'] = 'no'
        config = self.dest / '.codex/config.toml'
        config.parent.mkdir()
        original = 'model_provider = "custom"\nservice_tier = "fast"\n'
        config.write_text(original)
        _, args = self.launch()
        self.assertEqual(config.read_text(), original)
        self.assertNotIn('--search', args)
        self.assertNotIn('DISPLAY=:0', args)
        create = next(c for c in self.calls() if c[0] == 'create')
        self.assertNotIn('--kit', create)
        self.assertIn('--skills=off', create)
        self.assertFalse(any(c[:2] == ['skills', 'import'] for c in self.calls()))
        self.assertFalse(any('exec update-codex-native' in str(c) for c in self.calls()))

    def test_options_reach_creation(self):
        self.env.update(SBX_TEST_EXISTING='no', SBX_CODEX_AUTH='preserve',
                        SBX_NODE_VERSION='26.8.1', SBX_REMOTE_CONTROL='false',
                        SBX_SHARED_SKILLS='false')
        _, args = self.launch()
        create = next(c for c in self.calls() if c[0] == 'create')
        self.assertIn('node-toolchain.version=26.8.1', create)
        self.assertIn('codex-defaults.auth=preserve', create)
        self.assertNotIn(str(ROOT / 'kits/shared-skills'), create)
        self.assertIn('--skills=off', create)
        self.assertFalse(any(c[:2] == ['skills', 'import'] for c in self.calls()))
        self.assertNotIn('forced_login_method=chatgpt', args)
        self.assertFalse(any('remote-control' in c for c in self.calls()))

    def test_explicit_update_does_not_launch(self):
        self.env['SBX_AUTO_UPDATE'] = 'false'
        self.launch()
        self.log.unlink()
        (self.root / 'calls.jsonl').write_text('')
        result = self.raw('update', 'codex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.log.exists())
        self.assertTrue(any('exec update-codex-native' in str(c) for c in self.calls()))
        self.env['SBX_TEST_FAIL_UPDATE'] = '1'
        self.assertNotEqual(self.raw('update', 'codex').returncode, 0)

    def test_pinned_mode_requires_digest_and_skips_mutable_installs(self):
        self.env['SBX_RELEASE_MODE'] = 'pinned'
        result = self.raw('codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('@sha256', result.stderr)
        self.env['SBX_CODEX_TEMPLATE'] = 'example/image@sha256:' + 'a' * 64
        self.env['SBX_TEST_EXISTING'] = 'no'
        _, args = self.launch()
        create = next(c for c in self.calls() if c[0] == 'create')
        self.assertNotIn(str(ROOT / 'kits/node-toolchain'), create)
        self.assertNotIn('DISPLAY=:0', args)
        self.assertFalse(any('exec update-codex-native' in str(c) for c in self.calls()))
        self.assertNotEqual(self.raw('update', 'codex').returncode, 0)


if __name__ == "__main__":
    unittest.main()
