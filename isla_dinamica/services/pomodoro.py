"""Temporizador Pomodoro."""
import time


class Pomodoro:
    """Ciclo pomodoro (trabajo y descansos) sin interfaz."""
    LABEL = {"work": "Enfoque", "short": "Descanso", "long": "Descanso largo"}

    def __init__(self, config, on_phase_end, on_change):
        self.cfg, self.on_phase_end, self.on_change = config, on_phase_end, on_change
        self.phase, self.running, self.end, self.done, self.active = "work", False, None, 0, False
        self.remaining = self.length("work")

    @property
    def conf(self):
        return self.cfg.data["pomodoro"]

    def length(self, phase):
        return max(1, int(self.conf[phase])) * 60

    def left(self):
        return max(0.0, self.end - time.monotonic()) if self.running else self.remaining

    def start(self):
        if not self.running:
            self.end = time.monotonic() + self.remaining
            self.running = self.active = True
            self.on_change()

    def pause(self):
        if self.running:
            self.remaining = self.left()
            self.running = False
            self.on_change()

    def toggle(self):
        self.pause() if self.running else self.start()

    def reset(self):
        self.phase, self.running, self.done, self.active = "work", False, 0, False
        self.remaining = self.length("work")
        self.on_change()

    def skip(self):
        self._advance(False)

    def tick(self):
        if self.running and time.monotonic() >= self.end:
            self._advance(True)

    def _advance(self, finished):
        prev, was_running = self.phase, self.running
        every = max(1, int(self.conf["every"]))
        if prev == "work":
            self.done += 1
            nxt = "long" if self.done % every == 0 else "short"
        else:
            nxt = "work"
            if prev == "long":
                self.done = 0
        self.phase, self.running = nxt, False
        self.remaining = self.length(nxt)
        if self.conf["auto"] and (finished or was_running):
            self.start()
        if finished:
            self.on_phase_end(prev, nxt)
        self.on_change()

    def set_conf(self, key, value):
        if self.conf.get(key) == value:
            return
        self.conf[key] = value
        self.cfg.save()
        if not self.running and key == self.phase:
            self.remaining = self.length(self.phase)
        self.on_change()

    def cycle_text(self):
        every = max(1, int(self.conf["every"]))
        n = self.done % every + (1 if self.phase == "work" else 0)
        if self.phase == "long":
            n = every
        return f"Sesión {n} de {every}"
