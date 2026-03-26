from renderer import _weather_html

BASE_LOC = {
    "location": "Warwick, NY",
    "temp": 54,
    "condition": "Partly Cloudy",
    "high": 61,
    "low": 44,
    "sunrise": "6:52am",
    "sunset": "7:31pm",
    "alerts": [],
    "sentence": "A partly cloudy afternoon with highs in the low 60s.",
}

def test_weather_html_shows_location():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "Warwick, NY" in html

def test_weather_html_shows_high_low():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "61°" in html
    assert "44°" in html

def test_weather_html_shows_sentence():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "A partly cloudy afternoon" in html
    assert 'weather-summary' in html

def test_weather_html_omits_sentence_div_when_empty():
    loc = {**BASE_LOC, "sentence": ""}
    html = _weather_html({"locations": [loc]})
    assert "weather-summary" not in html

def test_weather_html_shows_sunrise_sunset():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "6:52am" in html
    assert "7:31pm" in html

def test_weather_html_no_rule_or_label():
    """section-rule div and section label must not appear — show_rule=False, label=None."""
    html = _weather_html({"locations": [BASE_LOC]})
    assert "section-rule" not in html
    assert "WEATHER ·" not in html

def test_weather_html_no_alert_when_empty():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "⚠" not in html

def test_weather_html_shows_alert_banner():
    loc = {**BASE_LOC, "alerts": [{
        "event": "Flood Watch",
        "expires": "Thu 6:00pm",
        "agency": "NWS Chicago",
        "url": "https://alerts.weather.gov/example",
    }]}
    html = _weather_html({"locations": [loc]})
    assert "⚠" in html
    assert "Flood Watch" in html
    assert "alerts.weather.gov" in html
    assert "Thu 6:00pm" in html
    assert "NWS Chicago" in html

def test_weather_html_alert_uses_inline_styles_not_class():
    """Alert banner has no CSS class — uses inline styles (email client compatibility)."""
    loc = {**BASE_LOC, "alerts": [{
        "event": "Winter Storm Warning",
        "expires": "Fri 9:00am",
        "agency": "NWS",
        "url": "https://alerts.weather.gov/example",
    }]}
    html = _weather_html({"locations": [loc]})
    assert 'style=' in html
    assert 'class="alert' not in html

def test_weather_html_shows_attribution():
    html = _weather_html({"locations": [BASE_LOC]})
    assert "weatherkit.apple.com/legal-attribution.html" in html
    assert ">Weather<" in html
