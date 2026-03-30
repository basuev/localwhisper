import shutil

import pytest

from scripts.generate_app_icon import (
    ICONSET_SPECS,
    _draw_blob_bitmap,
    _write_png,
    build_icns,
)


@pytest.mark.parametrize(
    ("base_size", "scale"),
    ICONSET_SPECS,
    ids=[f"{b}x{b}{'@2x' if s == 2 else ''}" for b, s in ICONSET_SPECS],
)
def test_bitmap_pixel_dimensions(base_size, scale):
    pixel_size = base_size * scale
    bitmap = _draw_blob_bitmap(pixel_size)
    assert bitmap.pixelsWide() == pixel_size
    assert bitmap.pixelsHigh() == pixel_size


def test_write_png_creates_valid_file(tmp_path):
    bitmap = _draw_blob_bitmap(32)
    out = tmp_path / "icon.png"
    _write_png(bitmap, out)
    assert out.exists()
    assert out.stat().st_size > 0


@pytest.mark.skipif(shutil.which("iconutil") is None, reason="iconutil not found")
def test_build_icns_end_to_end(tmp_path):
    icns = tmp_path / "App.icns"
    build_icns(icns)
    assert icns.exists()
    assert icns.stat().st_size > 0
