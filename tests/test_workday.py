import pygame
import pytest

import main
import workday as wd
from robot import BREAK, FOCUS

T = (480, 720, 780, 1020)      # 08:00 12:00 13:00 17:00


def test_segments():
    assert wd.segment(T, 479) == wd.BEFORE
    assert wd.segment(T, 480) == wd.MORNING
    assert wd.segment(T, 719.9) == wd.MORNING
    assert wd.segment(T, 720) == wd.LUNCH
    assert wd.segment(T, 780) == wd.AFTERNOON
    assert wd.segment(T, 1020) == wd.AFTER


def test_block_end_and_next_event():
    assert wd.block_end(T, wd.MORNING) == 720
    assert wd.block_end(T, wd.AFTERNOON) == 1020
    assert wd.next_event(T, wd.LUNCH, 730) == 780
    assert wd.next_event(T, wd.AFTER, 1100) == 480 + 1440


def test_worked_remaining_skips_lunch():
    assert wd.worked_remaining(T, 0) == 8 * 3600
    assert wd.worked_remaining(T, 660) == (60 + 240) * 60
    assert wd.worked_remaining(T, 740) == 240 * 60       # no almoço
    assert wd.worked_remaining(T, 1100) == 0


def test_day_progress():
    assert wd.day_progress(T, 400) == 0
    assert wd.day_progress(T, 720) == pytest.approx(0.5)
    assert wd.day_progress(T, 2000) == 1


def test_shift_pushes_neighbours():
    assert wd.shift(T, 0, 60) == (540, 720, 780, 1020)
    assert wd.shift(T, 1, 60) == (480, 780, 795, 1020)   # empurra a volta
    assert wd.shift(T, 3, -15) == (480, 720, 780, 1005)
    assert wd.shift(T, 2, -60) == (480, 705, 720, 1020)  # puxa o almoço


def test_shift_rejects_leaving_the_day():
    assert wd.shift((0, 100, 200, 300), 0, -15) == (0, 100, 200, 300)
    last = (480, 720, 780, 1439)
    assert wd.shift(last, 3, 15) == last


def test_valid_times():
    assert wd.valid_times(list(T))
    assert not wd.valid_times((480, 480, 780, 1020))
    assert not wd.valid_times((480, 720, 780))
    assert not wd.valid_times(None)


def test_formats():
    assert wd.format_clock(485) == "08:05"
    assert wd.format_hm(4 * 3600 + 12 * 60) == "4h12"
    assert wd.format_countdown(3900) == "1h05"
    assert wd.format_countdown(125) == "02:05"


# --- integração com a janela ---
@pytest.fixture
def app():
    window = main.App(focus_secs=25 * 60, break_secs=5 * 60, opaque=True,
                      persist=False, setup=True, times=T)
    window.clock_now = 600.0
    window.now = lambda: window.clock_now
    yield window
    pygame.quit()


def click(window, rect):
    window.on_release(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=rect.center))


def test_setup_screen_renders_and_starts_day(app):
    app.reveal = 1.0
    app.draw()
    click(app, main.BTN_START)
    assert not app.setup_open and app.schedule == T
    assert app.duty == wd.MORNING
    app.draw()


def test_setup_buttons_adjust_times(app):
    y = main.TIME_ROWS[0][1]
    plus_hour = next(b for b in main.TIME_BUTTONS if b[0] == "+1h")
    click(app, pygame.Rect(plus_hour[2], y, plus_hour[3], main.TIME_ROW_H))
    assert app.draft_times[0] == 540


def test_free_mode_has_no_schedule(app):
    click(app, main.BTN_FREE)
    assert app.schedule is None and app.on_duty()


def begin_day(app):
    app.reveal = 1.0
    click(app, main.BTN_START)


def test_focus_is_capped_at_lunch(app):
    app.clock_now = 700.0            # 11:40: faltam 20 min para o almoço
    begin_day(app)
    assert app.timer.running and app.timer.duration == 20 * 60
    assert app.timer.remaining == 20 * 60


def test_focus_not_capped_when_there_is_room(app):
    app.clock_now = 500.0
    begin_day(app)
    assert app.timer.duration == 25 * 60


def test_timer_stops_at_lunch_and_returns_after(app):
    app.clock_now = 715.0
    begin_day(app)
    app.update(1.0)
    assert app.timer.running
    app.clock_now = 720.0            # deu meio-dia
    app.update(1.0)
    assert app.duty == wd.LUNCH and not app.on_duty()
    assert not app.timer.running and app.alert > 0
    elapsed = app.timer.elapsed
    app.update(5.0)                  # no almoço o timer não corre
    assert app.timer.elapsed == elapsed
    app.primary()                    # clique é ignorado
    assert not app.timer.running
    app.reveal = 1.0
    app.draw()
    app.clock_now = 780.0
    app.update(1.0)
    assert app.duty == wd.AFTERNOON and app.timer.phase == FOCUS
    assert app.joy > 0 and app.timer.running       # já volta contando


def test_end_of_day_stops_timer(app):
    app.clock_now = 1019.0
    begin_day(app)
    app.clock_now = 1020.0
    app.update(1.0)
    assert app.duty == wd.AFTER and not app.on_duty()
    app.reveal = 0.0
    app.draw()
    app.reveal = 1.0
    app.draw()


def test_opening_during_lunch_shows_off_duty_without_alert(app):
    app.clock_now = 740.0
    begin_day(app)
    assert app.duty == wd.LUNCH and app.alert == 0
    label, status, button, wait = app.off_duty_info()
    assert (label, button) == ("ALMOÇO", "volta 13:00")
    assert wait == pytest.approx(40 * 60)


def test_cycles_survive_day_blocks(app):
    app.clock_now = 500.0
    begin_day(app)
    app.skip()
    assert app.timer.cycles == 1
    app.clock_now = 730.0
    app.update(0.1)
    app.clock_now = 790.0
    app.update(0.1)
    assert app.timer.cycles == 1


def test_jornada_button_reachable_from_settings(app):
    click(app, main.BTN_FREE)
    app.reveal = 1.0
    click(app, main.BTN_GEAR)
    app.draw()
    click(app, main.BTN_JORNADA)
    assert app.setup_open and not app.settings_open
    app.draw()


def test_confirm_persists_workday(app, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "PATH", str(tmp_path / "c.json"))
    app.persist = True
    app.clock_now = 500.0
    begin_day(app)
    assert config.load()["workday"] == list(T)


# --- digitar o horário ---
def test_parse_clock():
    assert wd.parse_clock("1312") == 13 * 60 + 12
    assert wd.parse_clock("912") == 9 * 60 + 12
    assert wd.parse_clock("13:12") == 13 * 60 + 12
    assert wd.parse_clock("9") == 9 * 60
    assert wd.parse_clock("13") == 13 * 60
    assert wd.parse_clock("") is None
    assert wd.parse_clock("2460") is None
    assert wd.parse_clock("1275") is None
    assert wd.parse_clock("24") is None


def test_set_time_pushes_neighbours():
    assert wd.set_time(T, 2, 13 * 60 + 12) == (480, 720, 792, 1020)
    assert wd.set_time(T, 1, 13 * 60 + 12) == (480, 792, 807, 1020)


def box(row):
    return main.TIME_BOX.move(0, main.TIME_ROWS[row][1])


def type_keys(app, *keys):
    for key in keys:
        app.on_key(key)


def test_type_time_in_field(app):
    click(app, box(2))                      # campo "volta"
    assert app.editing == 2
    app.draw()
    type_keys(app, pygame.K_1, pygame.K_3, pygame.K_1, pygame.K_2)
    app.draw()
    type_keys(app, pygame.K_RETURN)
    assert app.editing is None and app.setup_open
    assert app.draft_times == (480, 720, 792, 1020)


def test_backspace_and_limit(app):
    click(app, box(0))
    type_keys(app, pygame.K_0, pygame.K_9, pygame.K_3, pygame.K_0, pygame.K_5)
    assert app.edit_text == "0930"
    type_keys(app, pygame.K_BACKSPACE, pygame.K_BACKSPACE)
    assert app.edit_text == "09"
    type_keys(app, pygame.K_KP1, pygame.K_KP5, pygame.K_RETURN)
    assert app.draft_times[0] == 9 * 60 + 15


def test_invalid_time_keeps_previous(app):
    click(app, box(0))
    type_keys(app, pygame.K_9, pygame.K_9, pygame.K_9, pygame.K_9,
              pygame.K_RETURN)
    assert app.draft_times == T


def test_escape_cancels_edit_without_quitting(app):
    click(app, box(1))
    type_keys(app, pygame.K_1, pygame.K_1, pygame.K_ESCAPE)
    assert app.editing is None and app.running and app.draft_times == T


def test_clicking_elsewhere_commits(app):
    click(app, box(2))
    type_keys(app, pygame.K_1, pygame.K_3, pygame.K_1, pygame.K_2)
    click(app, main.BTN_START)
    assert app.schedule == (480, 720, 792, 1020) and app.editing is None


def test_switching_field_commits_previous(app):
    click(app, box(0))
    type_keys(app, pygame.K_9, pygame.K_3, pygame.K_0)
    click(app, box(3))
    assert app.draft_times[0] == 9 * 60 + 30 and app.editing == 3


def test_confirming_the_day_starts_counting_right_away(app):
    app.clock_now = 500.0
    begin_day(app)
    assert app.timer.running and app.timer.remaining == 25 * 60
    app.update(10.0)
    assert app.timer.remaining == pytest.approx(25 * 60 - 10)


def test_no_autostart_outside_work_hours(app):
    app.clock_now = 740.0            # almoço
    begin_day(app)
    assert not app.timer.running


def test_free_mode_does_not_autostart(app):
    click(app, main.BTN_FREE)
    assert not app.timer.running


# --- tempo para sair ---
def test_time_to_exit_counts_lunch():
    assert wd.time_to_exit(T, 600) == (1020 - 600) * 60      # manhã: inclui almoço
    assert wd.time_to_exit(T, 900) == (1020 - 900) * 60
    assert wd.time_to_exit(T, 1100) == 0


def test_format_until():
    assert wd.format_until(104 * 60) == "1h44"
    assert wd.format_until(44 * 60 + 30) == "44 min"
    assert wd.format_until(0) == "0 min"
    assert wd.format_until(3600) == "1h00"


def test_exit_text_in_app(app):
    app.clock_now = 900.0            # 15:00, saída 17:00
    begin_day(app)
    assert app.exit_text() == "sair 17:00 · faltam 2h00"
    app.clock_now = 1030.0
    app.update(0.1)
    assert app.exit_text() == "expediente encerrado"
    app.reveal = 1.0
    app.draw()
    app.reveal = 0.0
    app.draw()


def test_exit_text_before_lunch_counts_the_lunch_break(app):
    app.clock_now = 660.0            # 11:00 -> 6h até 17:00 (com almoço)
    begin_day(app)
    assert app.exit_text() == "sair 17:00 · faltam 6h00"
