"""Desenho do robô com formas geométricas (sem sprites externos)."""

import math

import pygame

from robot import CHARGING, FRESH, OVERHEATED, WARM, WORKING

INK = (22, 26, 34)
METAL = (176, 186, 200)
SCREEN = (16, 24, 32)
CYAN = (90, 220, 255)
AMBER = (255, 190, 80)
RED = (255, 72, 72)
GREEN = (90, 235, 150)
SMOKE = (96, 100, 112)
SPARK = (255, 232, 120)

EYE_COLOR = {FRESH: CYAN, WORKING: CYAN, WARM: AMBER,
             OVERHEATED: RED, CHARGING: GREEN}


def mix(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def shade(color, k):
    return tuple(min(255, int(round(c * k))) for c in color)


def battery_color(battery):
    if battery >= 55:
        return GREEN
    if battery >= 30:
        return AMBER
    return RED


def _pose_offsets(pose, t):
    """(head_dx, head_dy, body_dy, look) do robô em cada exercício."""
    if pose == "tilt":
        return int(math.sin(t * 1.6) * 8), 0, 0, None
    if pose == "twist":
        return int(math.sin(t * 1.4) * 5), 0, 0, None
    if pose == "shoulders":
        return 0, int(abs(math.sin(t * 2.5)) * 3), 0, None
    if pose == "squat":
        return 0, 0, int(abs(math.sin(t * 1.8)) * 7), None
    if pose == "look_far":
        return 0, 0, 0, (math.sin(t * 0.9), math.cos(t * 0.6) * 0.6)
    return 0, 0, 0, None


def _arm_rect(pose, side, cx, cy, t, joy):
    if pose == "arms_up":
        rect = pygame.Rect(0, 0, 7, 26)
        rect.midbottom = (cx + side * 26, cy + 8)
    elif pose == "twist":
        rect = pygame.Rect(0, 0, 24, 7)
        rect.center = (cx + side * 34,
                       cy + 8 + int(side * math.sin(t * 1.4) * 6))
    elif pose == "wrists":
        rect = pygame.Rect(0, 0, 7, 20)
        rect.midtop = (cx + side * 30 + int(math.cos(t * 6) * 2),
                       cy + 6 + int(math.sin(t * 6) * 3))
    elif pose == "shoulders":
        rect = pygame.Rect(0, 0, 7, 20)
        rect.midtop = (cx + side * 30,
                       cy + 6 - int(abs(math.sin(t * 2.5)) * 6))
    else:
        rect = pygame.Rect(0, 0, 7, 20)
        rect.midtop = (cx + side * 30, cy + 6 - (12 if joy else 0))
    return rect


def draw_robot(surf, cx, cy, t, battery, heat, mood, joy=False, look=(0, 0),
               pose=None):
    """Desenha o robô centrado em (cx, cy); ocupa ~76x100 px.

    `pose` (opcional) faz o robô executar um exercício de alongamento.
    """
    head_dx, head_dy, body_dy, pose_look = _pose_offsets(pose, t)
    cy += body_dy
    hx, hy = cx + head_dx, cy + head_dy
    if pose_look:
        look = pose_look
    metal = mix(METAL, (232, 128, 104), heat * 0.6)
    body_metal = shade(metal, 0.82)
    eye = EYE_COLOR[mood]

    _smoke_and_sparks(surf, cx, cy, t, mood)
    _antenna(surf, hx, hy, t, eye, mood)

    for side in (-1, 1):
        arm = _arm_rect(pose, side, cx, cy, t, joy)
        pygame.draw.rect(surf, body_metal, arm, border_radius=3)
        pygame.draw.rect(surf, INK, arm, 1, border_radius=3)

    for side in (-1, 1):
        foot = pygame.Rect(0, 0, 14, 7)
        foot.midtop = (cx + side * 11, cy + 34)
        pygame.draw.rect(surf, shade(metal, 0.65), foot, border_radius=3)
        pygame.draw.rect(surf, INK, foot, 1, border_radius=3)

    body = pygame.Rect(cx - 22, cy + 4, 44, 32)
    pygame.draw.rect(surf, body_metal, body, border_radius=7)
    pygame.draw.rect(surf, INK, body, 2, border_radius=7)
    _chest_battery(surf, cx, cy, battery)

    for side in (-1, 1):
        bolt = pygame.Rect(0, 0, 5, 12)
        bolt.midright = (hx - 28, hy - 16) if side < 0 else (hx + 33, hy - 16)
        pygame.draw.rect(surf, shade(metal, 0.7), bolt, border_radius=2)
        pygame.draw.rect(surf, INK, bolt, 1, border_radius=2)

    head = pygame.Rect(hx - 28, hy - 36, 56, 38)
    pygame.draw.rect(surf, metal, head, border_radius=9)
    pygame.draw.rect(surf, INK, head, 2, border_radius=9)
    pygame.draw.line(surf, mix(metal, (255, 255, 255), 0.45),
                     (head.x + 8, head.y + 3), (head.right - 8, head.y + 3), 2)

    screen = pygame.Rect(hx - 22, hy - 31, 44, 28)
    pygame.draw.rect(surf, SCREEN, screen, border_radius=5)
    _face(surf, hx, hy - 17, t, eye, mood, look)

    if mood == CHARGING:
        _cable(surf, cx, cy, t)
    if joy:
        _confetti(surf, cx, cy, t)


def _antenna(surf, cx, cy, t, eye, mood):
    pygame.draw.line(surf, INK, (cx, cy - 36), (cx, cy - 46), 2)
    speed = {OVERHEATED: 14.0, WARM: 6.0}.get(mood, 2.5)
    on = math.sin(t * speed) > -0.2
    color = eye if on else shade(eye, 0.35)
    pygame.draw.circle(surf, color, (cx, cy - 49), 4)
    pygame.draw.circle(surf, INK, (cx, cy - 49), 4, 1)


def _chest_battery(surf, cx, cy, battery):
    window = pygame.Rect(cx - 15, cy + 11, 28, 16)
    pygame.draw.rect(surf, SCREEN, window, border_radius=3)
    pygame.draw.rect(surf, INK, (window.right, cy + 15, 3, 8))
    lit = max(1 if battery > 4 else 0, int(math.ceil(battery / 25.0)))
    color = battery_color(battery)
    for i in range(4):
        cell = pygame.Rect(window.x + 3 + i * 6, window.y + 3, 5, 10)
        pygame.draw.rect(surf, color if i < lit else shade(SCREEN, 1.8), cell)
    pygame.draw.rect(surf, INK, window, 1, border_radius=3)


def _face(surf, cx, cy, t, eye, mood, look):
    lx = int(look[0] * 2)
    ly = int(look[1] * 2)
    blink = mood in (FRESH, WORKING) and (t % 4.0) < 0.12
    for side in (-1, 1):
        x = cx + side * 10
        if mood == CHARGING:
            pygame.draw.lines(surf, eye, False,
                              [(x - 4, cy + 1), (x, cy - 3), (x + 4, cy + 1)], 2)
        elif mood == OVERHEATED:
            _x_eye(surf, x, cy - 1, eye)
        elif blink:
            pygame.draw.line(surf, eye, (x - 4, cy), (x + 4, cy), 2)
        else:
            h = {FRESH: 9, WORKING: 7, WARM: 5}[mood]
            rect = pygame.Rect(0, 0, 8, h)
            rect.center = (x + lx, cy + ly)
            pygame.draw.rect(surf, eye, rect, border_radius=2)
            if mood == WARM:       # pálpebra meio fechada
                pygame.draw.line(surf, SCREEN, (rect.x - 1, rect.y),
                                 (rect.right, rect.y + 1), 2)
    _mouth(surf, cx, cy + 8, eye, mood)


def _x_eye(surf, x, y, color):
    jitter = 1 if int(pygame.time.get_ticks() / 90) % 2 else 0
    pygame.draw.line(surf, color, (x - 3, y - 3 + jitter), (x + 3, y + 3), 2)
    pygame.draw.line(surf, color, (x - 3, y + 3), (x + 3, y - 3 + jitter), 2)


def _mouth(surf, mx, my, color, mood):
    if mood in (FRESH, CHARGING):
        pygame.draw.lines(surf, color, False,
                          [(mx - 6, my - 1), (mx - 3, my + 1),
                           (mx + 3, my + 1), (mx + 6, my - 1)], 2)
    elif mood == WORKING:
        pygame.draw.line(surf, color, (mx - 5, my), (mx + 5, my), 2)
    elif mood == WARM:
        pygame.draw.lines(surf, color, False,
                          [(mx - 6, my), (mx - 2, my + 1), (mx + 2, my - 1),
                           (mx + 6, my)], 2)
    else:   # sinal falhando: zigue-zague
        pts = [(mx - 8 + i * 4, my + (2 if i % 2 else -2)) for i in range(5)]
        pygame.draw.lines(surf, color, False, pts, 2)


def _smoke_and_sparks(surf, cx, cy, t, mood):
    if mood not in (WARM, OVERHEATED):
        return
    puffs = 2 if mood == WARM else 4
    for i in range(puffs):
        phase = (t * 0.55 + i / puffs) % 1.0
        x = cx - 14 + i * (28 // max(1, puffs - 1)) + int(math.sin(t * 2 + i) * 3)
        y = cy - 38 - int(phase * 34)
        radius = 3 + int(phase * 5)
        pygame.draw.circle(surf, mix(SMOKE, (50, 52, 60), phase), (x, y), radius)
    if mood == OVERHEATED:
        for i in range(3):
            phase = (t * 3.0 + i * 0.37) % 1.0
            if phase > 0.5:
                continue
            ang = (i * 2.1 + int(t * 3.0 + i)) * 1.7
            x = int(cx + math.cos(ang) * 36)
            y = int(cy - 14 + math.sin(ang) * 26)
            pygame.draw.line(surf, SPARK, (x, y), (x + 3, y - 4), 2)
            pygame.draw.line(surf, SPARK, (x + 3, y - 4), (x + 1, y - 5), 1)


def _cable(surf, cx, cy, t):
    start = (cx + 22, cy + 28)
    pts = [start, (cx + 34, cy + 38), (cx + 42, cy + 34), (cx + 46, cy + 22)]
    pygame.draw.lines(surf, INK, False, pts, 3)
    plug = pygame.Rect(0, 0, 8, 10)
    plug.midbottom = (pts[-1][0], pts[-1][1] + 2)
    pygame.draw.rect(surf, GREEN, plug, border_radius=2)
    pulse = 0.5 + 0.5 * math.sin(t * 6)
    bolt = [(cx + 46, cy + 4), (cx + 41, cy + 13), (cx + 45, cy + 13),
            (cx + 42, cy + 21)]
    pygame.draw.lines(surf, mix(GREEN, (255, 255, 255), pulse), False, bolt, 2)


def _confetti(surf, cx, cy, t):
    colors = (CYAN, GREEN, AMBER, SPARK)
    for i in range(8):
        ang = t * 2.4 + i * math.pi / 4
        r = 46 + 4 * math.sin(t * 5 + i)
        x = int(cx + math.cos(ang) * r)
        y = int(cy - 4 + math.sin(ang) * r * 0.75)
        pygame.draw.rect(surf, colors[i % 4], (x - 2, y - 2, 4, 4))
