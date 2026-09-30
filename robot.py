"""Lógica do Working Time Robo: fases, bateria e humor. Sem nada de Pygame."""

FOCUS = "focus"
BREAK = "break"

# eventos devolvidos por tick()/toggle()/skip()
FOCUS_DONE = "focus_done"
BREAK_DONE = "break_done"
BREAK_BEGUN = "break_begun"
FOCUS_BEGUN = "focus_begun"

FULL_BATTERY = 100.0
MIN_BATTERY = 12.0       # o robô nunca chega a 0: só fica superaquecido

# humores, do mais descansado ao mais sobrecarregado
FRESH = "fresh"
WORKING = "working"
WARM = "warm"
OVERHEATED = "overheated"
CHARGING = "charging"


def format_time(seconds):
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class RobotTimer:
    """Timer de foco/pausa em que a bateria descarrega no foco e recarrega na pausa.

    Ao terminar uma fase o timer troca para a próxima e fica *esperando*: a
    fase só começa quando o usuário confirma (toggle), porque a pausa é manual.
    """

    def __init__(self, focus_secs=25 * 60, break_secs=5 * 60):
        self.focus_secs = focus_secs
        self.break_secs = break_secs
        self.reset()

    def reset(self):
        self.phase = FOCUS
        self.elapsed = 0.0
        self.running = False
        self.waiting = False
        self.battery = FULL_BATTERY
        self.cycles = 0
        self.cap = None     # teto (s) para a fase atual, ex.: até o almoço
        self._battery_at_start = FULL_BATTERY

    def new_block(self):
        """Volta a um foco zerado e descansado; mantém a contagem de ciclos."""
        self.phase = FOCUS
        self.elapsed = 0.0
        self.running = False
        self.waiting = False
        self.battery = FULL_BATTERY
        self.cap = None
        self._battery_at_start = FULL_BATTERY

    # --- estado derivado ---
    @property
    def duration(self):
        base = self.focus_secs if self.phase == FOCUS else self.break_secs
        return min(base, self.cap) if self.cap else base

    @property
    def remaining(self):
        return max(0.0, self.duration - self.elapsed)

    @property
    def progress(self):
        return min(1.0, self.elapsed / self.duration) if self.duration else 1.0

    @property
    def heat(self):
        """0 = frio, 1 = superaquecido."""
        return min(1.0, max(0.0, (FULL_BATTERY - self.battery)
                            / (FULL_BATTERY - MIN_BATTERY)))

    @property
    def mood(self):
        if self.phase == BREAK and self.running:
            return CHARGING
        if self.battery >= 70:
            return FRESH
        if self.battery >= 45:
            return WORKING
        if self.battery >= 25:
            return WARM
        return OVERHEATED

    @property
    def phase_label(self):
        return "FOCO" if self.phase == FOCUS else "RECARGA"

    # --- ações ---
    def toggle(self):
        """Botão único: começa a fase esperando, ou alterna pausar/retomar."""
        if self.waiting:
            self.waiting = False
            self.running = True
            return BREAK_BEGUN if self.phase == BREAK else FOCUS_BEGUN
        self.running = not self.running
        return None

    def skip(self):
        """Dá a fase atual por concluída agora."""
        self.elapsed = self.duration
        self._update_battery()
        return self._finish_phase()

    def tick(self, dt):
        if not self.running:
            return []
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.elapsed = self.duration
            self._update_battery()
            return [self._finish_phase()]
        self._update_battery()
        return []

    # --- internos ---
    def _update_battery(self):
        if self.phase == FOCUS:
            target = MIN_BATTERY
        else:
            target = FULL_BATTERY
        self.battery = (self._battery_at_start
                        + (target - self._battery_at_start) * self.progress)

    def _finish_phase(self):
        finished = self.phase
        if finished == FOCUS:
            self.cycles += 1
            self.phase = BREAK
        else:
            self.phase = FOCUS
        self.elapsed = 0.0
        self.running = False
        self.waiting = True
        self.cap = None
        self._battery_at_start = self.battery
        return FOCUS_DONE if finished == FOCUS else BREAK_DONE
