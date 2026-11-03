#!/usr/bin/env python3
"""A still of the 3D viewer at one moment of a run, for a paper figure.

    python experiments/capture_3d.py <run_id> --from TICK --who VILLAGER
        [--wait-for TEXT] [--out results/figures/village3d.png] [--size 1600x1000]

Starts its own viewer (``python -m hearthwick view``) on a spare port, so a
viewer already serving the live village is left alone. Opens
``/3d?paper=1&follow=1`` replaying the run from TICK, with VILLAGER selected
and the camera on it, in headless Chrome. Waits until the villager's panel
shows its last decision (and TEXT, when given), then saves a screenshot. The
page hides the name, the run id and the controls (``paper=1``).

The replay runs at its slowest, a tick every four seconds, so the panel still
shows the decision made just before TICK when the picture is taken, and the
picture is checked again afterwards. Chrome draws WebGL in software
(SwiftShader). The first visit to a run reads its whole history, which can
take a few minutes.

Needs Chrome or Chromium, and the websockets package (in the venv). From WSL
it uses Windows' Chrome, which reaches the viewer through WSL's mirrored
networking.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent.parent
CHROMES = ["/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
           "google-chrome", "chromium", "chromium-browser"]


def free_port(first: int, last: int) -> int:
    """A port nothing answers on, from a low range. Under WSL's mirrored
    networking, a port in Linux's dynamic range (32768 and up) is not reached
    across between WSL and Windows, so Chrome's debugging port there was never
    found."""
    for port in range(first, last):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit(f"no free port between {first} and {last}")


def wait_http(url: str, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"{url} did not answer within {seconds:.0f} seconds")


def find_chrome(given: str | None) -> str:
    for c in ([given] if given else CHROMES):
        if c and (Path(c).exists() or shutil.which(c)):
            return c
    raise SystemExit("no Chrome or Chromium found; give one with --chrome")


def profile_dir(chrome: str) -> tuple[Path, str]:
    """A throwaway profile, named as the browser sees it. Windows' Chrome
    gets one in Windows' temp folder: in the repository, under Documents, it
    never opened its debugging port."""
    if chrome.endswith(".exe"):
        temp = subprocess.run(["powershell.exe", "-NoProfile", "-Command", "$env:TEMP"],
                              capture_output=True, text=True, check=True).stdout.strip()
        win = temp + "\\capture3d_profile"
        path = Path(subprocess.run(["wslpath", "-u", win], capture_output=True, text=True,
                                   check=True).stdout.strip())
        return path, win
    path = ROOT / ".capture_profile"
    path.mkdir(exist_ok=True)
    return path, str(path)


class Browser:
    """Headless Chrome. Windows' Chrome started straight from WSL never opened
    its debugging port, so from WSL it is started through PowerShell."""

    def __init__(self, chrome: str, flags: list[str]):
        self.windows = chrome.endswith(".exe")
        if self.windows:
            exe = subprocess.run(["wslpath", "-w", chrome], capture_output=True, text=True,
                                 check=True).stdout.strip()
            quoted = ",".join("'" + f.replace("'", "''") + "'" for f in flags)
            out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                  f"(Start-Process -FilePath '{exe}' -ArgumentList {quoted} "
                                  "-PassThru).Id"], capture_output=True, text=True, check=True)
            self.pid = int(out.stdout.strip().splitlines()[-1])
            self.proc = None
        else:
            self.proc = subprocess.Popen([chrome, *flags], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)

    def stop(self) -> None:
        if self.windows:
            subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                            f"Stop-Process -Id {self.pid} -ErrorAction SilentlyContinue"],
                           capture_output=True)
        elif self.proc is not None:
            self.proc.terminate()


class Page:
    """Just enough of the Chrome DevTools protocol for one page."""

    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=None)
        self.n = 0

    def call(self, method: str, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def text(self, selector: str) -> str:
        r = self.call("Runtime.evaluate", returnByValue=True,
                      expression=f"(document.querySelector({json.dumps(selector)}) || {{}})"
                                 ".innerText || ''")
        return r.get("result", {}).get("value") or ""


def capture(args) -> Path:
    port, debug = free_port(8031, 8099), free_port(9322, 9399)
    viewer = subprocess.Popen([sys.executable, "-m", "hearthwick", "view", "--port", str(port)],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = None
    profile = None
    try:
        wait_http(f"http://127.0.0.1:{port}/", 60)
        chrome = find_chrome(args.chrome)
        profile, profile_arg = profile_dir(chrome)
        width, height = (int(v) for v in args.size.split("x"))
        browser = Browser(chrome, ["--headless=new", f"--remote-debugging-port={debug}",
                                   f"--user-data-dir={profile_arg}", "--use-angle=swiftshader",
                                   "--enable-unsafe-swiftshader", "--hide-scrollbars",
                                   f"--window-size={width},{height}",
                                   f"--force-device-scale-factor={args.scale}", "about:blank"])
        wait_http(f"http://127.0.0.1:{debug}/json/version", 30)
        with urllib.request.urlopen(f"http://127.0.0.1:{debug}/json", timeout=5) as r:
            target = next(t for t in json.load(r) if t.get("type") == "page")
        page = Page(target["webSocketDebuggerUrl"])
        url = (f"http://127.0.0.1:{port}/3d?run={args.run_id}&start=begin&from={args.tick}"
               f"&rate=0.25&who={args.who}&paper=1&follow=1&zoom={args.zoom}&aim={args.aim}")
        wanted = args.wait_for or "Chose"
        for attempt in range(3):
            page.call("Page.navigate", url=url)
            end = time.time() + args.timeout
            while time.time() < end and wanted not in page.text("#detail"):
                time.sleep(0.5)
            if wanted not in page.text("#detail"):
                raise SystemExit(f"the panel never showed {wanted!r} within {args.timeout} s")
            time.sleep(args.settle)               # let the camera reach the villager
            shot = page.call("Page.captureScreenshot", format="png")
            if wanted in page.text("#detail"):    # still the same decision
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_bytes(base64.b64decode(shot["data"]))
                print(f"  {args.out.name}: {args.run_id} from tick {args.tick}, {args.who} "
                      f"selected, {width}x{height}")
                return args.out
            print(f"  the decision moved on during attempt {attempt + 1}; trying again")
        raise SystemExit("could not take the picture before the next decision")
    finally:
        if browser is not None:
            browser.stop()
        viewer.terminate()
        if profile is not None:
            time.sleep(1)
            shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    ap.add_argument("--from", dest="tick", type=int, required=True,
                    help="replay from this tick; the panel shows the decision before it")
    ap.add_argument("--who", required=True, help="the villager to select, by id")
    ap.add_argument("--wait-for", default=None,
                    help="text the panel must show, such as the chosen instruction's id")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "figures" / "village3d.png")
    ap.add_argument("--size", default="1600x1000",
                    help="the page's size in CSS pixels; smaller makes the panel's text "
                         "a larger share of the picture")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="pixels per CSS pixel, for a sharper picture at the same layout")
    ap.add_argument("--zoom", type=float, default=1.0,
                    help="how much closer than the viewer's own camera to start")
    ap.add_argument("--aim", type=float, default=0.0,
                    help="tiles north of the villager to keep the camera on")
    ap.add_argument("--settle", type=float, default=2.5,
                    help="seconds to let the camera reach the villager")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--chrome", default=None)
    capture(ap.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())
