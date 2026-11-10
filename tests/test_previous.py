"""Previous Wallpaper: step back through what was shown this run."""
import pytest

import wallpaper_changer as wc


@pytest.fixture
def app(monkeypatch, tmp_path):
    app = wc.WallSwapApp()
    app.shown = []
    app.notes = []
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: app.shown.append(path))
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setattr(wc, "is_fullscreen_app_running", lambda: False)
    monkeypatch.setattr(wc.settings, "reload", lambda: True)
    monkeypatch.setattr(app, "notify", lambda message, title="WallSwap": app.notes.append(message))
    counter = iter(range(1000))

    def new_wallpaper():
        path = tmp_path / f"w{next(counter)}.jpg"
        path.write_bytes(b"x")
        return wc.Wallpaper(str(path), "wallhaven", path.stem)

    monkeypatch.setattr(wc, "get_new_wallpaper", new_wallpaper)
    return app


def _titles(app):
    return [w.title for w in app.history]


def test_previous_steps_back_one_at_a_time(app):
    for _ in range(3):
        assert app._change_wallpaper() == "set"
    assert (app.current.title, _titles(app)) == ("w2", ["w0", "w1"])

    app._previous_wallpaper()
    assert (app.current.title, _titles(app)) == ("w1", ["w0"])
    app._previous_wallpaper()
    assert (app.current.title, _titles(app)) == ("w0", [])
    assert app.shown[-1].endswith("w0.jpg")

    app._previous_wallpaper()
    assert app.current.title == "w0"
    assert app.notes == ["There's no earlier wallpaper to go back to."]


def test_next_after_previous_is_a_new_wallpaper_not_the_one_left(app):
    for _ in range(2):
        app._change_wallpaper()
    app._previous_wallpaper()  # back on w0; w1 is not kept as a "forward"
    app._change_wallpaper()
    assert (app.current.title, _titles(app)) == ("w2", ["w0"])


def test_previous_skips_a_wallpaper_whose_file_is_gone(app, tmp_path):
    for _ in range(3):
        app._change_wallpaper()
    (tmp_path / "w1.jpg").unlink()
    app._previous_wallpaper()
    assert (app.current.title, _titles(app)) == ("w0", [])


def test_history_keeps_only_the_newest(app):
    for _ in range(wc.HISTORY_LENGTH + 5):
        app._change_wallpaper()
    assert len(app.history) == wc.HISTORY_LENGTH
    assert app.history[0].title == "w4"


def test_previous_restarts_the_interval_and_clears_a_pending_retry(app):
    app._change_wallpaper()
    app._change_wallpaper()
    app.elapsed, app.retry_after, app.failures = 500, 60, 3
    app._previous_wallpaper()
    assert (app.elapsed, app.retry_after, app.failures) == (0, None, 0)


def test_a_failed_change_adds_nothing_to_the_history(app, monkeypatch):
    app._change_wallpaper()
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: (_ for _ in ()).throw(OSError("refused")))
    assert app._change_wallpaper() == "failed"
    assert (app.current.title, _titles(app)) == ("w0", [])
