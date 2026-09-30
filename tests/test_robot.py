import pytest

from robot import (BREAK, BREAK_BEGUN, BREAK_DONE, CHARGING, FOCUS,
                   FOCUS_BEGUN, FOCUS_DONE, FRESH, MIN_BATTERY, OVERHEATED,
                   RobotTimer, format_time)


def make():
    return RobotTimer(focus_secs=10, break_secs=4)


def test_format_time():
    assert format_time(0) == "00:00"
    assert format_time(65) == "01:05"
    assert format_time(1500) == "25:00"
    assert format_time(-3) == "00:00"


def test_starts_idle_and_full():
    tm = make()
    assert (tm.phase, tm.running, tm.waiting) == (FOCUS, False, False)
    assert tm.battery == 100 and tm.mood == FRESH


def test_tick_does_nothing_when_stopped():
    tm = make()
    assert tm.tick(5) == []
    assert tm.elapsed == 0


def test_toggle_pauses_and_resumes():
    tm = make()
    assert tm.toggle() is None and tm.running
    tm.tick(3)
    tm.toggle()
    tm.tick(3)
    assert not tm.running and tm.elapsed == 3


def test_battery_drains_during_focus():
    tm = make()
    tm.toggle()
    tm.tick(5)
    expected = 100 + (MIN_BATTERY - 100) * 0.5
    assert tm.battery == pytest.approx(expected)


def test_focus_end_waits_for_manual_break():
    tm = make()
    tm.toggle()
    assert tm.tick(10) == [FOCUS_DONE]
    assert tm.phase == BREAK and tm.waiting and not tm.running
    assert tm.cycles == 1
    assert tm.tick(100) == []          # esperando: o tempo não corre
    assert tm.battery == pytest.approx(MIN_BATTERY)
    assert tm.mood == OVERHEATED


def test_break_starts_only_on_toggle_and_recharges():
    tm = make()
    tm.toggle()
    tm.tick(10)
    assert tm.toggle() == BREAK_BEGUN
    assert tm.mood == CHARGING
    tm.tick(2)
    assert MIN_BATTERY < tm.battery < 100
    assert tm.tick(2) == [BREAK_DONE]
    assert tm.battery == pytest.approx(100)
    assert tm.phase == FOCUS and tm.waiting


def test_next_focus_begins_on_toggle():
    tm = make()
    tm.toggle()
    tm.tick(10)
    tm.toggle()
    tm.tick(4)
    assert tm.toggle() == FOCUS_BEGUN
    assert tm.running and tm.phase == FOCUS


def test_partial_recharge_carries_into_next_focus():
    tm = make()
    tm.toggle()
    tm.tick(10)
    tm.toggle()
    tm.skip()
    assert tm.battery == pytest.approx(100)
    tm.toggle()
    tm.tick(5)
    assert tm.battery < 100


def test_skip_finishes_phase():
    tm = make()
    tm.toggle()
    assert tm.skip() == FOCUS_DONE
    assert tm.phase == BREAK and tm.waiting


def test_overshoot_clamps_elapsed():
    tm = make()
    tm.toggle()
    tm.tick(999)
    assert tm.elapsed == 0          # fase nova, zerada
    assert tm.remaining == 4


def test_reset_restores_everything():
    tm = make()
    tm.toggle()
    tm.tick(10)
    tm.reset()
    assert (tm.phase, tm.cycles, tm.battery) == (FOCUS, 0, 100)
    assert not tm.running and not tm.waiting


def test_heat_range():
    tm = make()
    assert tm.heat == 0
    tm.toggle()
    tm.tick(10)
    assert tm.heat == pytest.approx(1.0)
