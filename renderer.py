from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

BADGE_OVERDUE = '<span style="display:inline-block;background:#fee2e2;color:#b91c1c;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">Overdue</span>'
BADGE_TODAY   = '<span style="display:inline-block;background:#dbeafe;color:#1d4ed8;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">Today</span>'
BADGE_REPLY   = '<span style="display:inline-block;background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;">Needs reply</span>'

SECTION_LABEL_STYLE = "font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#bbb;margin-bottom:12px;"

BASE_STYLES = """
body{margin:0;padding:0;background:#f0ede8;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;}
.wrap{max-width:600px;margin:0 auto;}
.email{background:#fff;border-radius:4px;overflow:hidden;}
.header{background:#1a1a1a;padding:32px 36px 28px;}
.logo{font-size:10px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#555;margin-bottom:10px;}
.date-line{font-size:26px;font-weight:300;color:#fff;letter-spacing:-0.02em;margin-bottom:14px;}
.welcome{font-size:15px;font-style:italic;color:#a3a3a3;line-height:1.5;border-top:1px solid #333;padding-top:14px;}
.section{padding:20px 36px;border-bottom:1px solid #f2f0ec;}
.msgrow{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.msgname{font-size:13px;font-weight:600;color:#1a1a1a;}
.msgmeta{font-size:11px;color:#bbb;margin-top:2px;}
.nyt{display:flex;gap:14px;margin-bottom:14px;align-items:flex-start;}
.nytthumb{width:60px;height:60px;object-fit:cover;border-radius:3px;flex-shrink:0;}
.nythed{font-size:13px;font-weight:600;color:#1a1a1a;margin-bottom:3px;line-height:1.35;}
.nytdek{font-size:11px;color:#888;line-height:1.45;}
.photo-caption{padding:10px 36px;font-size:11px;color:#bbb;background:#fafaf9;}
.footer{background:#f7f6f3;padding:16px 36px;font-size:10px;color:#ccc;text-align:center;border-top:1px solid #ede9e3;}
"""


def _label(text: str) -> str:
    return f'<div style="{SECTION_LABEL_STYLE}">{text}</div>'


def _section(label: str, content: str) -> str:
    return f'<div class="section">{_label(label)}{content}</div>'


def _weather_html(data: dict) -> str:
    parts = []
    for loc in data["locations"]:
        label = f"WEATHER · {loc['location'].upper()}"
        body = (
            f'<div style="font-size:32px;font-weight:200;color:#1a1a1a;letter-spacing:-0.02em;">'
            f'{loc["temp"]}°&thinsp; {loc["condition"]}</div>'
            f'<div style="font-size:12px;color:#999;margin-top:4px;">'
            f'High {loc["high"]}° · Low {loc["low"]}° · Sunrise {loc["sunrise"]} · Sunset {loc["sunset"]}</div>'
        )
        parts.append(_section(label, body))
    return "".join(parts)


def _calendar_html(events: list) -> str:
    if not events:
        body = '<div style="font-size:13px;color:#bbb;">Nothing on the calendar.</div>'
        return _section("TODAY", body)
    rows = []
    for e in events:
        time_str = e.get("time") or "All day"
        loc = (f'<span style="font-size:11px;color:#bbb;margin-left:6px;">· {e["location"]}</span>'
               if e.get("location") else "")
        rows.append(
            f'<div style="display:flex;gap:16px;align-items:baseline;margin-bottom:9px;">'
            f'<span style="font-size:11px;color:#bbb;min-width:36px;">{time_str}</span>'
            f'<span style="font-size:13px;color:#1a1a1a;">{e["title"]}{loc}</span></div>'
        )
    return _section("TODAY", "".join(rows))


def _reminders_html(data: dict) -> str:
    rows = []
    for r in data.get("overdue", []):
        rows.append(f'<div style="font-size:13px;color:#1a1a1a;margin-bottom:8px;">{BADGE_OVERDUE}{r["title"]}</div>')
    for r in data.get("today", []):
        rows.append(f'<div style="font-size:13px;color:#1a1a1a;margin-bottom:8px;">{BADGE_TODAY}{r["title"]}</div>')
    for r in data.get("upcoming", []):
        try:
            from datetime import datetime
            due = datetime.strptime(r["due"], "%Y-%m-%d").strftime("%a %-d")
        except Exception:
            due = r["due"]
        badge = f'<span style="display:inline-block;background:#f3f4f6;color:#6b7280;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:6px;">{due}</span>'
        rows.append(f'<div style="font-size:13px;color:#1a1a1a;margin-bottom:8px;">{badge}{r["title"]}</div>')
    if not rows:
        return _section("REMINDERS", '<div style="font-size:13px;color:#bbb;">All clear.</div>')
    return _section("REMINDERS", "".join(rows))


def _messages_html(threads: list) -> str:
    rows = []
    for t in threads:
        badge = BADGE_REPLY if t["needs_reply"] else ""
        rows.append(
            f'<div class="msgrow">'
            f'<div><div class="msgname">{t["name"]}</div>'
            f'<div class="msgmeta">{t["count"]} message{"s" if t["count"] != 1 else ""} · last {t["last_time"]}</div></div>'
            f'{badge}</div>'
        )
    return _section("MESSAGES", "".join(rows))


def _nyt_html(stories: list) -> str:
    rows = []
    for s in stories:
        if s.get("thumbnail"):
            img = f'<img class="nytthumb" src="{s["thumbnail"]}" alt="">'
        else:
            img = '<div class="nytthumb" style="background:#e5e7eb;"></div>'
        rows.append(
            f'<div class="nyt">{img}'
            f'<div><div class="nythed">'
            f'<a href="{s["url"]}" style="color:#1a1a1a;text-decoration:none;">{s["title"]}</a></div>'
            f'<div class="nytdek">{s["abstract"]}</div></div></div>'
        )
    return _section("IN THE NEWS", "".join(rows))


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
        welcome_html = f'<div class="welcome">"{welcome}"</div>'

    sections = []
    if weather:
        sections.append(_weather_html(weather))
    if calendar is not None:
        sections.append(_calendar_html(calendar))
    if reminders:
        sections.append(_reminders_html(reminders))
    if messages:
        sections.append(_messages_html(messages))

    photo_html = ""
    if photo:
        _, meta = photo
        caption_parts = []
        if meta.get("location"):
            caption_parts.append(meta["location"])
        if meta.get("date"):
            caption_parts.append(meta["date"])
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
        sections.append(_nyt_html(nyt))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{BASE_STYLES}</style></head>
<body>
<div class="wrap" style="padding:24px 16px;">
<div class="email">
  <div class="header">
    <div class="logo">NiederDaily</div>
    <div class="date-line">{date_str}</div>
    {welcome_html}
  </div>
  {"".join(sections)}
  {photo_html}
  <div class="footer">NiederDaily · {recipient} · Every morning at 6am</div>
</div>
</div>
</body></html>"""

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = recipient
    msg["From"] = recipient

    html_part = MIMEText(html, "html", "utf-8")
    msg.attach(html_part)

    if photo:
        img_bytes, _ = photo
        img_part = MIMEImage(img_bytes, _subtype="jpeg")
        img_part.add_header("Content-ID", "<onthisday>")
        img_part.add_header("Content-Disposition", "inline", filename="onthisday.jpg")
        msg.attach(img_part)

    return msg
