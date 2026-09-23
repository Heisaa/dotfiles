"""Exercise the host launcher without requiring sandboxd or credentials."""
import json
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import termios
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOCK_SBX = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(args) + '\n')
if args[:2] == ['ls', '-q']:
    print(os.environ.get('EXISTING', ''))
    if os.environ.get('LS_EXIT'):
        print('daemon unavailable', file=sys.stderr)
        sys.exit(int(os.environ['LS_EXIT']))
elif args[:2] == ['kit', 'validate']:
    sys.exit(int(os.environ.get('VALIDATE_EXIT', '0')))
elif args[0] == 'create':
    # Pre-0.42 sbx resolves custom agents by name from the --kit list.
    agent = next((arg for arg in args if arg in ('claude', 'codex', 'pi')), '')
    kits = [args[i + 1] for i, arg in enumerate(args) if arg == '--kit']
    if agent not in ('claude', 'codex', 'pi') or (agent == 'pi' and not any(
            Path(kit).name == 'pi' for kit in kits)):
        print(f'ERROR: unknown agent "{agent}"', file=sys.stderr)
        sys.exit(2)
    sys.exit(int(os.environ.get('CREATE_EXIT', '0')))
elif args[0] == 'run' or args[:2] in (['exec', '-i'], ['exec', '-it']):
    if os.environ.get('BREAK_TTY'):
        import tty
        tty.setraw(0)
        print('\x1b[?1049h', end='', flush=True)
    sys.exit(int(os.environ.get('RUN_EXIT', '0')))
elif args[0] == 'exec':
    if any('dispatcher' in arg for arg in args):
        sys.exit(int(os.environ.get('STARTUP_EXIT', '0')))
    if 'npm install' in ' '.join(args):
        sys.exit(int(os.environ.get('UPDATE_EXIT', '0')))
    print('1.0.0')

'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        home = self.base / 'home'
        kits = home / 'dotfiles/.sbx/kits'
        kits.parent.mkdir(parents=True)
        kits.symlink_to(ROOT / 'kits', target_is_directory=True)
        self.kits = kits
        self.voice_cache = home / '.cache/sbx/pi-voice'
        model = self.voice_cache / 'whisper-base'
        model.mkdir(parents=True)
        for name in ('base-encoder.int8.onnx', 'base-decoder.int8.onnx',
                     'base-tokens.txt', '.download-complete'):
            (model / name).write_text('fixture')
        binary = self.base / 'sbx'
        binary.write_text(MOCK_SBX)
        binary.chmod(0o755)
        self.calls = self.base / 'calls.jsonl'
        self.project = self.base / 'Project with spaces'
        self.project.mkdir()
        self.env = dict(os.environ, HOME=str(home), CALLS=str(self.calls),
                        PATH=f'{self.base}:{os.environ["PATH"]}')

    def run_launcher(self, agent='pi', *args, **env):
        self.calls.write_text('')
        result = subprocess.run(['bash', str(ROOT / 'sbx-agent'), agent, *args],
                                cwd=self.project, env=dict(self.env, **env),
                                text=True, capture_output=True, timeout=15)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        return result, calls

    def test_all_agents_and_forwarding(self):
        for agent in ('claude', 'codex', 'pi'):
            with self.subTest(agent=agent):
                result, calls = self.run_launcher(agent, '--model', 'a model')
                self.assertEqual(result.returncode, 0, result.stderr)
                create = next(c for c in calls if c[0] == 'create')
                agent_index = create.index(agent)
                if agent == 'pi':
                    index = create.index(str(self.kits / 'pi'))
                    self.assertEqual(create[index - 1], '--kit')
                self.assertEqual(create[agent_index + 1], str(self.project))
                if agent == 'pi':
                    self.assertEqual(create[agent_index + 2:], [str(self.voice_cache) + ':ro'])
                    self.assertIn('SBX_PI_VOICE_CACHE=' + str(self.voice_cache), create)
                else:
                    self.assertEqual(create[agent_index + 2:], [])
                self.assertIn(str(self.kits / 'node-toolchain'), create)
                self.assertIn(str(self.kits / 'skills'), create)
                if agent == 'pi':
                    self.assertEqual(calls[-1], ['exec', '-i', '-w', str(self.project),
                                                create[2], 'pi', '--model', 'a model'])
                else:
                    self.assertEqual(calls[-1], ['run', '--name', create[2],
                                                '--', '--model', 'a model'])
                self.assertTrue(any('dispatcher' in ' '.join(c) for c in calls))

    def test_reuses_existing_without_creation(self):
        _, calls = self.run_launcher()
        name = next(c for c in calls if c[0] == 'create')[2]
        result, calls = self.run_launcher(EXISTING=name)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ('create', 'kit') for c in calls))
        self.assertEqual(calls[-1], ['exec', '-i', '-w', str(self.project), name, 'pi'])

    def test_provisioning_failures_stop_launch(self):
        for stage in ('VALIDATE_EXIT', 'CREATE_EXIT', 'STARTUP_EXIT'):
            with self.subTest(stage=stage):
                result, calls = self.run_launcher(**{stage: '17'})
                self.assertEqual(result.returncode, 17)
                self.assertFalse(any(c[0] == 'run' or c[:2] in
                                     (['exec', '-i'], ['exec', '-it']) for c in calls))

    def test_update_failure_still_launches(self):
        result, calls = self.run_launcher(UPDATE_EXIT='1')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(calls[-1][:2], ['exec', '-i'])
        self.assertIn('Pi update failed', result.stdout)

    def test_run_exit_status_is_preserved(self):
        result, _ = self.run_launcher(RUN_EXIT='23')
        self.assertEqual(result.returncode, 23)
        self.assertIn('pi session exited with status 23', result.stderr)

    def test_daemon_failure_is_visible_and_stops_launch(self):
        result, calls = self.run_launcher(LS_EXIT='19')
        self.assertEqual(result.returncode, 19)
        self.assertEqual(calls, [['ls', '-q']])
        self.assertIn('daemon unavailable', result.stderr)
        self.assertIn('Checking sandbox availability', result.stdout)

    def test_restores_terminal_after_crash(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        before = termios.tcgetattr(slave)
        result = subprocess.run(
            ['bash', str(ROOT / 'sbx-agent'), 'pi'], cwd=self.project,
            env=dict(self.env, BREAK_TTY='1', RUN_EXIT='23'),
            stdin=slave, stdout=slave, stderr=slave, timeout=15)
        self.assertEqual(result.returncode, 23)
        self.assertEqual(termios.tcgetattr(slave), before)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls[-1][:4], ['exec', '-it', '-w', str(self.project)])
        self.assertEqual(calls[-1][-1], 'pi')
        output = os.read(master, 65536)
        self.assertIn(b'\x1b[?1049l', output)
        self.assertIn(b'pi session exited with status 23', output)

    def test_invalid_agent(self):
        result, calls = self.run_launcher('unknown')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
