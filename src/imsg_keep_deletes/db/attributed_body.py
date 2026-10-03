import re

# NSAttributedString blobs often store the message as a length-prefixed UTF-8
# string after a '+' marker in the typedstream/archive format.
_PLUS_LEN_RE = re.compile(rb"\x02[\x01\x02\x03\x04]\x08([^\x00]+)")


def decode_attributed_body(data: bytes | None) -> str | None:
    if not data:
        return None

    plus = data.find(b"+")
    if plus != -1 and plus + 2 < len(data):
        length = data[plus + 1]
        start = plus + 2
        end = start + length
        if 0 < length <= len(data) - start:
            try:
                text = data[start:end].decode("utf-8")
                if text.strip():
                    return text
            except UnicodeDecodeError:
                pass

    match = _PLUS_LEN_RE.search(data)
    if match:
        try:
            text = match.group(1).decode("utf-8")
            if text.strip():
                return text
        except UnicodeDecodeError:
            pass

    runs = re.findall(rb"[\x20-\x7e]{4,}", data)
    if not runs:
        return None
    return max(runs, key=len).decode("utf-8", errors="ignore") or None


def message_text(text: str | None, attributed_body: bytes | None) -> str:
    if text and text.strip():
        return text.strip()
    decoded = decode_attributed_body(attributed_body)
    if decoded:
        return decoded.strip()
    return ""
