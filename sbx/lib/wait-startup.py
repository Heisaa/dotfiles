"""Wait for this container's dispatcher; never accept an earlier boot's log."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time


# A stale dispatcher record means the container is exec-ready but sandboxd did
# not replay registered startup commands. This is distinct from an ordinary
# startup timeout so the host launcher can recover by invoking the registered
# dispatcher once as root.
STALE_EXIT = 75
STALE_GRACE_SECONDS = 5


def container_started():
    # Field 22 is measured in ticks since boot. Split after the process name,
    # which may itself contain spaces or parentheses.
    fields = Path('/proc/1/stat').read_text().rsplit(')', 1)[1].split()
    ticks = int(fields[19])
    boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                if line.startswith('btime '))
    return int(boot + ticks / os.sysconf('SC_CLK_TCK'))


def state(source, started):
    result = None
    for line in source.splitlines():
        if line.startswith('=== dispatcher run '):
            result = None
            try:
                timestamp = datetime.strptime(line.split()[3], '%Y-%m-%dT%H:%M:%SZ')
                if timestamp.replace(tzinfo=timezone.utc).timestamp() >= started:
                    result = 'running'
            except (ValueError, IndexError):
                pass
        elif result and line.startswith('fail '):
            result = 'failed'
        elif result == 'running' and line == '=== dispatcher complete ===':
            result = 'complete'
    return result


def main():
    log = Path('/var/log/sbx-kit-startup.log')
    started = container_started()
    deadline = time.monotonic() + 600
    stale_deadline = time.monotonic() + STALE_GRACE_SECONDS
    source = ''
    while time.monotonic() < deadline:
        try:
            source = log.read_text()
        except FileNotFoundError:
            source = ''
        current = state(source, started)
        if current == 'complete':
            return
        if current == 'failed':
            break
        # Give sandboxd a short window to append a current run. If the only
        # recognizable record is from an earlier container boot, report a
        # recoverable condition instead of appearing to hang for ten minutes.
        if time.monotonic() >= stale_deadline and state(source, 0) is not None:
            print('Startup dispatcher did not run for the current container start.',
                  file=sys.stderr)
            raise SystemExit(STALE_EXIT)
        time.sleep(2)
    reason = 'Startup kit failed' if state(source, started) == 'failed' else 'Startup kits timed out after 10 minutes'
    print(reason + '; inspect /var/log/sbx-kit-startup.log. Fix the cause and restart or recreate the sandbox.', file=sys.stderr)
    print('\n'.join(source.splitlines()[-40:]), file=sys.stderr)
    raise SystemExit(1)


if __name__ == '__main__':
    main()
