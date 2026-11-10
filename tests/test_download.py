"""Saving a download: a JPEG is kept as it is, anything else becomes a JPEG, a broken file is refused."""
import io

import pytest
from PIL import Image

import wallpaper_changer as wc


@pytest.fixture(autouse=True)
def no_cleanup(monkeypatch):
    monkeypatch.setattr(wc, "cleanup_old_wallpapers", lambda: None)
    yield
    for path in wc.WALLPAPER_DIR.glob("wallswap_*.jpg"):
        path.unlink()
    (wc.WALLPAPER_DIR / "_temp_test.jpg").unlink(missing_ok=True)


def _bytes(fmt: str, mode: str = "RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mode, (64, 36), 128 if mode == "L" else None).save(out, fmt, **({"quality": 60} if fmt == "JPEG" else {}))
    return out.getvalue()


def _download(data: bytes):
    tmp = wc.WALLPAPER_DIR / "_temp_test.jpg"

    def fetch():
        tmp.write_bytes(data)
        return wc.Wallpaper(str(tmp), "wallhaven", "t", key="k")

    return wc.download_wallpaper(fetch, attempts=1), tmp


@pytest.mark.parametrize("mode", ["RGB", "L"])
def test_a_jpeg_is_kept_byte_for_byte(mode):
    data = _bytes("JPEG", mode)
    saved, tmp = _download(data)
    assert open(saved.path, "rb").read() == data
    assert wc.is_own_download(wc.Path(saved.path)) and not tmp.exists()
    assert saved.key == "k"


def test_a_png_is_converted_to_jpeg():
    saved, tmp = _download(_bytes("PNG", "RGBA"))
    with Image.open(saved.path) as img:
        assert (img.format, img.mode) == ("JPEG", "RGB")
    assert not tmp.exists()


def test_a_cmyk_jpeg_is_converted_so_windows_can_show_it():
    saved, _tmp = _download(_bytes("JPEG", "CMYK"))
    with Image.open(saved.path) as img:
        assert (img.format, img.mode) == ("JPEG", "RGB")


def test_a_cut_off_jpeg_is_refused_and_leaves_no_wallpaper_file():
    data = _bytes("JPEG")
    saved, _tmp = _download(data[:len(data) // 2])
    assert saved is None
    assert list(wc.WALLPAPER_DIR.glob("wallswap_*.jpg")) == []
