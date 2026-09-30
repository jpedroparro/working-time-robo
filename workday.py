"""Jornada de trabalho: entrada, almoço, volta e saída. Lógica pura.

Os horários são minutos desde a meia-noite, numa tupla
(entrada, almoço, volta, saída). `now` também é em minutos (pode ter fração).
"""

MIN_GAP = 15
DEFAULT_TIMES = (8 * 60, 12 * 60, 13 * 60, 17 * 60)

BEFORE = "before"
MORNING = "morning"
LUNCH = "lunch"
AFTERNOON = "afternoon"
AFTER = "after"

WORKING = (MORNING, AFTERNOON)


def valid_times(times):
    try:
        ok = len(times) == 4 and all(isinstance(t, int) for t in times)
    except TypeError:
        return False
    return (ok and 0 <= times[0] and times[3] <= 24 * 60 - 1
            and all(b - a >= MIN_GAP for a, b in zip(times, times[1:])))


def shift(times, index, delta):
    """Move um horário e empurra os vizinhos para manter a ordem.

    Devolve a tupla original se o resultado sair do dia (00:00-23:59).
    """
    t = list(times)
    t[index] += delta
    for j in range(index + 1, 4):
        t[j] = max(t[j], t[j - 1] + MIN_GAP)
    for j in range(index - 1, -1, -1):
        t[j] = min(t[j], t[j + 1] - MIN_GAP)
    return tuple(t) if valid_times(t) else tuple(times)


def set_time(times, index, minutes):
    """Define um horário exato (empurrando os vizinhos, como shift)."""
    return shift(times, index, minutes - times[index])


def parse_clock(text):
    """'13:12', '1312', '912' ou '9' -> minutos; None se for inválido."""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not 1 <= len(digits) <= 4:
        return None
    hours, minutes = ((int(digits), 0) if len(digits) <= 2
                      else (int(digits[:-2]), int(digits[-2:])))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def segment(times, now):
    start, lunch, back, end = times
    if now < start:
        return BEFORE
    if now < lunch:
        return MORNING
    if now < back:
        return LUNCH
    if now < end:
        return AFTERNOON
    return AFTER


def block_end(times, seg):
    """Minuto em que termina o bloco de trabalho atual."""
    return times[1] if seg == MORNING else times[3]


def next_event(times, seg, now):
    """Minuto da próxima virada (amanhã, se o expediente já acabou)."""
    return {BEFORE: times[0], MORNING: times[1], LUNCH: times[2],
            AFTERNOON: times[3], AFTER: times[0] + 24 * 60}[seg]


def worked_remaining(times, now):
    """Segundos de trabalho que faltam hoje (sem contar o almoço)."""
    start, lunch, back, end = times
    left = (max(0.0, lunch - max(start, now))
            + max(0.0, end - max(back, now)))
    return left * 60


def time_to_exit(times, now):
    """Segundos de relógio até a saída (inclui o almoço); 0 depois dela."""
    return max(0.0, times[3] - now) * 60


def day_progress(times, now):
    start, lunch, back, end = times
    total = (lunch - start) + (end - back)
    done = total - worked_remaining(times, now) / 60
    return max(0.0, min(1.0, done / total))


def format_clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def format_hm(seconds):
    minutes = max(0, int(seconds // 60))
    return f"{minutes // 60}h{minutes % 60:02d}"


def format_countdown(seconds):
    """1h05 quando falta uma hora ou mais; senão MM:SS."""
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return format_hm(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_until(seconds):
    """1h44 quando falta uma hora ou mais; senão '44 min'."""
    minutes = max(0, int(seconds // 60))
    if minutes >= 60:
        return f"{minutes // 60}h{minutes % 60:02d}"
    return f"{minutes} min"
