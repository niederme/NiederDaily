from __future__ import annotations

from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from html import escape as _esc

ACCENT = "#ff453a"
INK = "#121212"
MUTED = "#474a51"
LINE = "#d6d0c6"

BADGE_OVERDUE = f'<span style="display:inline-block;min-width:56px;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Overdue</span>'
BADGE_TODAY = f'<span style="display:inline-block;min-width:56px;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Today</span>'
BADGE_REPLY = f'<span style="display:inline-block;color:{ACCENT};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Needs reply</span>'

SECTION_LABEL_STYLE = f"font-size:16px;font-weight:700;letter-spacing:-0.01em;color:{INK};margin-bottom:14px;"

BASE_STYLES = """
body{margin:0;padding:0;background:#ffffff;color:#121212;font-family:Sohne,"SF Pro Text","SF Pro Display",-apple-system,BlinkMacSystemFont,"Helvetica Neue","Arial Nova",Arial,sans-serif;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
a{color:#121212;}
.wrap{max-width:680px;margin:0 auto;}
.email{background:#ffffff;overflow:hidden;}
.header{padding:44px 40px 24px;}
.date-line{font-size:16px;font-weight:300;line-height:1.35;letter-spacing:-0.01em;color:#474a51;max-width:520px;margin-bottom:12px;}
.logo{font-size:44px;font-weight:700;line-height:0.96;letter-spacing:-0.03em;color:#121212;margin-bottom:18px;}
.welcome{max-width:520px;font-size:18px;font-weight:300;line-height:1.38;color:#474a51;}
.section{padding:0 40px 24px;}
.section-rule{height:1px;background:#d6d0c6;margin:0 0 24px;}
.module-place{font-size:20px;font-weight:700;line-height:1.15;letter-spacing:-0.02em;color:#121212;margin-bottom:12px;}
.weather-card{padding:20px 22px 18px;border:1px solid rgba(214,208,198,0.9);border-radius:18px;background:#ffffff;}
.display-line{font-size:58px;font-weight:300;line-height:0.94;letter-spacing:-0.03em;color:#121212;display:flex;align-items:center;gap:18px;flex-wrap:wrap;}
.weather-icon{display:inline-flex;align-items:center;justify-content:center;width:84px;height:84px;color:#474a51;flex-shrink:0;}
.weather-icon svg{width:56px;height:56px;}
.weather-condition{font-size:17px;font-weight:600;line-height:1.2;color:#121212;margin-top:10px;}
.weather-meta{font-size:12px;line-height:1.45;color:#6d7178;margin-top:4px;}
.supporting{font-size:13px;line-height:1.45;color:#474a51;margin-top:8px;}
.list-row{display:flex;gap:18px;align-items:baseline;padding:0 0 11px;margin:0 0 11px;border-bottom:1px solid rgba(214,208,198,0.55);}
.list-row:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.list-time{min-width:56px;font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#474a51;}
.list-main{flex:1;font-size:15px;line-height:1.35;color:#121212;}
.list-meta{display:block;font-size:12px;line-height:1.4;color:#474a51;margin-top:4px;}
.msgrow{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:0 0 14px;margin:0 0 14px;border-bottom:1px solid rgba(214,208,198,0.55);}
.msgrow:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.msgname{font-size:16px;font-weight:700;color:#121212;line-height:1.2;}
.msgmeta{font-size:12px;color:#474a51;line-height:1.45;margin-top:5px;}
.nyt{display:flex;gap:20px;align-items:flex-start;padding:0 0 16px;margin:0 0 16px;border-bottom:1px solid rgba(214,208,198,0.55);}
.nyt:last-child{padding-bottom:0;margin-bottom:0;border-bottom:0;}
.nytthumb{width:175px;height:117px;object-fit:cover;object-position:right center;flex-shrink:0;background:#f5efe5;}
.nythed{font-size:17px;font-weight:700;line-height:1.18;color:#121212;margin-bottom:6px;}
.nytdek{font-size:13px;color:#474a51;line-height:1.42;}
.nytbyline{font-size:11px;color:#474a51;line-height:1.4;margin-top:7px;}
.photo-caption{padding:14px 40px;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:#474a51;background:#f5efe5;border-bottom:1px solid #d6d0c6;}
.footer{padding:18px 40px 36px;font-size:11px;color:#474a51;border-top:0;background:#ffffff;}
.footer a{color:#121212;text-decoration:none;border-bottom:1px solid rgba(18,18,18,0.65);}
"""


def _label(text: str) -> str:
    return f'<div style="{SECTION_LABEL_STYLE}">{_esc(text)}</div>'


def _section(label: str | None, content: str, *, show_rule: bool = True) -> str:
    rule = '<div class="section-rule"></div>' if show_rule else ""
    heading = _label(label) if label else ""
    return f'<div class="section">{rule}{heading}{content}</div>'


def _weather_icon(condition: str) -> str:
    c = condition.lower()
    stroke = MUTED
    if "thunder" in c:
        return (
            f'<span class="weather-icon" aria-hidden="true">'
            f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M10 14.5C10 10.9101 12.9101 8 16.5 8C19.2451 8 21.5927 9.70662 22.5287 12.1172C22.8455 12.0398 23.1765 12 23.5167 12C25.9921 12 28 14.0079 28 16.4833C28 18.9588 25.9921 20.9667 23.5167 20.9667H12.5C9.46243 20.9667 7 18.5042 7 15.4667C7 12.4291 9.46243 9.96667 12.5 9.96667" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<path d="M17.5 16.5L14 22.5H17.8L15.8 27L21.5 19.8H17.8L20 16.5" stroke="{ACCENT}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg></span>'
        )
    if "snow" in c or "ice" in c:
        return (
            f'<span class="weather-icon" aria-hidden="true">'
            f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M11 14.5C11 10.9101 13.9101 8 17.5 8C20.2451 8 22.5927 9.70662 23.5287 12.1172C23.8455 12.0398 24.1765 12 24.5167 12C26.9921 12 29 14.0079 29 16.4833C29 18.9588 26.9921 20.9667 24.5167 20.9667H13.5C10.4624 20.9667 8 18.5042 8 15.4667C8 12.4291 10.4624 9.96667 13.5 9.96667" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<path d="M13.5 24.5H20.5M17 21V28M14.5 22.5L19.5 26.5M19.5 22.5L14.5 26.5" stroke="{stroke}" stroke-width="1.6" stroke-linecap="round"/>'
            f'</svg></span>'
        )
    if "rain" in c or "drizzle" in c or "shower" in c:
        return (
            f'<span class="weather-icon" aria-hidden="true">'
            f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M10 14.5C10 10.9101 12.9101 8 16.5 8C19.2451 8 21.5927 9.70662 22.5287 12.1172C22.8455 12.0398 23.1765 12 23.5167 12C25.9921 12 28 14.0079 28 16.4833C28 18.9588 25.9921 20.9667 23.5167 20.9667H12.5C9.46243 20.9667 7 18.5042 7 15.4667C7 12.4291 9.46243 9.96667 12.5 9.96667" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<path d="M14 23.5L12.8 26.5M18 23.5L16.8 26.5M22 23.5L20.8 26.5" stroke="{ACCENT}" stroke-width="1.8" stroke-linecap="round"/>'
            f'</svg></span>'
        )
    if "clear" in c or "sun" in c:
        return (
            f'<span class="weather-icon" aria-hidden="true">'
            f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'<circle cx="17" cy="17" r="5.5" stroke="{ACCENT}" stroke-width="1.8"/>'
            f'<path d="M17 6V9M17 25V28M28 17H25M9 17H6M24.8 9.2L22.6 11.4M11.4 22.6L9.2 24.8M24.8 24.8L22.6 22.6M11.4 11.4L9.2 9.2" stroke="{ACCENT}" stroke-width="1.8" stroke-linecap="round"/>'
            f'</svg></span>'
        )
    if "fog" in c:
        return (
            f'<span class="weather-icon" aria-hidden="true">'
            f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M10 13.5C10 10.4624 12.4624 8 15.5 8C17.8246 8 19.8128 9.44544 20.6058 11.4869C20.8742 11.4214 21.1547 11.3878 21.4433 11.3878C23.5424 11.3878 25.244 13.0894 25.244 15.1884C25.244 17.2875 23.5424 18.9891 21.4433 18.9891H12.1111C9.8406 18.9891 8 17.1485 8 14.878C8 12.6075 9.8406 10.7669 12.1111 10.7669" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
            f'<path d="M10 23.5H24M8 26.5H22" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
            f'</svg></span>'
        )
    return (
        f'<span class="weather-icon" aria-hidden="true">'
        f'<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="M10 14.5C10 10.9101 12.9101 8 16.5 8C19.2451 8 21.5927 9.70662 22.5287 12.1172C22.8455 12.0398 23.1765 12 23.5167 12C25.9921 12 28 14.0079 28 16.4833C28 18.9588 25.9921 20.9667 23.5167 20.9667H12.5C9.46243 20.9667 7 18.5042 7 15.4667C7 12.4291 9.46243 9.96667 12.5 9.96667" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round"/>'
        f'</svg></span>'
    )


def _weather_html(data: dict) -> str:
    parts = []
    for loc in data["locations"]:
        body = (
            f'<div class="weather-card">'
            f'<div class="module-place">{_esc(loc["location"])}</div>'
            f'<div class="display-line">'
            f'{_weather_icon(loc["condition"])}'
            f'<span>{loc["high"]}° / {loc["low"]}°</span></div>'
            f'<div class="weather-condition">{_esc(loc["condition"])}</div>'
            f'<div class="weather-meta">Sunrise {_esc(loc["sunrise"])} · Sunset {_esc(loc["sunset"])}</div>'
            f'</div>'
        )
        parts.append(_section(None, body, show_rule=False))
    return "".join(parts)


def _calendar_html(events: list, *, show_rule: bool = True) -> str:
    if not events:
        return _section("Calendar", '<div class="supporting">Nothing on the calendar.</div>', show_rule=show_rule)
    rows = []
    for e in events:
        time_str = _esc(e.get("time") or "All day")
        loc = (f'<span class="list-meta">{_esc(e["location"])}</span>' if e.get("location") else "")
        rows.append(
            f'<div class="list-row">'
            f'<span class="list-time">{time_str}</span>'
            f'<div class="list-main">{_esc(e["title"])}{loc}</div></div>'
        )
    return _section("Calendar", "".join(rows), show_rule=show_rule)


def _reminders_html(data: dict, *, show_rule: bool = True) -> str:
    rows = []
    for r in data.get("overdue", []):
        rows.append(f'<div class="list-row"><span class="list-time">{BADGE_OVERDUE}</span><div class="list-main">{_esc(r["title"])}</div></div>')
    for r in data.get("today", []):
        rows.append(f'<div class="list-row"><span class="list-time">{BADGE_TODAY}</span><div class="list-main">{_esc(r["title"])}</div></div>')
    next_day = None
    for r in data.get("upcoming", []):
        due_raw = r.get("due")
        if next_day is None:
            next_day = due_raw
        elif due_raw != next_day:
            break
        try:
            from datetime import datetime
            due = datetime.strptime(due_raw, "%Y-%m-%d").strftime("%a %-d")
        except Exception:
            due = due_raw
        badge = f'<span style="display:inline-block;min-width:56px;color:{MUTED};font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">{due}</span>'
        rows.append(f'<div class="list-row"><span class="list-time">{badge}</span><div class="list-main">{_esc(r["title"])}</div></div>')
    if not rows:
        return _section("Reminders", '<div class="supporting">All clear.</div>', show_rule=show_rule)
    return _section("Reminders", "".join(rows), show_rule=show_rule)


def _messages_html(threads: list, *, show_rule: bool = True) -> str:
    rows = []
    for t in threads:
        badge = BADGE_REPLY if t["needs_reply"] else ""
        rows.append(
            f'<div class="msgrow">'
            f'<div><div class="msgname">{_esc(t["name"])}</div>'
            f'<div class="msgmeta">{t["count"]} message{"s" if t["count"] != 1 else ""} · last {_esc(t["last_time"])}</div></div>'
            f'{badge}</div>'
        )
    return _section("Messages", "".join(rows), show_rule=show_rule)


def _nyt_html(stories: list, *, show_rule: bool = True) -> str:
    rows = []
    for s in stories:
        img = ""
        if s.get("thumbnail"):
            img = f'<img class="nytthumb" src="{_esc(s["thumbnail"])}" alt="">'
        byline = ""
        if s.get("byline"):
            byline = f'<div class="nytbyline">{_esc(s["byline"])}</div>'
        rows.append(
            f'<div class="nyt"><div style="flex:1;"><div class="nythed">'
            f'<a href="{_esc(s["url"])}" style="color:{INK};text-decoration:none;">{_esc(s["title"])}</a></div>'
            f'<div class="nytdek">{_esc(s["abstract"])}</div>{byline}</div>{img}</div>'
        )
    return _section("In the News", "".join(rows), show_rule=show_rule)


def render_email(
    recipient: str,
    welcome: str | None,
    weather: dict | None,
    calendar: list | None,
    reminders: dict | None,
    messages: list | None,
    photo: tuple | None,
    nyt: list | None,
) -> MIMEMultipart:
    today = date.today()
    date_str = today.strftime("%A, %B %-d, %Y")
    subject = f"NiederDaily · {date_str}"

    welcome_html = ""
    if welcome:
        welcome_html = f'<div class="welcome">{_esc(welcome)}</div>'

    sections = []
    next_section_rule = weather is None
    if weather:
        sections.append(_weather_html(weather))
    if calendar is not None:
        sections.append(_calendar_html(calendar, show_rule=next_section_rule))
        next_section_rule = True
    if reminders:
        sections.append(_reminders_html(reminders, show_rule=next_section_rule))
        next_section_rule = True
    if messages:
        sections.append(_messages_html(messages, show_rule=next_section_rule))
        next_section_rule = True

    photo_html = ""
    if photo:
        _, meta = photo
        caption_parts = []
        if meta.get("location"):
            caption_parts.append(_esc(meta["location"]))
        if meta.get("date"):
            caption_parts.append(_esc(meta["date"]))
        if meta.get("is_favorite"):
            caption_parts.append("★ Favorite")
        caption = " · ".join(caption_parts)
        photo_html = (
            '<div style="line-height:0;">'
            '<img src="cid:onthisday" style="width:100%;max-width:600px;display:block;" alt="On This Day">'
            '</div>'
            f'<div class="photo-caption">{caption}</div>'
        )

    if nyt:
        sections.append(_nyt_html(nyt, show_rule=next_section_rule))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{BASE_STYLES}</style></head>
<body>
<div class="wrap" style="padding:24px 20px 48px;">
<div class="email">
  <div class="header">
    <div class="date-line">{date_str}</div>
    <div class="logo">NiederDaily</div>
    {welcome_html}
  </div>
  {"".join(sections)}
  {photo_html}
  <div class="footer">NiederDaily · <a href="mailto:{recipient}">{recipient}</a> · Every morning at 6am</div>
</div>
</div>
</body></html>"""

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = recipient  # self-addressed; Gmail API sets the actual sender via OAuth

    html_part = MIMEText(html, "html", "utf-8")
    msg.attach(html_part)

    if photo:
        img_bytes, img_meta = photo
        img_fmt = img_meta.get("format", "jpeg")  # e.g. "jpeg", "heic", "png"
        img_ext = "jpg" if img_fmt in ("jpeg", "jpg") else img_fmt
        img_part = MIMEImage(img_bytes, _subtype=img_fmt)
        img_part.add_header("Content-ID", "<onthisday>")
        img_part.add_header("Content-Disposition", "inline", filename=f"onthisday.{img_ext}")
        msg.attach(img_part)

    return msg
