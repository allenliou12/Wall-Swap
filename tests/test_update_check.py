"""INV-18: the update check reads GitHub's latest release, compares versions and only tells the user."""
import json

import pytest
import requests

import wallpaper_changer as wc


@pytest.mark.parametrize("text, parsed", [
    ("1.2.0", (1, 2, 0, 0)),
    ("v1.2", (1, 2, 0, 0)),
    (" 2 ", (2, 0, 0, 0)),
    ("1.0.2.7", (1, 0, 2, 7)),
    ("1.2.0-beta", None),
    ("latest", None),
    ("", None),
    ("1.2.3.4.5", None),
    (None, None),
    (120, None),
])
def test_parse_version(text, parsed):
    assert wc.parse_version(text) == parsed


@pytest.mark.parametrize("latest, current, newer", [
    ("1.1.0", "1.0.2", True),
    ("1.10.0", "1.9.9", True),   # numbers, not text
    ("v2.0", "1.9.9", True),
    ("1.0.2", "1.0.2", False),
    ("1.0", "1.0.0", False),
    ("1.0.1", "1.0.2", False),   # an older release never counts as an update
    ("nonsense", "1.0.2", False),
])
def test_newer_version(latest, current, newer):
    assert wc.newer_version(latest, current) is newer


def _github(monkeypatch, reply):
    asked = []

    def fake_get(url, **kw):
        asked.append((url, kw))
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(wc, "safe_get", fake_get)
    return asked


def test_latest_release_asks_only_githubs_latest_release_address(monkeypatch):
    asked = _github(monkeypatch, wc.Fetched(200, json.dumps({"tag_name": "v9.9.9", "html_url": "https://evil"}).encode()))
    assert wc.latest_release() == "9.9.9"
    assert asked == [(wc.UPDATE_API_URL, {"max_bytes": wc.MAX_API_BYTES})]
    wc._check_url(wc.UPDATE_API_URL)  # an allowed https address (INV-1)
    with pytest.raises(wc.DownloadError):
        wc._check_url("https://github.com.evil.example/repos/x")


@pytest.mark.parametrize("reply", [
    wc.Fetched(404, b"{}"),
    wc.Fetched(200, b"not json"),
    wc.Fetched(200, json.dumps({"name": "no tag"}).encode()),
    wc.Fetched(200, json.dumps({"tag_name": "nightly"}).encode()),
    wc.Fetched(200, json.dumps({"tag_name": 5}).encode()),
    requests.ConnectionError("offline"),
])
def test_latest_release_raises_on_anything_odd(monkeypatch, reply):
    _github(monkeypatch, reply)
    with pytest.raises(Exception):
        wc.latest_release()


@pytest.fixture
def app(monkeypatch):
    wc.UPDATE_NOTIFIED_FILE.unlink(missing_ok=True)
    app = wc.WallSwapApp()
    app.notes = []
    monkeypatch.setattr(app, "notify", lambda message, title="WallSwap": app.notes.append(message))
    opened = []
    monkeypatch.setattr(wc.webbrowser, "open", opened.append)
    app.opened = opened
    app.dialogs = []      # (text, yes_no) of every dialog shown
    app.click_yes = False  # what the user clicks in a Yes/No dialog

    def fake_box(text, title="WallSwap", yes_no=False):
        app.dialogs.append((text, yes_no))
        return app.click_yes if yes_no else True

    monkeypatch.setattr(wc, "message_box", fake_box)
    yield app
    wc.UPDATE_NOTIFIED_FILE.unlink(missing_ok=True)


def _latest(monkeypatch, version):
    def fake():
        if isinstance(version, Exception):
            raise version
        return version
    monkeypatch.setattr(wc, "latest_release", fake)


def test_an_automatic_check_tells_once_per_version(app, monkeypatch):
    _latest(monkeypatch, "99.0.0")
    app._check_for_updates(manual=False)
    assert app.update_version == "99.0.0" and len(app.notes) == 1 and "99.0.0" in app.notes[0]

    app._check_for_updates(manual=False)  # the next day: the tray line stays, no second pop-up
    assert app.update_version == "99.0.0" and len(app.notes) == 1

    _latest(monkeypatch, "99.1.0")        # a newer one still: told again
    app._check_for_updates(manual=False)
    assert app.update_version == "99.1.0" and len(app.notes) == 2


def test_a_manual_check_always_answers_in_a_dialog_not_a_notification(app, monkeypatch):
    """Notifications can be switched off in Windows; an answer the user asked for must still be seen."""
    _latest(monkeypatch, "99.0.0")
    app._check_for_updates(manual=True)
    app._check_for_updates(manual=True)
    assert len(app.dialogs) == 2 and all(yes_no for _text, yes_no in app.dialogs)
    assert "99.0.0 is available" in app.dialogs[0][0]
    assert app.opened == []  # clicked No: nothing opens

    app.click_yes = True
    app._check_for_updates(manual=True)
    assert app.opened == [wc.RELEASES_URL]

    _latest(monkeypatch, wc.APP_VERSION)
    app._check_for_updates(manual=True)
    assert app.dialogs[-1] == (f"You're up to date.\n\nWallSwap {wc.APP_VERSION} is the newest version.", False)
    assert app.update_version is None

    _latest(monkeypatch, OSError("offline"))
    app._check_for_updates(manual=True)
    assert app.dialogs[-1][0].startswith("Couldn't check for updates right now.")
    assert app.notes == []  # no notifications at all for manual checks


def test_an_automatic_check_never_opens_a_dialog(app, monkeypatch):
    for version in ("99.0.0", wc.APP_VERSION, OSError("offline")):
        _latest(monkeypatch, version)
        app._check_for_updates(manual=False)
    assert app.dialogs == []


def test_a_manual_check_after_the_automatic_notice_still_answers_and_does_not_renotify(app, monkeypatch):
    _latest(monkeypatch, "99.0.0")
    app._check_for_updates(manual=False)
    app._check_for_updates(manual=True)
    app._check_for_updates(manual=False)
    assert len(app.notes) == 1 and len(app.dialogs) == 1


def test_a_second_click_while_a_check_is_open_does_nothing(app, monkeypatch):
    _latest(monkeypatch, wc.APP_VERSION)
    app.manual_update_check.acquire()  # a check is running or its dialog is open
    try:
        app._manual_update_check()
    finally:
        app.manual_update_check.release()
    assert app.dialogs == []
    app._manual_update_check()
    assert len(app.dialogs) == 1 and not app.manual_update_check.locked()


def test_if_the_dialog_cannot_be_shown_a_notification_is_tried(app, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no desktop")
    monkeypatch.setattr(wc, "message_box", broken)
    _latest(monkeypatch, wc.APP_VERSION)
    app._check_for_updates(manual=True)
    assert app.notes == [f"You're up to date.  WallSwap {wc.APP_VERSION} is the newest version."]


def test_an_automatic_check_is_silent_when_up_to_date_or_offline_and_retries_sooner(app, monkeypatch):
    _latest(monkeypatch, wc.APP_VERSION)
    app._check_for_updates(manual=False)
    _latest(monkeypatch, OSError("offline"))
    monkeypatch.setattr(wc.time, "monotonic", lambda: 1000.0)
    app.next_update_check = 1000.0 + wc.UPDATE_CHECK_SECONDS
    app._check_for_updates(manual=False)
    assert app.notes == []
    assert app.next_update_check == 1000.0 + wc.UPDATE_RETRY_SECONDS


class NoThread:
    started = 0

    def __init__(self, target, args=(), daemon=None):
        pass

    def start(self):
        NoThread.started += 1


def test_the_daily_check_runs_at_start_then_once_a_day_and_not_when_turned_off(app, monkeypatch):
    NoThread.started = 0
    monkeypatch.setattr(wc.threading, "Thread", NoThread)
    now = [5.0]
    monkeypatch.setattr(wc.time, "monotonic", lambda: now[0])
    monkeypatch.setitem(wc.settings.data, "check_for_updates", True)

    app.auto_check_for_updates()
    app.auto_check_for_updates()
    assert NoThread.started == 1
    now[0] += wc.UPDATE_CHECK_SECONDS - 1
    app.auto_check_for_updates()
    assert NoThread.started == 1
    now[0] += 1
    app.auto_check_for_updates()
    assert NoThread.started == 2

    monkeypatch.setitem(wc.settings.data, "check_for_updates", False)
    now[0] += wc.UPDATE_CHECK_SECONDS * 3
    app.auto_check_for_updates()
    assert NoThread.started == 2


def test_the_update_line_opens_the_fixed_releases_page(app):
    app.open_releases()
    assert app.opened == [wc.RELEASES_URL]
    assert wc.RELEASES_URL.startswith("https://github.com/allenliou12/Wall-Swap/")


def test_the_setting_defaults_on_and_the_window_can_turn_it_off():
    before = wc.settings.snapshot()
    assert wc.DEFAULT_SETTINGS["check_for_updates"] is True
    patch = wc.settings_patch(before, {**before, "check_for_updates": False})
    assert patch["set"] == [(("check_for_updates",), False)]
