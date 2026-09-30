import pygame
import pytest

import config
import main


def test_load_defaults_when_missing(tmp_path):
    assert config.load(tmp_path / "nope.json") == config.DEFAULTS


def test_load_defaults_when_corrupt(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert config.load(path) == config.DEFAULTS


def test_save_roundtrip_and_clamp(tmp_path):
    path = tmp_path / "c.json"
    saved = config.save({"focus_min": 999, "break_min": 0}, path)
    assert (saved["focus_min"], saved["break_min"]) == (180, 1)
    assert config.load(path) == saved


def test_save_merges_and_keeps_other_keys(tmp_path):
    path = tmp_path / "c.json"
    config.save({"focus_min": 40}, path)
    config.save({"workday": [540, 720, 780, 1080]}, path)
    data = config.load(path)
    assert data["focus_min"] == 40 and data["workday"] == [540, 720, 780, 1080]


def test_invalid_workday_falls_back_per_field(tmp_path):
    path = tmp_path / "c.json"
    path.write_text('{"focus_min": 50, "workday": [900, 600, 700, 800]}')
    data = config.load(path)
    assert data["focus_min"] == 50
    assert data["workday"] == config.DEFAULTS["workday"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PATH", str(tmp_path / "c.json"))
    window = main.App(focus_secs=25 * 60, break_secs=5 * 60, opaque=True,
                      persist=False)
    window.reveal = 1.0
    yield window
    pygame.quit()


def click(window, rect):
    window.on_release(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=rect.center))


def step_button(step, row):
    y = dict((k, y) for k, _, y in main.SETTING_ROWS)[row]
    for _, s, x, w in main.STEP_BUTTONS:
        if s == step:
            return main.step_rect(x, w, y)


def test_gear_opens_and_cancel_closes(app):
    click(app, main.BTN_GEAR)
    assert app.settings_open and app.draft == {
        "focus_min": 25, "break_min": 5, "activities": True}
    app.draw()
    click(app, main.BTN_CANCEL)
    assert not app.settings_open


def test_adjust_and_save_resets_timer(app):
    app.timer.toggle()
    app.timer.tick(30)
    click(app, main.BTN_GEAR)
    click(app, step_button(5, "focus_min"))
    click(app, step_button(-1, "break_min"))
    assert app.draft == {"focus_min": 30, "break_min": 4, "activities": True}
    click(app, main.BTN_SAVE)
    assert not app.settings_open
    assert (app.timer.focus_secs, app.timer.break_secs) == (1800, 240)
    assert app.timer.elapsed == 0 and not app.timer.running


def test_cancel_discards_changes(app):
    click(app, main.BTN_GEAR)
    click(app, step_button(5, "focus_min"))
    click(app, main.BTN_CANCEL)
    assert app.timer.focus_secs == 25 * 60


def test_values_stay_in_limits(app):
    click(app, main.BTN_GEAR)
    for _ in range(10):
        click(app, step_button(-5, "break_min"))
    assert app.draft["break_min"] == 1


def test_save_persists_when_enabled(app, tmp_path):
    app.persist = True
    click(app, main.BTN_GEAR)
    click(app, step_button(5, "focus_min"))
    click(app, main.BTN_SAVE)
    assert config.load(config.PATH)["focus_min"] == 30
