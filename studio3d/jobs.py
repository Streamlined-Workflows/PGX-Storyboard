"""Providers, the queue and its locks (3d_Generation_Plan Phases 19, 20 and 21).

A *provider* is something that can do one or more named jobs (capabilities): a local AI model behind an adapter, or
a deterministic tool that is part of the application. The registry knows what each can do and whether it may be
chosen. Today every provider is deterministic: no geometry, texture or landmark model has been set up, so those
capabilities are listed as unavailable and nothing pretends otherwise.

A *request* is one thing the person asked for. The ledger keeps every request on disk and decides what may be
admitted and what runs next:

  admission   a request may carry a lock scope ("geometry" for the whole machine, or one asset's workflow). While a
              request holding a scope is unfinished, a different request for the same scope is refused and is not
              queued. Sending the same request again (same key) returns the one already there.
  one at a time   a single worker runs requests one after another, so there is never more than one inference job and
              heavy work (conversion, packaging) never overlaps generation.
  order       the oldest eligible request goes first; while requests remain that use the model already loaded, they
              go next in the order they were sent, before the model is changed (Phase 21, 21.4).
  stopping    a waiting request is cancelled at once. A running one is asked to stop; if it does not, the ledger
              waits for the person to confirm a forced stop and keeps the slot until the work has really ended.
  restart     requests that were running when the application stopped become Interrupted and wait for an explicit
              retry; ones that had not started stay waiting.

A request's outcome says nothing about approval: finishing a job never approves what it made.
"""
import json
import os
import threading
import time
import uuid

ACTIVE = ("waiting", "running", "cancelling", "awaiting force-stop confirmation")
TERMINAL = ("succeeded", "partially succeeded", "failed", "cancelled", "interrupted")
FAILURES = ("unsupported", "unavailable", "invalid input", "resource unavailable", "failed", "cancelled")
KEEP_FINISHED = 10 * 24 * 3600
GRACE = 20.0                                # seconds a running job is given to stop before the person is asked

# Every capability the design names for the studio, so the page can say plainly which have nothing behind them yet.
CAPABILITIES = {
    "geometry.import": ("Import and measure FBX geometry", "deterministic"),
    "package.export": ("Package an asset as a SWIFT ZIP", "deterministic"),
    "package.import": ("Validate and reimport a SWIFT ZIP", "deterministic"),
    "character.inspect": ("Check a character's preparation", "deterministic"),
    "geometry.generate": ("Generate geometry from reference pictures", "ai"),
    "geometry.optimize": ("Reduce, remesh, retopologise or subdivide geometry", "ai or deterministic"),
    "geometry.segment": ("Split a mesh into components", "ai or deterministic"),
    "geometry.convert": ("Convert, normalise or rewrite FBX", "deterministic"),
    "uv.unwrap": ("Unwrap and pack UVs", "deterministic"),
    "texture.generate": ("Generate texture maps", "ai"),
    "texture.bake": ("Bake and transfer texture maps", "deterministic"),
    "character.pose": ("Convert between A-pose and T-pose", "ai or deterministic"),
    "character.weights": ("Transfer skin weights", "deterministic"),
    "character.landmarks": ("Place the 218 body landmarks", "ai"),
}


class Refused(ValueError):
    """A request was not admitted. `.kind` is one of FAILURES or "locked"; the message is for the person."""
    def __init__(self, kind, message, request=None):
        super().__init__(message)
        self.kind, self.request = kind, request


class Provider:
    def __init__(self, pid, name, version, capabilities, run, kind="deterministic", model=None, enabled=True, qualified=True, rank=0, kill=None, limits=""):
        self.id, self.name, self.version, self.capabilities, self.run = pid, name, version, tuple(capabilities), run
        self.kind, self.model, self.enabled, self.qualified, self.rank, self.kill, self.limits = kind, model, enabled, qualified, rank, kill, limits

    def describe(self):
        return {"id": self.id, "name": self.name, "version": self.version, "kind": self.kind, "capabilities": list(self.capabilities), "enabled": self.enabled,
                "qualified": self.qualified, "local": True, "limits": self.limits, "can_be_force_stopped": bool(self.kill)}


class Registry:
    def __init__(self):
        self.providers = {}

    def register(self, provider):
        self.providers[provider.id] = provider          # one enabled version per provider: registering again replaces it (Q19-03)
        return provider

    def select(self, capability, override=None):
        """The provider for a capability. Auto takes the best-ranked one that is enabled and has passed a real test on
        this machine; an override may pick another that can do the job, and is refused if it cannot (Phase 19)."""
        if capability not in CAPABILITIES:
            raise Refused("unsupported", "The studio has no such operation.")
        able = [p for p in self.providers.values() if capability in p.capabilities]
        if override:
            p = self.providers.get(override)
            if not p or capability not in p.capabilities:
                raise Refused("unsupported", f"{p.name if p else 'That provider'} cannot do this: {CAPABILITIES[capability][0].lower()}.")
            if not p.enabled:
                raise Refused("unavailable", f"{p.name} is switched off.")
            return p
        ready = sorted((p for p in able if p.enabled and p.qualified), key=lambda p: -p.rank)
        if ready:
            return ready[0]
        if able:
            raise Refused("unavailable", f"Nothing able to do this is ready: {', '.join(p.name + (' is switched off' if not p.enabled else ' has not passed a test on this machine') for p in able)}.")
        raise Refused("unavailable", f"No provider is set up for this yet: {CAPABILITIES[capability][0].lower()}.")

    def table(self):
        out = []
        for cap, (label, kind) in CAPABILITIES.items():
            able = [p for p in self.providers.values() if cap in p.capabilities]
            try:
                chosen, why = self.select(cap).id, ""
            except Refused as e:
                chosen, why = None, str(e)
            out.append({"capability": cap, "label": label, "kind": kind, "providers": [p.id for p in able], "auto": chosen, "available": chosen is not None, "reason": why})
        return out


class Context:
    def __init__(self, request, stopping):
        self.request, self._stopping = request, stopping

    def cancelled(self):
        return self._stopping.is_set()


class Ledger:
    def __init__(self, root, registry, clock=time.time):
        self.path, self.registry, self.clock = os.path.join(root, "ledger.json"), registry, clock
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = {}                    # request id -> the event that asks it to stop
        self.loaded = None                    # the model of the last inference job, for the ordering rule
        self.requests = []
        try:
            with open(self.path, encoding="utf-8") as f:
                self.requests = json.load(f)
        except (OSError, ValueError):
            self.requests = []
        self.reconcile()

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.requests, f)
        os.replace(tmp, self.path)

    def reconcile(self):
        """After a restart: anything that had started cannot be trusted to have finished, so it is marked Interrupted and
        waits for an explicit retry. Nothing is rerun by itself. Work that had not started stays waiting."""
        with self.lock:
            now = self.clock()
            for r in self.requests:
                if r["state"] in ("running", "cancelling", "awaiting force-stop confirmation"):
                    r.update(state="interrupted", ended=now, error={"class": "failed", "message": "The application stopped while this was running. Nothing was published. Retry it when ready."})
            self.requests = [r for r in self.requests if r["state"] in ACTIVE or now - (r.get("ended") or now) < KEEP_FINISHED]
            self._save()

    # ---- admission ----
    def submit(self, operation, payload, key=None, scope=None, asset=None, project=None, override=None, label=""):
        """Admit a request, or refuse it with the reason. The same key returns the request already there."""
        with self.lock:
            if key:
                same = next((r for r in self.requests if r.get("key") == key and r["state"] in ACTIVE), None)
                if same:
                    return same
            provider = self.registry.select(operation, override)
            if scope:
                holder = next((r for r in self.requests if r.get("scope") == scope and r["state"] in ACTIVE), None)
                if holder:
                    raise Refused("locked", f"{holder['label'] or CAPABILITIES[holder['operation']][0]} is still {'waiting to run' if holder['state'] == 'waiting' else 'running'}. Another one cannot be sent until it has finished.", holder)
            r = {"id": "req_" + uuid.uuid4().hex[:16], "key": key, "operation": operation, "label": label or CAPABILITIES[operation][0], "scope": scope, "asset": asset, "project": project,
                 "provider": provider.id, "provider_name": provider.name, "provider_version": provider.version, "kind": provider.kind, "model": provider.model,
                 "state": "waiting", "stage": "Waiting to run", "blocker": "", "created": self.clock(), "started": None, "ended": None, "error": None, "result": None, "payload": payload}
            self.requests.append(r)
            self._save()
            self.wake.set()
            return r

    def get(self, rid):
        with self.lock:
            r = next((r for r in self.requests if r["id"] == rid), None)
        if not r:
            raise LookupError("That request is no longer in the queue.")
        return r

    def listing(self, project=None):
        with self.lock:
            order = self.order()
            out = []
            for r in self.requests:
                if project and r.get("project") not in (None, project):
                    continue
                view = {k: r[k] for k in ("id", "operation", "label", "scope", "asset", "provider_name", "provider_version", "kind", "state", "stage", "blocker", "created", "started", "ended", "error", "result")}
                view["position"] = order.index(r["id"]) + 1 if r["id"] in order else None
                out.append(view)
            return out

    def locked(self, scope):
        with self.lock:
            return next((r for r in self.requests if r.get("scope") == scope and r["state"] in ACTIVE), None)

    # ---- order ----
    def order(self):
        """The ids of waiting requests in the order they will run: oldest first, except that requests using the model
        already loaded go ahead of a change of model, in the order they were sent."""
        with self.lock:
            waiting = sorted((r for r in self.requests if r["state"] == "waiting" and self.registry.providers.get(r["provider"])), key=lambda r: r["created"])
            out, loaded = [], self.loaded
            while waiting:
                same = [r for r in waiting if r["kind"] == "ai" and r["model"] and r["model"] == loaded]
                nxt = same[0] if same else waiting[0]
                if nxt["kind"] == "ai":
                    loaded = nxt["model"]
                out.append(nxt["id"])
                waiting.remove(nxt)
            return out

    # ---- running ----
    def run_next(self):
        """Run the next waiting request to its end. -> the request, or None if nothing was waiting."""
        with self.lock:
            if any(r["state"] in ("running", "cancelling", "awaiting force-stop confirmation") for r in self.requests):
                return None                                   # the slot is held until the last job has really ended
            order = self.order()
            if not order:
                return None
            r = self.get(order[0])
            provider = self.registry.providers[r["provider"]]
            if provider.version != r["provider_version"] or not provider.enabled:
                r.update(state="failed", ended=self.clock(), stage="", error={"class": "unavailable", "message": f"{provider.name} was changed or switched off after this was sent. Send it again."})
                self._save()
                return r
            stop = self.stopping[r["id"]] = threading.Event()
            r.update(state="running", started=self.clock(), stage="Running")
            if provider.kind == "ai":
                self.loaded = provider.model
            self._save()
        try:
            result = provider.run(r, Context(r, stop))
            outcome = {"state": "cancelled" if stop.is_set() and result is None else "partially succeeded" if isinstance(result, dict) and result.get("partial") else "succeeded", "result": result, "error": None}
            if outcome["state"] == "cancelled":
                outcome["error"] = {"class": "cancelled", "message": "Cancelled."}
        except Refused as e:
            outcome = {"state": "failed", "result": None, "error": {"class": e.kind, "message": str(e)}}
        except (ValueError, LookupError, OSError) as e:
            outcome = {"state": "failed", "result": None, "error": {"class": "invalid input" if isinstance(e, ValueError) else "failed", "message": str(e) or "It failed."}}
        except Exception as e:                                # a provider's own fault is contained to its request
            outcome = {"state": "failed", "result": None, "error": {"class": "failed", "message": f"The provider failed ({type(e).__name__})."}}
        with self.lock:
            if stop.is_set() and outcome["state"] in ("succeeded", "partially succeeded"):
                outcome = {"state": "cancelled", "result": None, "error": {"class": "cancelled", "message": "Cancelled. What arrived afterwards was discarded."}, "late": outcome["result"]}
            r.update(state=outcome["state"], result=outcome["result"], error=outcome["error"], ended=self.clock(), stage="")
            self.stopping.pop(r["id"], None)
            self._save()
        if outcome.get("late") and provider.capabilities and getattr(provider, "discard", None):
            provider.discard(outcome["late"])
        return r

    def run_pending(self, limit=100):
        done = []
        while len(done) < limit:
            r = self.run_next()
            if not r:
                break
            done.append(r)
        return done

    def stage(self, rid, text):
        with self.lock:
            r = self.get(rid)
            if r["state"] == "running":
                r["stage"] = text[:120]

    # ---- stopping ----
    def cancel(self, rid):
        with self.lock:
            r = self.get(rid)
            if r["state"] == "waiting":
                r.update(state="cancelled", ended=self.clock(), stage="", error={"class": "cancelled", "message": "Cancelled before it started."})
            elif r["state"] == "running":
                r.update(state="cancelling", stage="Asked to stop", cancel_asked=self.clock())
                self.stopping[rid].set()
            self._save()
            return r

    def check_stops(self):
        """A job that was asked to stop and has not: after a grace period the person is asked whether to force it."""
        with self.lock:
            for r in self.requests:
                if r["state"] == "cancelling" and self.clock() - r.get("cancel_asked", 0) > GRACE:
                    r.update(state="awaiting force-stop confirmation", stage="Did not stop when asked")
            self._save()

    def force(self, rid, confirmed):
        """The person's answer about forcing a stop. Declining forces nothing. Forcing is only possible for a provider
        that runs apart from the application; either way the slot stays held until the work has really ended."""
        with self.lock:
            r = self.get(rid)
            if r["state"] != "awaiting force-stop confirmation":
                return r
            provider = self.registry.providers.get(r["provider"])
            if not confirmed:
                r["stage"] = "Still stopping; a forced stop was declined"
            elif provider and provider.kill:
                r["stage"] = "Forced stop requested"
                self._save()
                provider.kill(r)
            else:
                r["stage"] = "This kind of job cannot be force-stopped; waiting for it to end"
            self._save()
            return r

    def retry(self, rid):
        """Send a failed or interrupted request again, as a new request with the same inputs."""
        with self.lock:
            r = self.get(rid)
            if r["state"] not in ("failed", "interrupted", "cancelled"):
                raise Refused("invalid input", "Only a failed, cancelled or interrupted request can be retried.")
            return self.submit(r["operation"], r["payload"], key=None, scope=r["scope"], asset=r["asset"], project=r["project"], label=r["label"])

    def forget(self, asset=None, artifacts=()):
        """Drop finished requests that belong to an asset or produced artifacts that have been deleted, so a deleted
        generation leaves no history behind (Phase 22, AVP-005)."""
        gone = set(artifacts)
        with self.lock:
            keep = []
            for r in self.requests:
                made = set((r.get("result") or {}).get("artifacts", [])) if isinstance(r.get("result"), dict) else set()
                if r["state"] in TERMINAL and ((asset and r.get("asset") == asset and not artifacts) or (made and made <= gone)):
                    continue
                keep.append(r)
            self.requests = keep
            self._save()

    # ---- the worker ----
    def start(self):
        def loop():
            while True:
                self.wake.wait(timeout=5)
                self.wake.clear()
                try:
                    self.check_stops()
                    self.run_pending()
                except Exception:
                    time.sleep(1)
        threading.Thread(target=loop, daemon=True, name="studio3d-queue").start()
