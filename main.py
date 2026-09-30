"""Working Time Robo — Pomodoro flutuante com um robô que descarrega e recarrega.

Durante o foco a bateria cai e o robô esquenta (fumaça, faíscas, olhos
vermelhos). Quando o tempo acaba ele espera você ligar a recarga: a pausa é
manual. Na recarga ele comemora, conecta o cabo e volta ao normal.

Controles:
    Clique esquerdo ... botão principal (iniciar / pausar / começar fase)
    Arrastar .......... mover a janela
    Clique direito .... reiniciar
    ESPAÇO / ENTER .... botão principal
    S ................. pular fase
    R ................. reiniciar
    ESC ............... sair

Opções: --demo (fases curtas, já iniciado)   --opaque (sem transparência)
"""

import math
import datetime
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import activities
import config
import painter
import workday
from robot import (BREAK, BREAK_BEGUN, BREAK_DONE, CHARGING, FOCUS_DONE,
                   RobotTimer, format_time)
from winfx import WindowFX

WIDTH, HEIGHT = 240, 168
FPS = 60

KEY = (255, 0, 255)             # cor-chave da transparência
BG = (22, 25, 32)
PANEL = (36, 40, 50)
TEXT = (232, 238, 246)
MUTED = (132, 142, 160)
FOCUS_ACCENT = (255, 150, 70)
BREAK_ACCENT = (90, 235, 150)

ALPHA_IDLE, ALPHA_ACTIVE = 130, 240
REVEAL_SPEED = 6.0
JOY_SECONDS = 2.0
ALERT_SECONDS = 1.6

COMPACT_ROBOT = (60, 90)
COMPACT_TIMER = (176, 90)

PANEL_RECT = pygame.Rect(3, 3, WIDTH - 6, HEIGHT - 6)
EXPANDED_ROBOT = (178, 84)
EXPANDED_TIMER = (72, 52)
BTN_MAIN = pygame.Rect(12, 72, 120, 22)
BTN_SKIP = pygame.Rect(12, 98, 38, 20)
BTN_RESET = pygame.Rect(53, 98, 38, 20)
BTN_EXIT = pygame.Rect(94, 98, 38, 20)
BATTERY_BAR = pygame.Rect(12, 140, 216, 13)

# Tela de configuração (dentro do painel expandido)
BTN_GEAR = pygame.Rect(PANEL_RECT.right - 27, PANEL_RECT.y + 5, 20, 20)
BTN_SAVE = pygame.Rect(12, 138, 104, 22)
BTN_CANCEL = pygame.Rect(124, 138, 104, 22)
BTN_TOGGLE = pygame.Rect(12, 114, 216, 18)
SETTING_ROWS = (("focus_min", "foco (minutos)", 44),
                ("break_min", "recarga (minutos)", 86))
# (texto, passo, x, largura) dos botões de cada linha; o valor fica no meio
STEP_BUTTONS = (("-5", -5, 12, 30), ("-1", -1, 46, 30),
                ("+1", 1, 164, 30), ("+5", 5, 198, 30))
VALUE_BOX_X, VALUE_BOX_W = 80, 80
ROW_H = 24
BTN_JORNADA = pygame.Rect(128, 7, 78, 17)

# Atividades da recarga (menu, alongamento e forca)
BTN_MENU = (pygame.Rect(12, 34, 120, 26), pygame.Rect(12, 64, 120, 26),
            pygame.Rect(12, 94, 120, 26))
BTN_ACT_A = pygame.Rect(12, 140, 58, 20)
BTN_ACT_B = pygame.Rect(74, 140, 58, 20)
GALLOWS_ORIGIN = (150, 32)

# Tela da jornada: uma linha por horário (entrada, almoço, volta, saída)
BTN_START = pygame.Rect(12, 140, 104, 20)
BTN_FREE = pygame.Rect(124, 140, 104, 20)
TIME_ROWS = (("entrada", 34), ("almoço", 61), ("volta", 88), ("saída", 115))
TIME_BUTTONS = (("-1h", -60, 70, 26), ("-15", -15, 98, 26),
                ("+15", 15, 174, 26), ("+1h", 60, 202, 26))
TIME_BOX = pygame.Rect(126, 0, 46, 22)
TIME_ROW_H = 22


def step_rect(x, width, y):
    return pygame.Rect(x, y, width, ROW_H)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class App:
    def __init__(self, focus_secs=25 * 60, break_secs=5 * 60, opaque=False,
                 persist=True, setup=False, times=workday.DEFAULT_TIMES,
                 activities_on=True):
        pygame.init()
        self.activities_enabled = activities_on
        self.activity = None            # None | menu | stretch | hangman
        self.routine = None
        self.game = None
        self.menu_note = ""
        self.persist = persist          # salvar escolhas em config.json
        self.settings_open = False
        self.draft = {}
        self.setup_open = setup         # tela "qual a sua jornada?"
        self.draft_times = tuple(times)
        self.editing = None             # linha da jornada sendo digitada
        self.edit_text = ""
        self.schedule = None           # None = modo livre, sem jornada
        self.duty = None                # trecho atual da jornada
        self.now = self.clock_minutes   # injetável nos testes
        pygame.display.set_caption("Working Time Robo")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
        self.clock = pygame.time.Clock()
        self.base = BG if opaque else KEY
        self.timer = RobotTimer(focus_secs, break_secs)

        def font(size, bold=False):
            return pygame.font.SysFont("consolas", size, bold=bold)
        self.f_big, self.f_mid = font(34, True), font(26, True)
        self.f_btn, self.f_small = font(13, True), font(11)

        self.fx = WindowFX()
        self.fx.keep_on_top()
        if not opaque:
            self.fx.make_transparent(KEY)

        self.running = True
        self.reveal = 0.0          # 0 compacto, 1 expandido
        self.joy = 0.0
        self.alert = 0.0
        self.look = (0.0, 0.0)
        self._down = False
        self._moved = False
        self._grab = ((0, 0), (0, 0))   # (cursor, origem da janela)

    # --- geometria ---
    @property
    def expanded(self):
        return self.reveal > 0.4

    def robot_pos(self):
        return EXPANDED_ROBOT if self.expanded else COMPACT_ROBOT

    def robot_hitbox(self):
        rect = pygame.Rect(0, 0, 80, 104)
        rect.center = self.robot_pos()
        return rect

    # --- jornada ---
    @staticmethod
    def clock_minutes():
        now = datetime.datetime.now()
        return now.hour * 60 + now.minute + now.second / 60.0

    def on_duty(self):
        return self.schedule is None or self.duty in workday.WORKING

    def sync_workday(self):
        """Acompanha o relógio: o timer só roda dentro do expediente."""
        if self.schedule is None:
            self.duty = None
            return
        seg = workday.segment(self.schedule, self.now())
        if seg == self.duty:
            return
        first = self.duty is None
        self.duty = seg
        self.timer.new_block()
        if seg in workday.WORKING:
            self.toggle_timer()             # expediente: já começa a contar
            if not first:
                self.joy = JOY_SECONDS      # voltou do almoço / começou o dia
        elif not first:
            self.alert = ALERT_SECONDS

    def off_duty_info(self):
        """(rótulo da fase, status, rótulo do botão, segundos até a virada)."""
        seg = self.duty
        event = workday.next_event(self.schedule, seg, self.now())
        wait = (event - self.now()) * 60
        at = workday.format_clock(event % (24 * 60))
        return {workday.BEFORE: ("FORA", "antes do turno", f"começa {at}"),
                workday.LUNCH: ("ALMOÇO", "almoçando", f"volta {at}"),
                workday.AFTER: ("FORA", "fim do turno", "fim de turno"),
                }[seg] + (wait,)

    def display_mood(self):
        return self.timer.mood if self.on_duty() else CHARGING

    def open_setup(self):
        self.draft_times = tuple(self.schedule or self.draft_times)
        self.settings_open = False
        self.setup_open = True
        self.editing, self.edit_text = None, ""

    def confirm_setup(self):
        self.schedule = tuple(self.draft_times)
        if self.persist:
            try:
                config.save({"workday": list(self.schedule)})
            except OSError:
                pass
        self.duty = None
        self.setup_open = False
        self.editing, self.edit_text = None, ""
        self.sync_workday()

    def free_mode(self):
        self.schedule = None
        self.duty = None
        self.timer.new_block()
        self.setup_open = False

    def commit_edit(self):
        """Aplica o horário digitado; se for inválido, mantém o anterior."""
        minutes = workday.parse_clock(self.edit_text)
        if self.editing is not None and minutes is not None:
            self.draft_times = workday.set_time(
                self.draft_times, self.editing, minutes)
        self.editing, self.edit_text = None, ""

    def edit_key(self, key):
        if key == pygame.K_ESCAPE:
            self.editing, self.edit_text = None, ""
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self.commit_edit()
        elif key == pygame.K_BACKSPACE:
            self.edit_text = self.edit_text[:-1]
        elif pygame.K_0 <= key <= pygame.K_9:
            self.type_digit(key - pygame.K_0)
        elif pygame.K_KP1 <= key <= pygame.K_KP9:
            self.type_digit(key - pygame.K_KP1 + 1)
        elif key == pygame.K_KP0:
            self.type_digit(0)

    def type_digit(self, digit):
        if len(self.edit_text) < 4:
            self.edit_text += str(digit)

    def click_setup(self, pos):
        boxes = [TIME_BOX.move(0, y).collidepoint(pos) for _, y in TIME_ROWS]
        hit = boxes.index(True) if True in boxes else None
        if self.editing is not None and hit != self.editing:
            self.commit_edit()
        if hit is not None:
            self.editing, self.edit_text = hit, ""
            return
        if BTN_START.collidepoint(pos):
            self.confirm_setup()
        elif BTN_FREE.collidepoint(pos):
            self.free_mode()
        for i, (_, y) in enumerate(TIME_ROWS):
            for _, delta, x, width in TIME_BUTTONS:
                if pygame.Rect(x, y, width, TIME_ROW_H).collidepoint(pos):
                    self.draft_times = workday.shift(
                        self.draft_times, i, delta)

    # --- ações ---
    def primary(self):
        self.sync_workday()
        if self.on_duty():
            self.toggle_timer()

    def toggle_timer(self):
        tm = self.timer
        starting = tm.waiting or (not tm.running and tm.elapsed == 0)
        if starting and self.schedule:
            # a fase nunca passa do horário do almoço / fim do expediente
            left = (workday.block_end(self.schedule, self.duty)
                    - self.now()) * 60
            tm.cap = max(1.0, left)
        if tm.toggle() == BREAK_BEGUN:
            self.joy = JOY_SECONDS
            if self.activities_enabled:
                self.menu_note = ""
                self.activity = "menu"

    def skip(self):
        if not self.on_duty():
            return
        if self.timer.skip() in (FOCUS_DONE, BREAK_DONE):
            self.alert = ALERT_SECONDS

    def open_settings(self):
        self.draft = {"focus_min": round(self.timer.focus_secs / 60),
                      "break_min": round(self.timer.break_secs / 60),
                      "activities": self.activities_enabled}
        self.settings_open = True
        self.setup_open = False

    def apply_settings(self):
        values = dict(self.draft)
        if self.persist:
            try:
                values = config.save(values)
            except OSError:
                pass        # sem permissão de escrita: vale só nesta sessão
        self.timer.focus_secs = values["focus_min"] * 60
        self.timer.break_secs = values["break_min"] * 60
        self.activities_enabled = values["activities"]
        self.timer.reset()
        self.settings_open = False

    def click_settings(self, pos):
        if BTN_SAVE.collidepoint(pos):
            self.apply_settings()
        elif BTN_CANCEL.collidepoint(pos) or BTN_GEAR.collidepoint(pos):
            self.settings_open = False
        elif BTN_JORNADA.collidepoint(pos):
            self.open_setup()
        elif BTN_TOGGLE.collidepoint(pos):
            self.draft["activities"] = not self.draft["activities"]
        for key, _, y in SETTING_ROWS:
            for _, step, x, width in STEP_BUTTONS:
                if step_rect(x, width, y).collidepoint(pos):
                    self.draft[key] = config.clamp_minutes(
                        key, self.draft[key] + step)

    # --- atividades da recarga ---
    def show_menu(self, note=""):
        self.activity = "menu"
        self.menu_note = note

    def click_activity(self, pos):
        first, second, third = (b.collidepoint(pos) for b in BTN_MENU)
        if self.activity == "menu":
            if first:
                self.routine = activities.StretchRoutine(
                    max(1.0, self.timer.remaining))
                self.activity = "stretch"
            elif second:
                if self.game is None or self.game.status != activities.PLAYING:
                    self.game = activities.Hangman()
                self.activity = "hangman"
            elif third:
                self.activity = None
        elif self.activity == "stretch":
            if BTN_ACT_A.collidepoint(pos):
                self.routine.next()
                if self.routine.done:
                    self.show_menu("alongamento feito!")
            elif BTN_ACT_B.collidepoint(pos):
                self.show_menu()
        elif self.activity == "hangman":
            if BTN_ACT_A.collidepoint(pos):
                self.game = activities.Hangman()
            elif BTN_ACT_B.collidepoint(pos):
                self.show_menu()

    def activity_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.activity == "menu":
                self.activity = None
            else:
                self.show_menu()
        elif self.activity == "hangman":
            if pygame.K_a <= key <= pygame.K_z:
                self.game.guess(chr(key))
            elif (key == pygame.K_RETURN
                  and self.game.status != activities.PLAYING):
                self.game = activities.Hangman()

    def update_activity(self, dt):
        tm = self.timer
        if self.activity and (tm.phase != BREAK or tm.waiting):
            self.activity = None            # a recarga acabou (ou foi pulada)
        if self.activity == "stretch" and tm.running:
            self.routine.tick(dt)
            if self.routine.done:
                self.show_menu("alongamento feito!")

    # --- eventos ---
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                self.on_key(ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                self.on_press(ev)
            elif ev.type == pygame.MOUSEBUTTONUP:
                self.on_release(ev)
            elif ev.type == pygame.MOUSEMOTION:
                self.on_motion()

    def on_key(self, key):
        if self.setup_open and self.editing is not None:
            self.edit_key(key)
        elif self.activity:
            self.activity_key(key)
        elif key == pygame.K_ESCAPE:
            self.running = False
        elif self.setup_open:
            if key == pygame.K_RETURN:
                self.confirm_setup()
        elif self.settings_open:
            return
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self.primary()
        elif key == pygame.K_s:
            self.skip()
        elif key == pygame.K_r:
            self.timer.reset()

    def on_press(self, ev):
        if ev.button == 1:
            self._down, self._moved = True, False
            self._grab = (self.fx.cursor() if self.fx.ok else (0, 0),
                          self.fx.origin() if self.fx.ok else (0, 0))
        elif (ev.button == 3 and not self.settings_open
              and not self.setup_open):
            self.timer.reset()

    def on_release(self, ev):
        if ev.button != 1:
            return
        dragged, self._down, self._moved = self._moved, False, False
        if dragged:
            return
        if self.setup_open:
            self.click_setup(ev.pos)
        elif self.activity:
            self.click_activity(ev.pos)
        elif not self.expanded:
            self.primary()
        elif self.settings_open:
            self.click_settings(ev.pos)
        elif BTN_GEAR.collidepoint(ev.pos):
            self.open_settings()
        elif BTN_SKIP.collidepoint(ev.pos):
            self.skip()
        elif BTN_RESET.collidepoint(ev.pos):
            self.timer.reset()
        elif BTN_EXIT.collidepoint(ev.pos):
            self.running = False
        elif (BTN_MAIN.collidepoint(ev.pos)
              or self.robot_hitbox().collidepoint(ev.pos)):
            self.primary()

    def on_motion(self):
        if not (self._down and self.fx.ok):
            return
        (cx0, cy0), (ox, oy) = self._grab
        cx, cy = self.fx.cursor()
        if abs(cx - cx0) > 3 or abs(cy - cy0) > 3:
            self._moved = True
        if self._moved:
            self.fx.move(ox + cx - cx0, oy + cy - cy0, WIDTH, HEIGHT)

    # --- loop ---
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def update(self, dt):
        self.sync_workday()
        if self.on_duty():
            for ev in self.timer.tick(dt):
                if ev in (FOCUS_DONE, BREAK_DONE):
                    self.alert = ALERT_SECONDS
        self.update_activity(dt)
        self.joy = max(0.0, self.joy - dt)
        self.alert = max(0.0, self.alert - dt)

        target = 1.0 if (pygame.mouse.get_focused() or self.setup_open
                         or self.activity) else 0.0
        step = REVEAL_SPEED * dt
        self.reveal = (min(target, self.reveal + step) if self.reveal < target
                       else max(target, self.reveal - step))

        cx, cy = self.robot_pos()
        mx, my = pygame.mouse.get_pos()
        self.look = (clamp((mx - cx) / (WIDTH / 2), -1, 1),
                     clamp((my - cy) / (HEIGHT / 2), -1, 1))

    # --- desenho ---
    def accent(self):
        return BREAK_ACCENT if self.timer.phase == BREAK else FOCUS_ACCENT

    def timer_color(self):
        if not self.on_duty():
            return MUTED
        return self.accent() if self.timer.waiting else TEXT

    def timer_text(self):
        if not self.on_duty():
            return workday.format_countdown(self.off_duty_info()[3])
        return format_time(self.timer.remaining)

    def main_label(self):
        tm = self.timer
        if not self.on_duty():
            return self.off_duty_info()[2]
        if tm.waiting:
            return "recarregar" if tm.phase == BREAK else "iniciar foco"
        if tm.running:
            return "pausar"
        return "retomar" if tm.elapsed > 0 else "iniciar"

    def draw(self):
        t = pygame.time.get_ticks() / 1000.0
        self.screen.fill(self.base)
        if self.expanded:
            self.draw_panel(t)
        else:
            self.draw_robot(t, *COMPACT_ROBOT)
            label = self.f_big.render(self.timer_text(), False,
                                      self.timer_color())
            self.screen.blit(label, label.get_rect(center=COMPACT_TIMER))
            self.draw_alert(COMPACT_ROBOT[0], COMPACT_ROBOT[1] - 62)
            if self.schedule:
                left = workday.time_to_exit(self.schedule, self.now())
                note = (f"sair em {workday.format_until(left)}" if left
                        else "fim de turno")
                text = self.f_small.render(note, False, TEXT)
                self.screen.blit(text, text.get_rect(
                    center=(COMPACT_TIMER[0], COMPACT_TIMER[1] + 26)))
        alpha = ALPHA_IDLE + (ALPHA_ACTIVE - ALPHA_IDLE) * self.reveal
        self.fx.set_alpha(alpha)

    def draw_robot(self, t, cx, cy, pose=None):
        tm = self.timer
        bob = (-abs(math.sin(t * 7)) * 10 if self.joy > 0
               else math.sin(t * (3.5 if tm.heat > 0.7 else 2.0)) * 3)
        painter.draw_robot(self.screen, cx, int(cy + bob), t, tm.battery,
                           tm.heat, self.display_mood(), self.joy > 0,
                           self.look, pose)

    def draw_gear(self):
        rect = BTN_GEAR
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        color = TEXT if hovered or self.settings_open else MUTED
        cx, cy = rect.center
        for i in range(8):
            ang = i * math.pi / 4
            pygame.draw.line(
                self.screen, color,
                (cx + math.cos(ang) * 5, cy + math.sin(ang) * 5),
                (cx + math.cos(ang) * 8, cy + math.sin(ang) * 8), 3)
        pygame.draw.circle(self.screen, color, (cx, cy), 6)
        pygame.draw.circle(self.screen, PANEL, (cx, cy), 2)

    def draw_settings(self):
        title = self.f_small.render("CONFIGURAÇÃO", False, (18, 20, 26))
        pill = pygame.Rect(0, 0, title.get_width() + 16, 17)
        pill.topleft = (PANEL_RECT.x + 8, PANEL_RECT.y + 7)
        pygame.draw.rect(self.screen, FOCUS_ACCENT, pill, border_radius=8)
        self.screen.blit(title, title.get_rect(center=pill.center))
        self.button(BTN_JORNADA, "jornada")

        for key, label, y in SETTING_ROWS:
            self.screen.blit(self.f_small.render(label, False, MUTED),
                             (12, y - 15))
            for text, step, x, width in STEP_BUTTONS:
                self.button(step_rect(x, width, y), text)
            box = pygame.Rect(VALUE_BOX_X, y, VALUE_BOX_W, ROW_H)
            pygame.draw.rect(self.screen, painter.shade(PANEL, 0.75), box,
                             border_radius=5)
            value = self.f_mid.render(str(self.draft[key]), False, TEXT)
            self.screen.blit(value, value.get_rect(center=box.center))

        state = "sim" if self.draft["activities"] else "não"
        self.button(BTN_TOGGLE, f"atividades na recarga: {state}")
        self.button(BTN_SAVE, "salvar e zerar", primary=True)
        self.button(BTN_CANCEL, "cancelar")

    def draw_panel(self, t):
        tm = self.timer
        pygame.draw.rect(self.screen, PANEL, PANEL_RECT, border_radius=10)
        pygame.draw.rect(self.screen, painter.shade(PANEL, 1.7), PANEL_RECT, 2,
                         border_radius=10)
        if self.setup_open:
            self.draw_setup()
            return
        if self.activity:
            self.draw_activity(t)
            return
        self.draw_gear()
        if self.settings_open:
            self.draw_settings()
            return

        if self.on_duty():
            phase_text = tm.phase_label
            status = ("aguardando" if tm.waiting
                      else "ligado" if tm.running else "em espera")
        else:
            phase_text, status = self.off_duty_info()[:2]
        label = self.f_small.render(phase_text, False, (18, 20, 26))
        pill = pygame.Rect(0, 0, label.get_width() + 16, 17)
        pill.topleft = (PANEL_RECT.x + 8, PANEL_RECT.y + 7)
        pygame.draw.rect(self.screen, self.accent(), pill, border_radius=8)
        self.screen.blit(label, label.get_rect(center=pill.center))

        txt = self.f_small.render(status, False, MUTED)
        self.screen.blit(txt, txt.get_rect(
            midleft=(pill.right + 8, pill.centery)))

        self.draw_robot(t, *EXPANDED_ROBOT)
        clock = self.f_mid.render(self.timer_text(), False,
                                  self.timer_color())
        self.screen.blit(clock, clock.get_rect(center=EXPANDED_TIMER))

        self.button(BTN_MAIN, self.main_label(), primary=self.on_duty())
        self.button(BTN_SKIP, "Pular")
        self.button(BTN_RESET, "Zerar")
        self.button(BTN_EXIT, "Sair")
        self.draw_battery()
        self.draw_alert(EXPANDED_ROBOT[0], EXPANDED_ROBOT[1] - 62)

    def button(self, rect, label, primary=False):
        tm = self.timer
        lit = primary and (tm.waiting or not tm.running)
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        base = self.accent() if lit else painter.shade(PANEL, 1.35)
        color = painter.mix(base, (255, 255, 255), 0.25 if hovered else 0.0)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, painter.shade(PANEL, 1.9), rect, 1,
                         border_radius=5)
        txt = self.f_btn.render(label, False, (18, 20, 26) if lit else TEXT)
        self.screen.blit(txt, txt.get_rect(center=rect.center))

    def draw_battery(self):
        tm = self.timer
        bar = BATTERY_BAR
        pygame.draw.rect(self.screen, painter.shade(PANEL, 0.75), bar,
                         border_radius=5)
        width = int(bar.width * clamp(tm.battery / 100.0, 0, 1))
        if width > 0:
            pygame.draw.rect(self.screen, painter.battery_color(tm.battery),
                             (bar.x, bar.y, width, bar.height), border_radius=5)
        pygame.draw.rect(self.screen, painter.shade(PANEL, 1.8), bar, 1,
                         border_radius=5)
        self.outlined_text(f"bateria {int(tm.battery)}%",
                           (bar.x + 6, bar.centery))
        if self.schedule:
            self.draw_day_bar()
            self.screen.blit(self.f_small.render(self.exit_text(), False, TEXT),
                             (bar.x, bar.y - 15))
        cycles = self.f_small.render(f"ciclos {tm.cycles}", False, MUTED)
        self.screen.blit(cycles, cycles.get_rect(
            topright=(bar.right, bar.y - 15)))

    def outlined_text(self, text, midleft):
        """Texto claro com contorno escuro: legível sobre qualquer cor."""
        shadow = self.f_small.render(text, False, (12, 14, 18))
        light = self.f_small.render(text, False, TEXT)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.screen.blit(shadow, shadow.get_rect(
                midleft=(midleft[0] + dx, midleft[1] + dy)))
        self.screen.blit(light, light.get_rect(midleft=midleft))

    def exit_text(self):
        left = workday.time_to_exit(self.schedule, self.now())
        if left <= 0:
            return "expediente encerrado"
        return (f"sair {workday.format_clock(self.schedule[3])}"
                f" · faltam {workday.format_until(left)}")

    def pill(self, text, color, extra=""):
        label = self.f_small.render(text, False, (18, 20, 26))
        pill = pygame.Rect(0, 0, label.get_width() + 16, 17)
        pill.topleft = (PANEL_RECT.x + 8, PANEL_RECT.y + 7)
        pygame.draw.rect(self.screen, color, pill, border_radius=8)
        self.screen.blit(label, label.get_rect(center=pill.center))
        if extra:
            note = self.f_small.render(extra, False, MUTED)
            self.screen.blit(note, note.get_rect(
                midleft=(pill.right + 8, pill.centery)))

    def wrap(self, text, width):
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.f_small.size(trial)[0] > width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line] if line else lines

    def draw_activity(self, t):
        rest = format_time(self.timer.remaining)
        if self.activity == "menu":
            self.draw_menu(t, rest)
        elif self.activity == "stretch":
            self.draw_stretch(t, rest)
        else:
            self.draw_hangman(rest)

    def draw_menu(self, t, rest):
        self.pill("DESCANSO", BREAK_ACCENT, f"faltam {rest}")
        for rect, label in zip(BTN_MENU, ("Alongar", "Jogar forca",
                                          "Só descansar")):
            self.button(rect, label)
        if self.menu_note:
            note = self.f_small.render(self.menu_note, False, BREAK_ACCENT)
            self.screen.blit(note, (12, 128))
        self.draw_robot(t, *EXPANDED_ROBOT)

    def draw_stretch(self, t, rest):
        routine = self.routine
        name, text, _, pose = routine.current
        self.pill("ALONGAR", BREAK_ACCENT,
                  f"{routine.index + 1}/{len(routine.steps)} · {rest}")
        self.screen.blit(self.f_btn.render(name, False, TEXT), (12, 32))
        for i, line in enumerate(self.wrap(text, 120)[:4]):
            self.screen.blit(self.f_small.render(line, False, MUTED),
                             (12, 50 + i * 13))
        clock = self.f_mid.render(format_time(routine.step_remaining), False,
                                  BREAK_ACCENT)
        self.screen.blit(clock, (12, 104))
        bar = pygame.Rect(12, 132, 120, 3)
        pygame.draw.rect(self.screen, painter.shade(PANEL, 0.75), bar)
        pygame.draw.rect(self.screen, BREAK_ACCENT,
                         (bar.x, bar.y, int(bar.width * routine.step_progress),
                          bar.height))
        self.button(BTN_ACT_A, "Próximo")
        self.button(BTN_ACT_B, "Voltar")
        self.draw_robot(t, *EXPANDED_ROBOT, pose=pose)

    def draw_hangman(self, rest):
        game = self.game
        errors = len(game.wrong)
        self.pill("FORCA", BREAK_ACCENT, f"erros {errors}/{activities.MAX_ERRORS}")
        self.draw_gallows(errors, game.status == activities.LOST)
        hint = {activities.PLAYING: "digite letras",
                activities.WON: "acertou!",
                activities.LOST: "era: " + game.word}[game.status]
        color = {activities.PLAYING: MUTED, activities.WON: BREAK_ACCENT,
                 activities.LOST: painter.RED}[game.status]
        self.screen.blit(self.f_small.render(hint, False, color), (12, 34))
        for i, line in enumerate(self.wrap(" ".join(game.wrong), 120)[:3]):
            self.screen.blit(self.f_small.render(line, False, MUTED),
                             (12, 50 + i * 13))
        word = self.f_mid.render(game.masked, False, TEXT)
        if word.get_width() > 208:          # palavra longa: encolhe para caber
            word = pygame.transform.scale(
                word, (208, word.get_height() * 208 // word.get_width()))
        self.screen.blit(word, word.get_rect(center=(PANEL_RECT.centerx, 113)))
        self.button(BTN_ACT_A, "Nova")
        self.button(BTN_ACT_B, "Voltar")
        clock = self.f_small.render(rest, False, MUTED)
        self.screen.blit(clock, clock.get_rect(
            midright=(PANEL_RECT.right - 12, 150)))

    def draw_gallows(self, errors, lost):
        ox, oy = GALLOWS_ORIGIN
        line = lambda a, b, col=MUTED: pygame.draw.line(
            self.screen, col, (ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), 2)
        line((0, 62), (60, 62))
        line((14, 62), (14, 2))
        line((14, 2), (44, 2))
        line((44, 2), (44, 12))
        col = painter.RED if lost else TEXT
        if errors >= 1:
            pygame.draw.circle(self.screen, col, (ox + 44, oy + 18), 6, 2)
        parts = ((2, (44, 24), (44, 42)), (3, (44, 29), (36, 36)),
                 (4, (44, 29), (52, 36)), (5, (44, 42), (37, 54)),
                 (6, (44, 42), (51, 54)))
        for need, a, b in parts:
            if errors >= need:
                line(a, b, col)

    def draw_day_bar(self):
        bar = pygame.Rect(BATTERY_BAR.x, BATTERY_BAR.bottom + 6,
                          BATTERY_BAR.width, 3)
        pygame.draw.rect(self.screen, painter.shade(PANEL, 0.75), bar)
        done = workday.day_progress(self.schedule, self.now())
        if done > 0:
            pygame.draw.rect(self.screen, FOCUS_ACCENT,
                             (bar.x, bar.y, int(bar.width * done), bar.height))

    def draw_setup(self):
        title = self.f_small.render("SUA JORNADA", False, (18, 20, 26))
        pill = pygame.Rect(0, 0, title.get_width() + 16, 17)
        pill.topleft = (PANEL_RECT.x + 8, PANEL_RECT.y + 7)
        pygame.draw.rect(self.screen, FOCUS_ACCENT, pill, border_radius=8)
        self.screen.blit(title, title.get_rect(center=pill.center))

        for i, ((label, y), value) in enumerate(zip(TIME_ROWS,
                                                    self.draft_times)):
            self.screen.blit(self.f_small.render(label, False, MUTED),
                             (12, y + 5))
            for text, _, x, width in TIME_BUTTONS:
                self.button(pygame.Rect(x, y, width, TIME_ROW_H), text)
            box = TIME_BOX.move(0, y)
            pygame.draw.rect(self.screen, painter.shade(PANEL, 0.75), box,
                             border_radius=5)
            typing = self.editing == i
            if typing:
                pygame.draw.rect(self.screen, FOCUS_ACCENT, box, 1,
                                 border_radius=5)
                text = self.edit_text
                shown = (f"{text}_" if len(text) <= 2
                         else f"{text[:-2]}:{text[-2:]}")
            else:
                shown = workday.format_clock(value)
            clock = self.f_btn.render(shown, False, TEXT)
            self.screen.blit(clock, clock.get_rect(center=box.center))
        self.button(BTN_START, "começar dia", primary=True)
        self.button(BTN_FREE, "modo livre")

    def draw_alert(self, x, y):
        if self.alert <= 0:
            return
        pulse = 1.0 + 0.4 * abs(math.sin(pygame.time.get_ticks() / 130.0))
        mark = self.f_btn.render("!", False, self.accent())
        size = (int(mark.get_width() * pulse * 1.5),
                int(mark.get_height() * pulse * 1.5))
        mark = pygame.transform.scale(mark, size)
        self.screen.blit(mark, mark.get_rect(center=(int(x), int(y))))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    opaque = "--opaque" in argv
    if "--demo" in argv:
        app = App(focus_secs=8, break_secs=60, opaque=opaque, persist=False)
        app.timer.toggle()
    else:
        saved = config.load()
        app = App(focus_secs=saved["focus_min"] * 60,
                  break_secs=saved["break_min"] * 60, opaque=opaque,
                  setup=True, times=tuple(saved["workday"]),
                  activities_on=saved["activities"])
    app.run()


if __name__ == "__main__":
    main()
