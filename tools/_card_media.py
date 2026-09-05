"""Find/rewrite actual local img src attributes while preserving other HTML.

HTMLParser excludes comments/script contents. The attribute scanner locates
the original value within each parsed img tag so unrelated markup and existing
note GUID inputs are not normalized by serializing the whole document again.
"""
import html
from html.parser import HTMLParser
import re


_ATTR = re.compile(r'''([^\s/>=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?''')
_TAG = re.compile(r"<\s*[^\s/>]+")


def rewrite_local_images(markup, rewrite):
    """Call rewrite(path) for local images and substitute only their src value."""
    edits = []
    line_starts = [0] + [m.end() for m in re.finditer("\n", markup)]

    class Images(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != "img":
                return
            raw = self.get_starttag_text()
            for attr in _ATTR.finditer(raw, _TAG.match(raw).end()):
                if attr.group(1).lower() != "src":
                    continue
                # Browsers use the first attribute when a name is duplicated.
                token = attr.group(2)
                if not token:
                    return
                quote = token[0] if token[0] in "\"'" else ""
                value = html.unescape(token[1:-1] if quote else token).strip()
                if not value or value.lower().startswith(("data:", "http:", "https:", "//")):
                    return
                replacement = rewrite(value)
                if replacement != value:
                    line, column = self.getpos()
                    offset = line_starts[line - 1] + column
                    delimiter = quote or '"'
                    edits.append((offset + attr.start(2), offset + attr.end(2),
                                  delimiter + html.escape(replacement, quote=True) + delimiter))
                return

        handle_startendtag = handle_starttag

    parser = Images(convert_charrefs=False)
    parser.feed(markup)
    parser.close()
    for start, end, replacement in reversed(edits):
        markup = markup[:start] + replacement + markup[end:]
    return markup


def local_image_sources(markup):
    sources = []

    def collect(path):
        sources.append(path)
        return path

    rewrite_local_images(markup, collect)
    return sources
