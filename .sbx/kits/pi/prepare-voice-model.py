#!/usr/bin/env python3
"""Prepare the shared host cache; print its absolute path for the launcher."""
import fcntl
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


URL = ('https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'
       'sherpa-onnx-whisper-base.tar.bz2')
FILES = ('base-encoder.int8.onnx', 'base-decoder.int8.onnx', 'base-tokens.txt')


def complete(model):
    return (model / '.download-complete').is_file() and all(
        (model / name).is_file() and (model / name).stat().st_size > 0 for name in FILES)


def prepare(cache):
    cache = cache.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    model = cache / 'whisper-base'
    # flock is released even if the process crashes; concurrent launches wait.
    with (cache / '.download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if complete(model):
            return cache
        print('Preparing shared Pi voice model (~198 MB download)…', file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix='.download-', dir=cache) as tmp:
            staging = Path(tmp)
            archive = staging / 'model.tar.bz2'
            subprocess.run(['curl', '--fail', '--location', '--show-error',
                            '--retry', '3', '--connect-timeout', '30',
                            '--max-time', '600', '--output', str(archive), URL], check=True)
            extracted = staging / 'whisper-base'
            extracted.mkdir(mode=0o755)
            # Copy only the required regular files, never archive paths or symlinks.
            wanted = {'sherpa-onnx-whisper-base/' + name: name for name in FILES}
            found = set()
            with tarfile.open(archive, 'r|bz2') as tar:
                for member in tar:
                    name = wanted.get(member.name)
                    if name is None:
                        continue
                    if not member.isfile() or member.size <= 0:
                        raise ValueError('Invalid voice model file: ' + name)
                    with tar.extractfile(member) as source, (extracted / name).open('wb') as dest:
                        shutil.copyfileobj(source, dest)
                    (extracted / name).chmod(0o644)
                    found.add(name)
            if found != set(FILES):
                raise ValueError('Voice model archive is missing required files')
            (extracted / '.download-complete').touch(mode=0o644)
            # Publish only a complete model. Keep old files until extraction succeeds.
            if model.exists() or model.is_symlink():
                model.rename(staging / 'previous')
            extracted.rename(model)
    return cache


if __name__ == '__main__':
    try:
        print(prepare(Path.home() / '.cache/sbx/pi-voice'))
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        sys.exit('Could not prepare shared Pi voice model: ' + str(exc))
