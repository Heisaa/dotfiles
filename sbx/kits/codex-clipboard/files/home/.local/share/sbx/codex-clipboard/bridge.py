#!/usr/bin/python3
"""Expose sbx's session-specific host clipboard to native X11 clients.

XRes identifies the requesting process, so each paste uses that process's
SBX_HOST_SESSION_ID, even when the adapter starts before sbx run attaches.
Only image reads and explicit text copies are forwarded to the host.
"""

import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from Xlib import X, Xatom, display, error, protocol
from Xlib.ext import res

CHUNK = 64 * 1024
MAX_IMAGE = 64 * 1024 * 1024
ENDPOINT = "http://gateway.docker.internal:3128/_sbx/"
STATE = Path.home() / ".cache/sbx-codex-clipboard"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def host_request(route, body, limit=MAX_IMAGE):
    request = urllib.request.Request(
        ENDPOINT + route, json.dumps(body).encode(),
        {"Content-Type": "application/json"}, method="POST",
    )
    with HTTP.open(request, timeout=5) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("clipboard data exceeds size limit")
    return data


class Clipboard:
    def __init__(self, connection):
        self.d = connection
        self.d.res_query_version(1, 2)
        self.atoms = {name: self.d.intern_atom(name) for name in (
            "CLIPBOARD", "TARGETS", "image/png", "INCR", "UTF8_STRING",
            "SBX_COPY",
        )}
        self.window = self.d.screen().root.create_window(
            0, 0, 1, 1, 0, X.CopyFromParent,
            event_mask=X.PropertyChangeMask,
        )
        self.transfers = {}
        self.copy = None
        self.claim()

    def claim(self):
        self.window.set_selection_owner(self.atoms["CLIPBOARD"], X.CurrentTime)
        self.d.sync()

    def session(self, window):
        reply = self.d.res_query_client_ids([
            {"client": window.id, "mask": res.LocalClientPIDMask},
        ])
        for item in reply.ids:
            if item.spec.mask & res.LocalClientPIDMask and item.value:
                pid = item.value[0]
                for entry in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
                    if entry.startswith(b"SBX_HOST_SESSION_ID="):
                        value = entry.split(b"=", 1)[1].decode()
                        if value:
                            return value
        raise ValueError("X11 client has no sbx host session")

    def request(self, event):
        prop = event.property or event.target
        result = X.NONE
        try:
            if event.selection != self.atoms["CLIPBOARD"]:
                pass
            elif event.target == self.atoms["TARGETS"]:
                event.requestor.change_property(prop, Xatom.ATOM, 32, [
                    self.atoms["TARGETS"], self.atoms["image/png"],
                ])
                result = prop
            elif event.target == self.atoms["image/png"]:
                data = host_request("clipboard", {
                    "type": "image/png", "session_id": self.session(event.requestor),
                })
                if data.startswith(b"\x89PNG\r\n\x1a\n"):
                    if len(data) <= CHUNK:
                        event.requestor.change_property(prop, event.target, 8, data)
                    else:
                        event.requestor.change_attributes(event_mask=X.PropertyChangeMask)
                        self.transfers[event.requestor.id, prop] = (
                            event.requestor, event.target, data, 0, time.monotonic(),
                        )
                        event.requestor.change_property(prop, self.atoms["INCR"], 32, [len(data)])
                    result = prop
        except (OSError, ValueError, error.XError):
            logging.exception("clipboard read failed")
        event.requestor.send_event(protocol.event.SelectionNotify(
            time=event.time, requestor=event.requestor, selection=event.selection,
            target=event.target, property=result,
        ))
        self.d.flush()

    def property(self, event):
        key = event.window.id, event.atom
        if event.state == X.PropertyDelete and key in self.transfers:
            window, target, data, offset, _ = self.transfers[key]
            chunk = data[offset:offset + CHUNK]
            window.change_property(event.atom, target, 8, chunk)
            if chunk:
                self.transfers[key] = window, target, data, offset + len(chunk), time.monotonic()
            else:
                del self.transfers[key]
            self.d.flush()
        elif (self.copy and self.copy["incremental"]
              and event.window.id == self.window.id
              and event.atom == self.atoms["SBX_COPY"]
              and event.state == X.PropertyNewValue):
            value = self.window.get_full_property(event.atom, X.AnyPropertyType)
            self.window.delete_property(event.atom)
            self.d.flush()
            if value is not None:
                if value.value:
                    self.copy["data"].extend(value.value)
                    if len(self.copy["data"]) > MAX_IMAGE:
                        self.finish_copy(False)
                else:
                    self.finish_copy(True)

    def begin_copy(self):
        # Preserve native /copy: a client taking ownership supplies text that
        # must reach the host before this adapter reclaims the image selection.
        owner = self.d.get_selection_owner(self.atoms["CLIPBOARD"])
        if not owner or owner.id == self.window.id:
            return
        try:
            session = self.session(owner)
        except (OSError, ValueError, error.XError):
            self.claim()
            return
        self.copy = {"session": session, "data": bytearray(),
                     "incremental": False, "deadline": time.monotonic() + 5}
        self.window.convert_selection(self.atoms["CLIPBOARD"],
                                      self.atoms["UTF8_STRING"],
                                      self.atoms["SBX_COPY"], X.CurrentTime)
        self.d.flush()

    def finish_copy(self, success):
        if success:
            try:
                host_request("clipboard-write", {
                    "session_id": self.copy["session"],
                    "text": bytes(self.copy["data"]).decode("utf-8"),
                })
            except (OSError, ValueError):
                logging.exception("clipboard write failed")
        self.copy = None
        self.claim()

    def copied(self, event):
        if not self.copy:
            return
        if event.property == X.NONE:
            self.finish_copy(False)
            return
        value = self.window.get_full_property(event.property, X.AnyPropertyType)
        self.window.delete_property(event.property)
        self.d.flush()
        if value is None:
            self.finish_copy(False)
        elif value.property_type == self.atoms["INCR"]:
            self.copy["incremental"] = True
        elif value.property_type == self.atoms["UTF8_STRING"]:
            self.copy["data"].extend(value.value)
            self.finish_copy(True)
        else:
            self.finish_copy(False)

    def run(self):
        while True:
            while self.d.pending_events():
                event = self.d.next_event()
                try:
                    if event.type == X.SelectionRequest:
                        self.request(event)
                    elif event.type == X.PropertyNotify:
                        self.property(event)
                    elif event.type == X.SelectionClear:
                        self.begin_copy()
                    elif event.type == X.SelectionNotify:
                        self.copied(event)
                except (OSError, ValueError, error.XError):
                    logging.exception("clipboard event failed")
            now = time.monotonic()
            self.transfers = {key: value for key, value in self.transfers.items()
                              if now - value[4] < 10}
            if self.copy and now > self.copy["deadline"]:
                self.finish_copy(False)
            select.select([self.d], [], [], .2)


def serve():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        # Never take over an unrelated display server.
        with socket.socket(socket.AF_UNIX) as probe:
            probe.settimeout(.5)
            try:
                probe.connect("/tmp/.X11-unix/X0")
            except (FileNotFoundError, ConnectionRefusedError):
                pass  # Xvfb handles stale sockets left by an unclean stop.
            else:
                raise RuntimeError("display :0 is already in use")
        server = subprocess.Popen([
            "Xvfb", ":0", "-screen", "0", "1x1x24", "-nolisten", "tcp", "-noreset",
        ], stdin=subprocess.DEVNULL)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Xvfb exited during startup")
                try:
                    connection = display.Display(":0")
                except error.DisplayConnectionError:
                    time.sleep(.05)
                else:
                    break
            else:
                raise RuntimeError("Xvfb did not become ready")
            adapter = Clipboard(connection)
            (STATE / "ready").write_text(str(os.getpid()))
            adapter.run()
        finally:
            (STATE / "ready").unlink(missing_ok=True)
            server.terminate()
            server.wait(timeout=5)


def start():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The daemon lock, not a stale PID file, determines whether it is running.
    running = False
    with (STATE / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            running = True
    process = None
    if not running:
        (STATE / "ready").unlink(missing_ok=True)
        with (STATE / "bridge.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve"],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
    for _ in range(100):
        if (STATE / "ready").exists():
            return
        if process and process.poll() is not None:
            break
        time.sleep(.05)
    raise SystemExit(f"codex-clipboard failed to start; see {STATE / 'bridge.log'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    serve() if args.serve else start()
