"""从 GitHub 公开贡献日历生成最近 90 天的立体贡献图。"""
from datetime import datetime, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USER = "linx29853"
DAYS = 90
OUTPUT = Path("metrics.plugin.isocalendar.fullyear.svg")


class ContributionsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates = {}
        self.counts = {}
        self.tooltip = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.dates[attrs["id"]] = attrs["data-date"]
        if tag == "tool-tip":
            self.tooltip = attrs.get("for")
            self.text = []

    def handle_data(self, text):
        if self.tooltip:
            self.text.append(text)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip:
            text = "".join(self.text).strip()
            match = re.match(r"([\d,]+) contributions?\b", text)
            if match:
                self.counts[self.tooltip] = int(match[1].replace(",", ""))
            elif text.startswith("No contributions"):
                self.counts[self.tooltip] = 0
            self.tooltip = None


def fetch_counts(start, end):
    counts = {}
    # GitHub 贡献页面按年提供日历，跨年时分别读取。
    for year in range(start.year, end.year + 1):
        url = f"https://github.com/users/{USER}/contributions?from={year}-01-01&to={year}-12-31"
        request = Request(url, headers={"User-Agent": "profile-contribution-calendar", "Accept-Language": "en-US"})
        with urlopen(request, timeout=60) as response:
            html = response.read().decode("utf-8")
        parser = ContributionsParser()
        parser.feed(html)
        counts.update({day: parser.counts[key] for key, day in parser.dates.items() if key in parser.counts})
    required = [(start + timedelta(days=i)).isoformat() for i in range(DAYS)]
    missing = [day for day in required if day not in counts]
    if missing:
        raise RuntimeError(f"GitHub 日历缺少 {len(missing)} 天的数据，保留原图。")
    return [(day, counts[day]) for day in required]


def render(days):
    start = datetime.fromisoformat(days[0][0]).date()
    end = datetime.fromisoformat(days[-1][0]).date()
    # 星期日作为每周起点；范围外的位置留空，不参与平均值计算。
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    values = [count for _, count in days]
    total, peak = sum(values), max(values)
    average = total / len(values)
    streak = longest = 0
    for count in values:
        streak = streak + 1 if count else 0
        longest = max(longest, streak)
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="280" viewBox="0 0 480 280" role="img" aria-labelledby="title desc">
<title id="title">Recent {DAYS} days of GitHub contributions</title>
<desc id="desc">{start} to {end}: {total} contributions, {average:.2f} per day. Public GitHub contribution calendar.</desc>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;fill:#57606a}}.heading{{fill:#0969da;font-size:16px}}.small{{font-size:11px}}.value{{font-size:21px;fill:#24292f}}@media(prefers-color-scheme:dark){{text{{fill:#8b949e}}.heading{{fill:#58a6ff}}.value{{fill:#c9d1d9}}}}</style>
<text x="16" y="23" class="heading">GitHub contributions · Last {DAYS} days</text>
<text x="16" y="43" class="small">{start} — {end} · {total} contributions</text>
''']
    palette = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
    for day, count in days:
        date = datetime.fromisoformat(day).date()
        offset = (date - first_sunday).days
        week, weekday = divmod(offset, 7)
        ratio = count / peak if peak else 0
        level = 0 if not count else min(4, max(1, int(ratio * 4 + 0.999)))
        color = palette[level]
        x, y = 100 + week * 23 - weekday * 12, 70 + week * 8 + weekday * 7
        height = ratio * 34
        top = y - height
        # 顶面和两侧共享同一个贡献柱高度。
        svg.append(f'''<g><title>{escape(day)}: {count} contributions</title>
<path fill="{color}" d="M{x},{top} l6,-3 6,3 -6,3 Z"/>
<path fill="{color}" d="M{x},{top} l6,3 v{height} l-6,-3 Z"/>
<path fill="#000" opacity=".18" d="M{x},{top} l6,3 v{height} l-6,-3 Z"/>
<path fill="{color}" d="M{x+6},{top+3} l6,-3 v{height} l-6,3 Z"/>
<path fill="#000" opacity=".35" d="M{x+6},{top+3} l6,-3 v{height} l-6,3 Z"/>
</g>''')
    for x, value, label in [(18, f"{average:.2f}", "per day"), (136, str(peak), "best day"), (254, str(streak), "current streak"), (372, str(longest), "longest streak")]:
        svg.append(f'<text x="{x}" y="247" class="value">{value}</text><text x="{x}" y="267" class="small">{label}</text>')
    svg.append("</svg>\n")
    return "\n".join(svg)


def main():
    end = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    start = end - timedelta(days=DAYS - 1)
    days = fetch_counts(start, end)
    result = render(days)
    OUTPUT.write_text(result, encoding="utf-8")
    print(f"{start} — {end}: {sum(n for _, n in days)} contributions / {DAYS} days = {sum(n for _, n in days) / DAYS:.2f} per day")


if __name__ == "__main__":
    main()
