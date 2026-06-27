import re

import forecast
import swpc

_UTC_Z = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


def _text(embed):
    return " ".join([embed.description or ""]
                    + [f.name + " " + f.value for f in embed.fields]
                    + [embed.footer.text or ""])


def test_observed_embed_no_motion_and_local_times(ship, grid, kp_rows):
    obs = swpc.latest_observed_kp(kp_rows)
    e = forecast.build_observed_embed(ship, obs, grid, "2026-06-23T16:07:00Z")
    assert "SOG" not in e.description and "COG" not in e.description
    blob = _text(e)
    assert not _UTC_Z.search(blob)        # times converted to local, no bare UTC 'Z'
    assert "AK" in e.footer.text          # local tz abbreviation


def test_prediction_embed_has_crossref_and_kp_field(ship, grid, kp_rows):
    e = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4,
                                        gi_daily={"2026-06-25": 4})
    names = [f.name for f in e.fields]
    assert any("cross-reference" in n.lower() for n in names)
    assert any("Kp ≥ 4" in n for n in names)
    xref = next(f.value for f in e.fields if "cross-reference" in f.name.lower())
    assert "GI Kp 4" in xref and "gi.alaska.edu" in xref


def test_prediction_embed_has_gi_viewline_image_and_noaa_dashboard_link(ship, grid, kp_rows):
    e = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4)
    # GI predicted Alaska viewline attached as the embed image (peak predicted Kp 5 -> Alaska_5).
    assert e.image.url == "https://www.gi.alaska.edu/modules/custom/aurora-forecast/images/idl_graphics/ak/Alaska_5.png"
    blob = " ".join(f.value for f in e.fields)
    assert swpc.NOAA_AURORA_DASHBOARD in blob


def test_prediction_embed_has_dark_hours_field(ship, grid, kp_rows):
    e = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4)
    assert any("Dark hours" in f.name for f in e.fields)


def test_alert_embed_image_crossref_footer(ship, kp_rows):
    windows = [r for r in kp_rows if r["kind"] == "predicted" and r["kp"] >= 4]
    e = forecast.build_alert_embed(windows, ship, kp_rows, {"2026-06-25": 4}, 4)
    assert e.image.url.endswith("Alaska_5.png")   # peak Kp among windows is 5
    assert "Kp 5" in e.footer.text
    assert any("cross-reference" in f.name.lower() for f in e.fields)


def test_next_window_line_with_window(ship, kp_rows):
    line = forecast.next_window_line(kp_rows, ship, 4)
    assert line.startswith("Kp 4")          # earliest window >= 4
    assert "AK" in line                       # local time shown
    assert ("dark at ship" in line) or ("daylight at ship" in line)


def test_next_window_line_none(ship, kp_rows):
    assert forecast.next_window_line(kp_rows, ship, 9).startswith("None ≥ Kp 9")


def test_swpc_forecast_embed_attaches_bytes():
    e, f = forecast.swpc_forecast_embed(b"\xff\xd8\xffjpeg")
    assert f is not None and f.filename == "swpc_aurora_forecast.jpg"
    assert e.image.url == "attachment://swpc_aurora_forecast.jpg"


def test_swpc_forecast_embed_url_fallback():
    e, f = forecast.swpc_forecast_embed(None)
    assert f is None
    assert e.image.url == swpc.NOAA_OVATION_IMAGE


def test_noaa_viewline_embeds():
    embeds = forecast.noaa_viewline_embeds()
    assert len(embeds) == 2
    urls = {e.image.url for e in embeds}
    assert urls == set(swpc.NOAA_VIEWLINE.values())
    titles = " ".join(e.title for e in embeds).lower()
    assert "tonight" in titles and "tomorrow" in titles
