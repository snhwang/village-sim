"""Web server: live village over a websocket, plus replay of saved runs.

Two ways to watch. ``/ws`` runs a village inside the server (``hearthwick
serve``), which is convenient but ends with the server. ``/ws/follow`` watches
a run that lives on its own (``hearthwick run --checkpoint-every``) by reading
its log files as they grow, so the run neither knows nor cares whether anyone is
watching (``hearthwick view``). The 3D viewer at ``/3d`` uses either.

A village run by the server can also be talked to (hearthwick/player.py). A
human is a stranger who picks a villager and talks with it through
``/api/talk/start``, ``/api/talk/say`` and ``/api/talk/end``. While they talk,
the world stands still. While nobody watches, it runs at its idle pace, or
flat out if it has none.

A village meant to live on (``--idle-speed``, ``--checkpoint-every``) saves
itself as it goes and when stopped, and ``--resume`` picks it up again, in the
same log, after a stop or a reboot.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import json
import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from hearthwick.accounts import Accounts
from hearthwick.config import CLIENT_DIR, SimConfig
from hearthwick.designs import Library
from hearthwick.follow import Tail, _record, is_live, reading, roster, snapshot, world_for
from hearthwick.world import World

logger = logging.getLogger(__name__)

# A conversation with a human that has gone quiet this long is ended, so a
# closed browser does not hold the village still for ever.
TALK_TIMEOUT_SECONDS = 300


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    break  # partially written last line of a live run
    return out


class LiveVillage:
    """Runs the simulation in the background and fans ticks out to viewers."""

    def __init__(self, config: SimConfig, speed: float, make_speech: Callable[[SimConfig], Awaitable],
                 idle_speed: float = 0.0, checkpoint_every: float = 0.0,
                 resume: str | None = None, turn_on: list[str] | None = None):
        self.config = config
        self.turn_on = turn_on
        self.speed = speed
        self.idle_speed = idle_speed           # ticks a second while nobody watches; 0 is flat out
        self.checkpoint_days = checkpoint_every or 0.0
        self.checkpoint_ticks = 0
        self.resume = resume
        self.make_speech = make_speech
        self.sim = None
        self.running = True
        self.clients: set[WebSocket] = set()
        self.watchers = 0              # viewers following the run's files
        self.talk_token: str | None = None
        self.talk_seen = 0.0
        self._stopping = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        from hearthwick import checkpoint
        from hearthwick.sim import Simulation

        speech = await self.make_speech(self.config)
        self.sim = Simulation(self.config, speech)
        self.checkpoint_ticks = int(self.checkpoint_days * self.sim.clock.ticks_per_day)
        if self.resume:
            # The village it was, carried on in its own log.
            path = checkpoint.find(self.config.runs_dir, self.resume)
            self.sim.log.adopt(self.config.runs_dir / self.resume, self.turn_on)
            tick = self.sim.resume_from(path)
            logger.info("resumed %s at tick %d", self.resume, tick)
        else:
            self.sim.log.meta["plan"] = {"serve": True, "checkpoint_every": self.checkpoint_days}
            self.sim.log.write_meta()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Finish the tick in progress and, for a village that checkpoints,
        save it, so stopping on purpose loses nothing."""
        self._stopping = True
        if self._task:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self.sim:
            if self.sim.players.talking:
                await self.end_talk()
            if self.checkpoint_ticks:
                await self.sim.save()
            self.sim.close()

    async def _loop(self) -> None:
        while not self._stopping:
            started = asyncio.get_running_loop().time()
            if self.sim.players.talking:
                await self._frozen()
                continue
            if self.running:
                try:
                    frame = await self.sim.step()
                except Exception:
                    logger.exception("Simulation step failed; pausing")
                    self.running = False
                    continue
                await self.broadcast({"type": "tick", "frame": frame, "events": self.sim.log.drain(),
                                      "running": self.running, "speed": self.speed})
                if self.checkpoint_ticks and self.sim.clock.tick % self.checkpoint_ticks == 0:
                    await self.sim.save()
            else:
                # Speech lines can still arrive while paused.
                events = self.sim.log.drain()
                if events:
                    await self.broadcast({"type": "events", "events": events})
            # A watchable pace while anyone watches, and otherwise the idle
            # pace, which leaves the machine and the model to other work.
            watched = self.clients or self.watchers
            pace = max(self.speed, 0.1) if watched else self.idle_speed
            delay = 1.0 / pace if pace > 0 else 0.0
            await asyncio.sleep(max(0.0, delay - (asyncio.get_running_loop().time() - started)))

    async def _frozen(self) -> None:
        """The world stands still while a human talks with a villager. The
        lines still reach the log and the viewers, and the frames file is kept
        fresh so a viewer does not take a long conversation for the run's end."""
        loop = asyncio.get_running_loop()
        if loop.time() - self.talk_seen > TALK_TIMEOUT_SECONDS:
            await self.end_talk()
            return
        self.sim.log.flush()
        with contextlib.suppress(OSError):
            os.utime(self.sim.log.dir / "frames.jsonl")
        events = self.sim.log.drain()
        if events:
            await self.broadcast({"type": "events", "events": events})
        await asyncio.sleep(0.25)

    def begin_talk(self, villager: str, name: str | None = None) -> dict:
        players = self.sim.players
        reason = players.refusal(villager)
        if reason:
            raise ValueError(reason)
        conv = players.begin(villager, name)
        self.talk_token = secrets.token_hex(8)
        self.talk_seen = asyncio.get_running_loop().time()
        self.sim.log.flush()
        return {"token": self.talk_token, "villager": villager,
                "name": self.sim.characters[villager].name, "conversation": conv.id}

    async def say(self, text: str) -> dict:
        self.talk_seen = asyncio.get_running_loop().time()
        reply = await self.sim.players.say(text)
        self.talk_seen = asyncio.get_running_loop().time()
        self.sim.log.flush()
        return {"reply": reply}

    async def end_talk(self) -> dict:
        self.talk_token = None
        result = await self.sim.players.end()
        self.sim.log.flush()
        return result

    async def broadcast(self, message: dict) -> None:
        if not self.clients:
            return
        text = json.dumps(message, ensure_ascii=False)
        dead = []
        for ws in self.clients:
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001 - drop broken connections
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def hello(self) -> dict:
        sim = self.sim
        return {
            "type": "hello",
            "run_id": sim.log.run_id,
            "meta": sim.log.meta,
            "clock": sim.clock.to_dict(),
            "frame": sim.last_frame,
            "roster": [c.profile() for c in sim.characters.values()],
            "decisions": sim.decisions,
            "recent": sim.log.recent[-300:],
            "running": self.running,
            "speed": self.speed,
        }


def create_app(config: SimConfig, live: bool, speed: float,
               make_speech: Callable[[SimConfig], Awaitable], idle_speed: float = 0.0,
               checkpoint_every: float = 0.0, resume: str | None = None,
               turn_on: list[str] | None = None) -> FastAPI:
    village = (LiveVillage(config, speed, make_speech, idle_speed, checkpoint_every, resume,
                           turn_on) if live else None)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if village:
            await village.start()
            # Read the run's log once now, on a worker thread, so the first
            # viewer to arrive does not wait for it.
            run_dir = getattr(getattr(village, "sim", None), "log", None)
            if run_dir is not None:
                asyncio.get_running_loop().run_in_executor(None, _record, run_dir.dir)
        yield
        if village:
            await village.stop()

    app = FastAPI(title="Hearthwick", lifespan=lifespan)
    app.state.village = village
    runs_dir = config.runs_dir
    # The designs the 3D viewer draws the village's places from
    # (hearthwick/designs.py). They are drawings, so a replay of any run,
    # however old, gets them too.
    library = Library.load(config.data_dir)

    def drawn(world) -> dict:
        """The world with the designs it is drawn from."""
        return {**world.to_dict(), **library.payload()}

    @app.get("/api/world")
    def world():
        w = village.sim.world if village else World.from_yaml(config.data_dir / "world" / "village.yaml")
        return drawn(w)

    @app.get("/api/live")
    def live_status():
        if not village or not village.sim:
            return {"live": False}
        talk = village.sim.players.talk
        return {"live": True, "run_id": village.sim.log.run_id,
                "talking_with": talk.villager if talk else None}

    @app.get("/api/loading")
    def loading(run: str = "latest"):
        """How much of a run's log has been read for viewers (hearthwick/
        follow.py), so a viewer waiting for its hello can show how far along
        it is. The first read after a restart takes two or three minutes."""
        d = _latest_dir() if run == "latest" else _run_dir(run)
        read, size = reading(d)
        return {"run_id": d.name, "read": read, "size": size}

    def _talk_open(body: dict) -> None:
        if not village or not village.sim:
            raise HTTPException(409, "there is no live village to talk to")
        if not village.sim.players.talking or body.get("token") != village.talk_token:
            raise HTTPException(409, "that conversation is not open")

    # What the villagers call each visitor, kept against its account.
    accounts = Accounts(config.runs_dir / "accounts.json")

    @app.get("/api/me")
    def me(request: Request):
        key = accounts.key(request.headers)
        return {"name": accounts.name_of(key), "known": key is not None}

    @app.post("/api/me")
    def set_me(body: dict, request: Request):
        key = accounts.key(request.headers)
        if key is None:
            raise HTTPException(400, "this page could not say who you are")
        name = " ".join(str(body.get("name", "")).split())
        taken = {c.name for c in village.sim.characters.values()} if village and village.sim else set()
        reason = accounts.refusal(name, taken)
        if reason:
            raise HTTPException(400, reason)
        accounts.set(key, name)
        return {"name": name}

    @app.post("/api/talk/start")
    async def talk_start(body: dict, request: Request):
        if not village or not village.sim:
            raise HTTPException(409, "there is no live village to talk to")
        try:
            return village.begin_talk(str(body.get("villager", "")),
                                      accounts.name_of(accounts.key(request.headers)))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/talk/say")
    async def talk_say(body: dict):
        _talk_open(body)
        text = str(body.get("text", ""))[:500]
        return await village.say(text)

    @app.post("/api/talk/end")
    async def talk_end(body: dict):
        _talk_open(body)
        return await village.end_talk()

    @app.get("/api/runs")
    def runs():
        out = []
        if runs_dir.exists():
            for d in sorted(runs_dir.iterdir(), reverse=True):
                meta = d / "meta.json"
                if meta.exists():
                    m = json.loads(meta.read_text(encoding="utf-8"))
                    out.append({"run_id": d.name, "started": m.get("started"),
                                "finished": m.get("finished"), "ticks": m.get("ticks"),
                                "speech_model": m.get("speech_model"),
                                "village": (m.get("config") or {}).get("village"),
                                "live": is_live(d)})
        return out

    def _run_dir(run_id: str) -> Path:
        d = (runs_dir / run_id).resolve()
        if d.parent != runs_dir.resolve() or not d.is_dir():
            raise HTTPException(404, "run not found")
        return d

    def _latest_dir() -> Path:
        """The run being written to now, or else the newest one."""
        dirs = [d for d in runs_dir.iterdir() if (d / "frames.jsonl").exists()]             if runs_dir.exists() else []
        if not dirs:
            raise HTTPException(404, "no runs yet")
        live = [d for d in dirs if is_live(d)]
        return max(live or dirs, key=lambda d: (d / "frames.jsonl").stat().st_mtime)

    @app.get("/api/runs/{run_id}/world")
    def run_world(run_id: str):
        d = _latest_dir() if run_id == "latest" else _run_dir(run_id)
        return drawn(world_for(d, config.data_dir), d)

    @app.get("/api/runs/{run_id}")
    def run_data(run_id: str):
        d = _run_dir(run_id)
        return JSONResponse({
            "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")),
            "frames": _read_jsonl(d / "frames.jsonl"),
            "events": _read_jsonl(d / "events.jsonl"),
        })

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        if not village or not village.sim:
            await websocket.send_text(json.dumps({"type": "no_live"}))
            await websocket.close()
            return
        village.clients.add(websocket)
        await websocket.send_text(json.dumps(village.hello(), ensure_ascii=False))
        try:
            while True:
                msg = json.loads(await websocket.receive_text())
                cmd = msg.get("cmd")
                if cmd == "pause":
                    village.running = False
                elif cmd == "resume":
                    village.running = True
                elif cmd == "speed":
                    village.speed = max(0.25, min(60.0, float(msg.get("value", 2))))
                await village.broadcast({"type": "control", "running": village.running,
                                         "speed": village.speed})
        except (WebSocketDisconnect, json.JSONDecodeError, ValueError):
            pass
        finally:
            village.clients.discard(websocket)

    @app.websocket("/ws/follow")
    async def follow(websocket: WebSocket):
        """Stream a run from its log files: the live end, or a replay from the start.

        Query: ``run`` (an id, or ``latest``), ``start`` (``live`` or ``begin``),
        ``rate`` (ticks a second while replaying) and ``from`` (a tick to skip
        ahead to when replaying). The viewer can send
        ``{"cmd": "rate", "value": n}`` and ``{"cmd": "live"}``.
        """
        await websocket.accept()
        q = websocket.query_params
        if village:
            village.watchers += 1
        try:
            await _follow(websocket, q)
        finally:
            if village:
                village.watchers -= 1

    async def _follow(websocket: WebSocket, q) -> None:
        try:
            run = q.get("run") or "latest"
            d = _latest_dir() if run == "latest" else _run_dir(run)
        except HTTPException as exc:
            await websocket.send_text(json.dumps({"type": "error", "detail": exc.detail}))
            await websocket.close()
            return
        start = q.get("start", "live")
        skip_to = int(q.get("from", 0) or 0) if start == "begin" else 0
        state = {"rate": max(0.25, min(240.0, float(q.get("rate", 4) or 4))), "jump": False}

        def greeting() -> dict:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            hello = {"type": "hello", "mode": "follow", "run_id": d.name, "meta": meta,
                     "world": drawn(world_for(d, config.data_dir, grown=start != "begin")),
                     "roster": roster(d),
                     "live": is_live(d), "start": start, "rate": state["rate"]}
            if start == "begin":
                hello.update(frame=None, weather="clear", decisions={}, recent=[])
            else:
                hello.update(snapshot(d))
            return hello

        # Read off the event loop, which the live village steps on: the
        # first read of a long log takes a minute or more.
        hello = await asyncio.to_thread(greeting)
        frames, events = Tail(d / "frames.jsonl"), Tail(d / "events.jsonl")
        if start != "begin":
            frames.at_end()
            events.at_end()
        await websocket.send_text(json.dumps(hello, ensure_ascii=False))

        async def listen():
            while True:
                msg = json.loads(await websocket.receive_text())
                if msg.get("cmd") == "rate":
                    state["rate"] = max(0.25, min(240.0, float(msg.get("value", 4))))
                elif msg.get("cmd") == "live":
                    state["jump"] = True

        listener = asyncio.create_task(listen())
        queue: collections.deque = collections.deque()
        pending: list[dict] = []
        ended = False
        try:
            while not listener.done():
                if state["jump"]:
                    state["jump"] = False
                    queue.clear()
                    pending.clear()
                    frames.at_end()
                    events.at_end()
                    snap = snapshot(d)
                    await websocket.send_text(json.dumps({"type": "jumped", **snap},
                                                         ensure_ascii=False))
                if len(queue) < 64:
                    queue.extend(frames.read(1 << 18))
                if not queue:
                    if not ended and not is_live(d):
                        ended = True
                        await websocket.send_text(json.dumps({"type": "end"}))
                    await asyncio.sleep(0.25 if not ended else 1.0)
                    continue
                ended = False
                frame = queue.popleft()
                if not pending or pending[-1].get("t", 0) <= frame["t"]:
                    pending.extend(events.read(1 << 18))
                due = [e for e in pending if e.get("t", 0) <= frame["t"]]
                pending = [e for e in pending if e.get("t", 0) > frame["t"]]
                if frame["t"] < skip_to - 1:
                    continue            # skipping ahead: no pacing, nothing sent
                await websocket.send_text(json.dumps(
                    {"type": "tick", "frame": frame, "events": due,
                     "live": is_live(d), "rate": state["rate"]}, ensure_ascii=False))
                # Behind the end of the file: replaying, so pace it. At the end
                # of a live run, frames arrive at the simulation's own pace.
                if queue or start == "begin" and not is_live(d):
                    await asyncio.sleep(1.0 / state["rate"])
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await listener

    @app.get("/3d")
    def village3d():
        return FileResponse(CLIENT_DIR / "village3d.html")

    @app.get("/")
    def index():
        return FileResponse(CLIENT_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")
    return app
