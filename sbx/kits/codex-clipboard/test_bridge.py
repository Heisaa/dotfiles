"""Native X11 integration tests; never read or write the real host clipboard."""

import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import unittest

from Xlib import X, display, protocol

SOURCE = Path(__file__).parent / "files/home/.local/share/sbx/codex-clipboard/bridge.py"
SMALL = b"\x89PNG\r\n\x1a\n" + b"small image"
LARGE = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8192
TEXT = "Clipboard copy: café\n"


def adapter_server(name, ready, writes):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("bridge", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def request(route, body, **kwargs):
        if route == "clipboard-write":
            writes.put(body)
            return b""
        return {"small": SMALL, "large": LARGE, "empty": b""}.get(body["session_id"], b"")

    module.host_request = request
    clipboard = module.Clipboard(display.Display(name))
    ready.set()
    clipboard.run()


def client(name, operation):
    connection = display.Display(name)
    window = connection.screen().root.create_window(
        0, 0, 1, 1, 0, X.CopyFromParent, event_mask=X.PropertyChangeMask,
    )
    atoms = {key: connection.intern_atom(key) for key in (
        "CLIPBOARD", "image/png", "INCR", "TEST", "UTF8_STRING",
    )}
    incremental = False
    data = bytearray()
    pending = None
    if operation == "read":
        window.convert_selection(atoms["CLIPBOARD"], atoms["image/png"], atoms["TEST"], X.CurrentTime)
    else:
        window.set_selection_owner(atoms["CLIPBOARD"], X.CurrentTime)
    connection.flush()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if not connection.pending_events():
            select.select([connection], [], [], .05)
            continue
        event = connection.next_event()
        if operation == "read":
            if event.type == X.SelectionNotify:
                if not event.property:
                    return {"unavailable": True}
                value = window.get_full_property(atoms["TEST"], X.AnyPropertyType)
                incremental = value.property_type == atoms["INCR"]
                if not incremental:
                    data.extend(value.value)
                    break
                window.delete_property(atoms["TEST"])
                connection.flush()
            elif incremental and event.type == X.PropertyNotify and event.state == X.PropertyNewValue:
                value = window.get_full_property(atoms["TEST"], X.AnyPropertyType)
                if value is None or value.property_type == atoms["INCR"]:
                    continue
                data.extend(value.value)
                window.delete_property(atoms["TEST"])
                connection.flush()
                if not len(value.value):
                    break
        elif event.type == X.SelectionRequest:
            payload = (TEXT * (100000 if operation == "copy-large" else 1)).encode()
            prop = event.property or event.target
            if operation == "copy-large":
                event.requestor.change_attributes(event_mask=X.PropertyChangeMask)
                event.requestor.change_property(prop, atoms["INCR"], 32, [len(payload)])
                pending = event.requestor, prop, payload, 0
            else:
                event.requestor.change_property(prop, atoms["UTF8_STRING"], 8, payload)
            event.requestor.send_event(protocol.event.SelectionNotify(
                time=event.time, requestor=event.requestor, selection=event.selection,
                target=event.target, property=prop,
            ))
            connection.flush()
        elif event.type == X.PropertyNotify and event.state == X.PropertyDelete and pending:
            requestor, prop, payload, offset = pending
            chunk = payload[offset:offset + 65536]
            requestor.change_property(prop, atoms["UTF8_STRING"], 8, chunk)
            pending = (requestor, prop, payload, offset + len(chunk)) if chunk else None
            connection.flush()
        elif event.type == X.SelectionClear:
            return {"copied": True}
    else:
        raise RuntimeError("native clipboard transfer timed out")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "incremental": incremental}


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read_fd, write_fd = os.pipe()
        cls.xvfb = subprocess.Popen([
            "Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1x1x24", "-nolisten", "tcp", "-noreset",
        ], pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write_fd)
        with os.fdopen(read_fd) as pipe:
            cls.name = ":" + pipe.readline().strip()
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        cls.writes = context.Queue()
        cls.adapter = context.Process(target=adapter_server, args=(cls.name, ready, cls.writes))
        cls.adapter.start()
        assert ready.wait(5), "adapter did not start"

    @classmethod
    def tearDownClass(cls):
        cls.adapter.terminate()
        cls.adapter.join(5)
        cls.xvfb.terminate()
        cls.xvfb.wait(timeout=5)

    def command(self, session, operation="read"):
        env = dict(os.environ)
        env.pop("SBX_HOST_SESSION_ID", None)
        if session is not None:
            env["SBX_HOST_SESSION_ID"] = session
        return subprocess.Popen([sys.executable, __file__, "--client", self.name, operation],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def result(self, process):
        out, err = process.communicate(timeout=12)
        self.assertEqual(process.returncode, 0, err.decode())
        return json.loads(out)

    def test_small_image(self):
        value = self.result(self.command("small"))
        self.assertEqual(value["sha256"], hashlib.sha256(SMALL).hexdigest())
        self.assertFalse(value["incremental"])

    def test_large_image(self):
        value = self.result(self.command("large"))
        self.assertEqual(value["sha256"], hashlib.sha256(LARGE).hexdigest())
        self.assertTrue(value["incremental"])

    def test_concurrent_host_sessions(self):
        small, large = self.command("small"), self.command("large")
        self.assertEqual(self.result(small)["sha256"], hashlib.sha256(SMALL).hexdigest())
        self.assertEqual(self.result(large)["sha256"], hashlib.sha256(LARGE).hexdigest())

    def test_empty_clipboard(self):
        self.assertEqual(self.result(self.command("empty")), {"unavailable": True})

    def test_missing_session(self):
        self.assertEqual(self.result(self.command(None)), {"unavailable": True})

    def test_native_text_copy(self):
        self.assertEqual(self.result(self.command("small", "copy")), {"copied": True})
        self.assertEqual(self.writes.get(timeout=2), {"session_id": "small", "text": TEXT})
        self.assertEqual(self.result(self.command("large"))["bytes"], len(LARGE))

    def test_native_large_text_copy(self):
        # Drain the queue while the adapter writes; its OS pipe is finite.
        process = self.command("large", "copy-large")
        self.assertEqual(self.writes.get(timeout=10), {"session_id": "large", "text": TEXT * 100000})
        self.assertEqual(self.result(process), {"copied": True})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--client":
        print(json.dumps(client(sys.argv[2], sys.argv[3])))
    else:
        unittest.main()
