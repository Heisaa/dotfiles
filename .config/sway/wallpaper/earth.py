"""Land/ocean mask of the earth at 0.5 degree resolution (720x360, equirectangular),
derived from Natural Earth 1:110m land polygons (public domain). Packed 1 bit per
cell, zlib, base64: ~5.6 KB. Regenerate with `python3 earth.py ne_110m_land.geojson`."""

import base64
import zlib

W, H = 720, 360

_BLOB = (
    "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"
)

_bits = None


def _mask():
    global _bits
    if _bits is None:
        _bits = zlib.decompress(base64.b64decode(_BLOB))
    return _bits


def is_land(lat, lon):
    """True if the cell containing (lat, lon) in degrees is land."""
    x = int((lon + 180.0) % 360.0 * W / 360.0)
    y = min(H - 1, max(0, int((90.0 - lat) * H / 180.0)))
    i = y * W + x
    return bool(_mask()[i >> 3] & (0x80 >> (i & 7)))


if __name__ == "__main__":
    # Rebuild _BLOB from a Natural Earth land GeoJSON (needs pycairo only).
    import json
    import sys
    import textwrap
    import cairo

    gj = json.load(open(sys.argv[1]))
    surf = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
    cr = cairo.Context(surf)
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    for f in gj["features"]:
        g = f["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            for ring in poly:
                for i, (lon, lat) in enumerate(ring):
                    (cr.move_to if i == 0 else cr.line_to)((lon + 180) * W / 360, (90 - lat) * H / 180)
                cr.close_path()
            cr.set_source_rgba(0, 0, 0, 1)
            cr.fill()
    surf.flush()
    buf, stride = surf.get_data(), surf.get_stride()
    bits = bytearray(W * H // 8)
    for y in range(H):
        for x in range(W):
            if buf[y * stride + x] > 127:
                i = y * W + x
                bits[i >> 3] |= 0x80 >> (i & 7)
    blob = base64.b64encode(zlib.compress(bytes(bits), 9)).decode()
    print("_BLOB = (")
    for line in textwrap.wrap(blob, 96):
        print(f'    "{line}"')
    print(")")
