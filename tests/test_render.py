import pygame
import pytest

import main
from robot import BREAK


@pytest.fixture
def app():
    window = main.App(focus_secs=10, break_secs=4, opaque=True)
    yield window
    pygame.quit()


def frame(window, expanded):
    window.reveal = 1.0 if expanded else 0.0
    window.draw()


@pytest.mark.parametrize("expanded", [False, True])
def test_draws_every_mood(app, expanded):
    tm = app.timer
    for battery in (100, 60, 35, 12):
        tm.battery = battery
        frame(app, expanded)
    tm.toggle()
    tm.skip()
    tm.toggle()                 # recarga em andamento
    frame(app, expanded)
    assert tm.phase == BREAK


def test_joy_and_alert_render(app):
    app.joy, app.alert = 1.0, 1.0
    frame(app, True)
    frame(app, False)


def test_primary_action_flow(app):
    app.primary()
    assert app.timer.running
    app.skip()
    assert app.alert > 0 and app.timer.waiting
    app.primary()
    assert app.joy > 0 and app.timer.running


def test_click_on_button_in_expanded_panel(app):
    app.reveal = 1.0
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                              pos=main.BTN_MAIN.center)
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1,
                            pos=main.BTN_MAIN.center)
    app.on_press(down)
    app.on_release(up)
    assert app.timer.running


def test_exit_button_stops_loop(app):
    app.reveal = 1.0
    app.on_release(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1,
                                      pos=main.BTN_EXIT.center))
    assert not app.running
