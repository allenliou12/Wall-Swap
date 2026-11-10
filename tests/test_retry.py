"""INV-14: a change that was skipped or failed is tried again soon, not a whole interval later."""
import pytest

import wallpaper_changer as wc


def test_a_set_wallpaper_goes_back_to_the_normal_interval():
    assert wc.retry_plan("set", 3) == (None, 0)


def test_a_skipped_change_retries_every_minute_and_never_slows_down():
    assert wc.retry_plan("skipped", 0) == (wc.RETRY_SECONDS, 0)
    assert wc.retry_plan("skipped", 99) == (wc.RETRY_SECONDS, 99)


def test_failed_changes_retry_fast_five_times_then_slowly():
    failures, waits = 0, []
    for _ in range(wc.FAST_RETRIES + 2):
        wait, failures = wc.retry_plan("failed", failures)
        waits.append(wait)
    assert waits == [wc.RETRY_SECONDS] * wc.FAST_RETRIES + [wc.SLOW_RETRY_SECONDS] * 2


def test_nothing_to_fetch_goes_back_to_the_normal_interval():
    assert wc.retry_plan("nothing", 2) == (None, 0)


@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    app.outcomes = []  # what each change attempt will do, in order
    app.attempts = 0

    def change():
        app.attempts += 1
        return app.outcomes.pop(0)

    monkeypatch.setattr(app, "_do_change_wallpaper", change)
    monkeypatch.setitem(wc.settings.data, "interval_minutes", 30)
    return app


def _run(app, seconds: int):
    for _ in range(seconds // 5):
        app.tick(5)


def test_a_game_in_front_is_checked_again_each_minute_until_it_is_gone(app):
    app.outcomes = ["skipped", "skipped", "set"]
    _run(app, 30 * 60)
    assert app.attempts == 1
    _run(app, 60)
    assert app.attempts == 2
    _run(app, 60)
    assert app.attempts == 3 and app.retry_after is None
    _run(app, 30 * 60 - 5)
    assert app.attempts == 3  # back on the normal interval, counted from the change that worked
    app.outcomes = ["set"]
    _run(app, 5)
    assert app.attempts == 4


def test_a_failed_first_change_is_retried_after_a_minute(app):
    app.outcomes = ["failed", "set"]
    assert app._change_wallpaper() == "failed"  # what timer_loop does at startup
    _run(app, 55)
    assert app.attempts == 1
    _run(app, 5)
    assert app.attempts == 2 and app.failures == 0


def test_nothing_is_retried_while_paused(app):
    app.outcomes = ["failed"]
    app._change_wallpaper()
    app.paused = True
    _run(app, 3600)
    assert app.attempts == 1


def test_a_change_already_running_leaves_the_plan_alone(app):
    app.retry_after, app.failures = 60, 2
    app.change_lock.acquire()
    try:
        assert app._change_wallpaper() == "busy"
    finally:
        app.change_lock.release()
    assert (app.retry_after, app.failures, app.attempts) == (60, 2, 0)


@pytest.mark.parametrize("paused, outcome, remaining, text", [
    (False, "set", 30 * 60, "Next change in 30 min"),
    (False, None, 61, "Next change in 2 min"),      # rounded up
    (False, "set", 5, "Next change in 1 min"),      # never 0
    (False, "set", 0, "Next change in 1 min"),
    (False, "set", 2 * 60 * 60, "Next change in 2 h"),
    (False, "nothing", 80 * 60, "Next change in 1 h 20 min"),
    (False, "skipped", 60, "Waiting for the fullscreen app to close"),
    (False, "failed", 10 * 60, "Trying again in 10 min"),
    (True, "skipped", 60, "Paused"),
])
def test_the_menu_line_says_when_the_next_change_is_or_why_it_waits(paused, outcome, remaining, text):
    assert wc.next_change_text(paused, outcome, remaining) == text


def test_the_status_counts_down_and_names_a_fullscreen_wait(app):
    app.outcomes = ["skipped", "set"]
    assert app.status_text() == "Next change in 30 min"
    _run(app, 10 * 60)
    assert app.status_text() == "Next change in 20 min"
    _run(app, 20 * 60)
    assert app.status_text() == "Waiting for the fullscreen app to close"
    _run(app, 60)
    assert app.status_text() == "Next change in 30 min"
    app.paused = True
    assert app.status_text() == "Paused"


def test_the_menu_is_rebuilt_when_the_minute_shown_changes_but_not_while_a_menu_is_open(app, monkeypatch):
    rebuilt = []
    monkeypatch.setattr(app, "refresh_menu", lambda: (rebuilt.append(app.status_text()),
                                                      setattr(app, "status_shown", app.status_text())))
    monkeypatch.setattr(wc, "menu_is_open", lambda: False)
    _run(app, 60)
    assert rebuilt == ["Next change in 30 min", "Next change in 29 min"]
    monkeypatch.setattr(wc, "menu_is_open", lambda: True)
    _run(app, 120)
    assert len(rebuilt) == 2  # an open menu is left alone
    monkeypatch.setattr(wc, "menu_is_open", lambda: False)
    _run(app, 5)
    assert rebuilt[-1] == "Next change in 27 min"
