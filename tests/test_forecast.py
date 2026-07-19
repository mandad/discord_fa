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


def test_prediction_embed_no_crossref_section_but_keeps_kp_field(ship, grid, kp_rows):
    e, _ = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4,
                                           gi_daily={"2026-06-25": 4})
    names = [f.name for f in e.fields]
    assert not any("cross-reference" in n.lower() for n in names)   # section removed
    assert any("Kp ≥ 4" in n for n in names)
    # the GI link now lives under the Predicted viewline field
    viewline = next(f.value for f in e.fields if "viewline" in f.name.lower())
    assert "gi.alaska.edu/monitors/aurora-forecast" in viewline


def test_prediction_embed_attaches_viewline_bytes(ship, grid, kp_rows):
    # Bytes are attached (attachment://) so each daily post keeps its own copy — embedding the
    # static NOAA URL made Discord's media cache render one (often stale) image on every post.
    e, f = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4,
                                           viewline_img=b"\x89PNG_fake")
    assert f is not None and f.filename == "tonight_viewline.png"
    assert e.image.url == "attachment://tonight_viewline.png"
    viewline = next(fl.value for fl in e.fields if "viewline" in fl.name.lower())
    assert swpc.NOAA_AURORA_DASHBOARD in viewline and "UAF GI forecast" in viewline


def test_prediction_embed_url_fallback_when_no_bytes(ship, grid, kp_rows):
    e, f = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4)
    assert f is None
    assert e.image.url == swpc.NOAA_VIEWLINE["tonight"]


def test_prediction_embed_has_dark_hours_field(ship, grid, kp_rows):
    e, _ = forecast.build_prediction_embed(ship, kp_rows, grid, "2026-06-23T16:07:00Z", 4)
    assert any("Dark hours" in f.name for f in e.fields)


def test_alert_embed_image_footer_no_crossref(ship, kp_rows):
    windows = [r for r in kp_rows if r["kind"] == "predicted" and r["kp"] >= 4]
    e = forecast.build_alert_embed(windows, ship, kp_rows, {"2026-06-25": 4}, 4)
    assert e.image.url.endswith("Alaska_5.png")   # peak Kp among windows is 5
    assert "Kp 5" in e.footer.text
    assert not any("cross-reference" in f.name.lower() for f in e.fields)   # section removed


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


def test_noaa_viewline_embeds_attach_bytes():
    imgs = {"tonight": b"png1", "tomorrow night": b"png2"}
    embeds, files = forecast.noaa_viewline_embeds(imgs)
    assert len(embeds) == 2 and len(files) == 2
    assert {e.image.url for e in embeds} == {"attachment://tonight_viewline.png",
                                             "attachment://tomorrow_night_viewline.png"}
    assert {f.filename for f in files} == {"tonight_viewline.png", "tomorrow_night_viewline.png"}
    titles = " ".join(e.title for e in embeds).lower()
    assert "tonight" in titles and "tomorrow" in titles


def test_noaa_viewline_embeds_url_fallback():
    embeds, files = forecast.noaa_viewline_embeds(None)
    assert files == []
    assert {e.image.url for e in embeds} == set(swpc.NOAA_VIEWLINE.values())


def test_noaa_viewline_embeds_partial_fallback():
    # one fetch failed -> that embed falls back to the URL, the other still attaches
    embeds, files = forecast.noaa_viewline_embeds({"tonight": b"png1", "tomorrow night": None})
    assert len(files) == 1 and files[0].filename == "tonight_viewline.png"
    urls = {e.image.url for e in embeds}
    assert "attachment://tonight_viewline.png" in urls
    assert swpc.NOAA_VIEWLINE["tomorrow night"] in urls
