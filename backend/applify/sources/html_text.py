"""HTML posting text → plain text with light Markdown (## headings, - lists).

The frontend renders that format without {@html} (lib/text.ts), as it does for the BA text.
"""

import re
from html.parser import HTMLParser

BLOCK = frozenset(
    [
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "br",
        "hr",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ]
)
HEADING = frozenset(["h1", "h2", "h3", "h4", "h5", "h6"])
BOLD = frozenset(["strong", "b"])
SKIP = frozenset(["script", "style", "noscript", "template"])
# A paragraph that is bold only and this short reads as a heading ("Deine Aufgaben").
MAX_BOLD_HEADING = 80


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.parts: list[str] = []
        self.bold_chars = 0
        self.heading = False
        self.items = 0  # open <li> elements
        self.bold = 0
        self.skip = 0

    def flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.parts)).strip()
        if text:
            if self.heading or (
                not self.items
                and self.bold_chars >= len(text.replace(" ", ""))
                and len(text) <= MAX_BOLD_HEADING
            ):
                self.lines += ["", f"## {text.rstrip(':')}"]
            elif self.items:
                self.lines.append(f"- {text}")
            else:
                self.lines += ["", text]
        self.parts, self.bold_chars, self.heading = [], 0, False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.flush()
            if tag in HEADING:
                self.heading = True
            elif tag == "li":
                self.items += 1
            elif tag in ("ul", "ol"):
                self.lines.append("")
        elif tag in BOLD:
            self.bold += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.flush()
            if tag == "li":
                self.items = max(0, self.items - 1)
        elif tag in BOLD:
            self.bold = max(0, self.bold - 1)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        self.parts.append(data)
        if self.bold:
            self.bold_chars += len(re.sub(r"\s", "", data))


def html_to_text(html: str) -> str:
    if "<" not in html:
        return html.strip()
    parser = _Text()
    parser.feed(html)
    parser.close()
    parser.flush()
    text = "\n".join(parser.lines)
    # Lists directly follow each other; blank lines separate everything else once.
    return re.sub(r"\n{3,}", "\n\n", text).strip()
