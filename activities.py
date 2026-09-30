"""Atividades da recarga: alongamento guiado e jogo da forca. Lógica pura."""

import random

# (nome, instrução, segundos, pose do robô)
STRETCHES = (
    ("Pescoço", "Incline a cabeça devagar para um lado e para o outro", 40,
     "tilt"),
    ("Ombros", "Suba os ombros até as orelhas e solte", 30, "shoulders"),
    ("Braços", "Entrelace os dedos e estique os braços para cima", 40,
     "arms_up"),
    ("Punhos", "Gire os punhos para os dois lados", 30, "wrists"),
    ("Costas", "Abra os braços e gire o tronco devagar", 40, "twist"),
    ("Olhos", "Olhe para longe, pisque e relaxe a vista", 40, "look_far"),
    ("Pernas", "Em pé, flexione os joelhos como um agachamento leve", 40,
     "squat"),
)
MIN_STEP_SECONDS = 5


class StretchRoutine:
    """Sequência de exercícios que cabe no tempo que resta da recarga."""

    def __init__(self, budget=300):
        total = sum(step[2] for step in STRETCHES)
        factor = min(1.0, budget / total)
        self.steps = [(name, text, max(MIN_STEP_SECONDS, round(sec * factor)),
                       pose) for name, text, sec, pose in STRETCHES]
        self.index = 0
        self.elapsed = 0.0

    @property
    def done(self):
        return self.index >= len(self.steps)

    @property
    def current(self):
        return None if self.done else self.steps[self.index]

    @property
    def step_remaining(self):
        return 0.0 if self.done else self.current[2] - self.elapsed

    @property
    def step_progress(self):
        return 1.0 if self.done else min(1.0, self.elapsed / self.current[2])

    def next(self):
        if not self.done:
            self.index += 1
            self.elapsed = 0.0

    def tick(self, dt):
        if self.done:
            return
        self.elapsed += dt
        if self.elapsed >= self.current[2]:
            self.next()


# sem acentos: o jogo aceita só letras de A a Z
WORDS = ("COMPUTADOR", "TECLADO", "CAFE", "REUNIAO", "PLANILHA", "PROJETO",
         "MONITOR", "RELATORIO", "INTERNET", "SERVIDOR", "BATERIA", "ROBO",
         "PAUSA", "DESCANSO", "CADEIRA", "MOUSE", "ALONGAMENTO", "PRAZO",
         "EXPEDIENTE", "SISTEMA", "ARQUIVO", "AGENDA", "ALMOCO", "FOCO")
MAX_ERRORS = 6

PLAYING = "playing"
WON = "won"
LOST = "lost"


class Hangman:
    def __init__(self, word=None, rng=None):
        rng = rng or random
        self.word = (word or rng.choice(WORDS)).upper()
        self.guessed = []
        self.wrong = []

    @property
    def status(self):
        if len(self.wrong) >= MAX_ERRORS:
            return LOST
        if all(ch in self.guessed for ch in self.word):
            return WON
        return PLAYING

    @property
    def masked(self):
        return " ".join(ch if ch in self.guessed else "_" for ch in self.word)

    def guess(self, letter):
        """True se acertou, False se errou, None se ignorada."""
        letter = letter.upper()
        if (self.status != PLAYING or len(letter) != 1
                or not "A" <= letter <= "Z" or letter in self.guessed
                or letter in self.wrong):
            return None
        if letter in self.word:
            self.guessed.append(letter)
            return True
        self.wrong.append(letter)
        return False
