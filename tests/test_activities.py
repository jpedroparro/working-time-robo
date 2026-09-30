import random

import pygame
import pytest

import activities as act
import config
import main


# --- lógica pura ---
def test_routine_fits_the_break():
    routine = act.StretchRoutine(budget=300)
    assert sum(step[2] for step in routine.steps) <= 300
    short = act.StretchRoutine(budget=60)
    assert sum(step[2] for step in short.steps) <= 60 + 5 * len(short.steps)
    assert all(step[2] >= act.MIN_STEP_SECONDS for step in short.steps)


def test_routine_advances_and_finishes():
    routine = act.StretchRoutine(budget=1000)
    first = routine.current
    routine.tick(first[2] - 1)
    assert routine.current is first and routine.step_remaining == pytest.approx(1)
    routine.tick(1)
    assert routine.index == 1 and routine.elapsed == 0
    while not routine.done:
        routine.next()
    assert routine.current is None and routine.step_remaining == 0
    routine.tick(5)                      # não quebra depois de pronto
    assert routine.done


def test_hangman_win_and_loss():
    game = act.Hangman(word="robo")
    assert game.masked == "_ _ _ _"
    assert game.guess("r") is True and game.guess("R") is None
    assert game.guess("z") is False and game.guess("z") is None
    assert game.masked == "R _ _ _" and game.wrong == ["Z"]
    game.guess("o")
    game.guess("b")
    assert game.status == act.WON and game.masked == "R O B O"
    assert game.guess("a") is None       # jogo acabou

    lose = act.Hangman(word="robo")
    for letter in "QWEXYZ":
        lose.guess(letter)
    assert lose.status == act.LOST


def test_hangman_ignores_non_letters():
    game = act.Hangman(word="robo")
    assert game.guess("1") is None and game.guess("") is None
    assert game.guess("ab") is None and not game.wrong


def test_random_word_comes_from_list():
    game = act.Hangman(rng=random.Random(1))
    assert game.word in act.WORDS


def test_config_activities_flag(tmp_path):
    path = tmp_path / "c.json"
    assert config.load(path)["activities"] is True
    config.save({"activities": False}, path)
    assert config.load(path)["activities"] is False
    path.write_text('{"activities": "nao"}')
    assert config.load(path)["activities"] is True


# --- integração com a janela ---
@pytest.fixture
def app():
    window = main.App(focus_secs=10, break_secs=60, opaque=True, persist=False)
    window.reveal = 1.0
    yield window
    pygame.quit()


def click(window, rect):
    window.on_release(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=rect.center))


def start_break(window):
    window.primary()
    window.skip()
    window.primary()                     # começa a recarga


def test_menu_opens_when_break_starts(app):
    start_break(app)
    assert app.activity == "menu"
    app.draw()


def test_focus_does_not_open_menu(app):
    app.primary()
    assert app.activity is None


def test_menu_can_be_disabled(app):
    app.activities_enabled = False
    start_break(app)
    assert app.activity is None


def test_just_rest_closes_menu(app):
    start_break(app)
    click(app, main.BTN_MENU[2])
    assert app.activity is None


def test_stretch_flow_with_every_pose(app):
    start_break(app)
    click(app, main.BTN_MENU[0])
    assert app.activity == "stretch"
    for _ in app.routine.steps:
        app.draw()
        app.update(0.1)
        click(app, main.BTN_ACT_A)       # próximo
    assert app.activity == "menu" and "feito" in app.menu_note
    app.draw()


def test_stretch_steps_follow_the_clock(app):
    start_break(app)
    click(app, main.BTN_MENU[0])
    first = app.routine.current
    app.update(first[2] + 0.5)
    assert app.routine.index == 1


def test_back_button_returns_to_menu(app):
    start_break(app)
    click(app, main.BTN_MENU[0])
    click(app, main.BTN_ACT_B)
    assert app.activity == "menu"


def test_hangman_by_keyboard(app):
    start_break(app)
    click(app, main.BTN_MENU[1])
    assert app.activity == "hangman"
    app.game = act.Hangman(word="robo")
    app.on_key(pygame.K_r)
    app.on_key(pygame.K_z)
    assert app.game.masked == "R _ _ _" and app.game.wrong == ["Z"]
    app.draw()
    for key in (pygame.K_o, pygame.K_b):
        app.on_key(key)
    assert app.game.status == act.WON
    app.draw()
    app.on_key(pygame.K_RETURN)          # nova partida
    assert app.game.status == act.PLAYING and app.game.word != ""


def test_hangman_lost_screen_and_new_button(app):
    start_break(app)
    click(app, main.BTN_MENU[1])
    app.game = act.Hangman(word="robo")
    for key in (pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_x, pygame.K_y,
                pygame.K_z):
        app.on_key(key)
    assert app.game.status == act.LOST
    app.draw()
    old = app.game
    click(app, main.BTN_ACT_A)
    assert app.game is not old


def test_unfinished_game_is_kept_between_visits(app):
    start_break(app)
    click(app, main.BTN_MENU[1])
    app.game = act.Hangman(word="robo")
    app.on_key(pygame.K_r)
    click(app, main.BTN_ACT_B)           # volta ao menu
    click(app, main.BTN_MENU[1])
    assert app.game.guessed == ["R"]


def test_escape_leaves_activity_without_quitting(app):
    start_break(app)
    click(app, main.BTN_MENU[0])
    app.on_key(pygame.K_ESCAPE)
    assert app.activity == "menu" and app.running
    app.on_key(pygame.K_ESCAPE)
    assert app.activity is None and app.running
    app.on_key(pygame.K_ESCAPE)
    assert not app.running


def test_activity_closes_when_break_ends(app):
    start_break(app)
    click(app, main.BTN_MENU[0])
    app.update(61)                       # a recarga de 60 s termina
    assert app.activity is None and app.timer.waiting


def test_skip_during_break_closes_activity(app):
    start_break(app)
    app.skip()
    app.update(0.1)
    assert app.activity is None


def test_settings_toggle_persists_choice(app, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PATH", str(tmp_path / "c.json"))
    app.persist = True
    click(app, main.BTN_GEAR)
    app.draw()
    click(app, main.BTN_TOGGLE)
    assert app.draft["activities"] is False
    click(app, main.BTN_SAVE)
    assert app.activities_enabled is False
    assert config.load()["activities"] is False


def test_keys_during_activity_do_not_trigger_timer(app):
    start_break(app)
    click(app, main.BTN_MENU[1])
    running = app.timer.running
    app.on_key(pygame.K_s)               # 's' vira chute da forca, não pula
    app.on_key(pygame.K_r)
    assert app.timer.running == running and app.timer.phase == "break"


def test_longest_word_fits_the_panel(app):
    start_break(app)
    click(app, main.BTN_MENU[1])
    longest = max(act.WORDS, key=len)
    app.game = act.Hangman(word=longest)
    app.draw()
    row = pygame.Rect(0, 100, main.WIDTH, 26)
    edge = [app.screen.get_at((x, y))[:3] != main.BG
            and app.screen.get_at((x, y))[:3] != main.PANEL
            for x in (main.PANEL_RECT.x + 4, main.PANEL_RECT.right - 6)
            for y in range(row.top, row.bottom)]
    assert not any(edge)                 # nada encosta nas bordas
