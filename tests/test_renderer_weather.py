from renderer import _weather_html, _weather_emoji

BASE_LOC = {
    "location": "Warwick, NY",
    "temp": 54,
    "condition": "Partly Cloudy",
    "high": 61,
    "low": 44,
    "sunrise": "6:52am",
    "sunset": "7:31pm",
    "alerts": [],
    "sentence": "A breezy spring afternoon under patchy clouds.",
}


def _html(loc=BASE_LOC):
    html, icons = _weather_html({"locations": [loc]})
    assert icons == []
    return html


def test_weather_html_shows_location():
    assert '<div class="weather-place">Warwick, NY</div>' in _html()


def test_weather_html_compact_line_order():
    html = _html()
    line = html[html.index('class="weather-line"'):]
    assert line.index("⛅") < line.index("54°") < line.index("(44°/61°)") < line.index("A breezy spring")


def test_weather_html_shows_sentence():
    assert '<span class="weather-summary">A breezy spring afternoon under patchy clouds.</span>' in _html()


def test_weather_html_omits_sentence_when_empty():
    assert "weather-summary" not in _html({**BASE_LOC, "sentence": ""})


def test_weather_html_drops_card_sunrise_and_inline_attribution():
    html = _html()
    assert "weather-card" not in html
    assert "Sunrise" not in html
    assert "legal-attribution" not in html


def test_weather_html_no_rule_or_label():
    html = _html()
    assert "section-rule" not in html
    assert "Weather</div>" not in html


def test_weather_html_no_alert_when_empty():
    assert "⚠" not in _html()


def test_weather_html_shows_alert_line_with_inline_styles():
    loc = {**BASE_LOC, "alerts": [{
        "event": "Wind Advisory",
        "expires": "Sat 6:00pm",
        "agency": "NWS",
        "url": "https://alerts.weather.gov/example",
    }]}
    html = _html(loc)
    assert "Wind Advisory until Sat 6:00pm" in html
    assert "alerts.weather.gov" in html
    assert "color:#d93025" in html


def test_weather_html_renders_each_location():
    travel = {**BASE_LOC, "location": "Chicago", "condition": "Windy", "temp": 48}
    html, _ = _weather_html({"locations": [BASE_LOC, travel]})
    assert html.count('class="weather-loc"') == 2
    assert "Chicago" in html and "\U0001f4a8" in html


def test_weather_emoji_mapping():
    assert _weather_emoji("Clear") == "☀️"
    assert _weather_emoji("Mostly Clear") == "\U0001f324️"
    assert _weather_emoji("Mostly Cloudy") == "\U0001f325️"
    assert _weather_emoji("Cloudy") == "☁️"
    assert _weather_emoji("Sun Showers") == "\U0001f326️"
    assert _weather_emoji("Heavy Rain") == "\U0001f327️"
    assert _weather_emoji("Scattered Thunderstorms") == "⛈️"
    assert _weather_emoji("Freezing Rain") == "\U0001f9ca"
    assert _weather_emoji("Unknown") == "\U0001f321️"
