import json
import logging
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from imsg_keep_deletes.models import UnsendEvent

logger = logging.getLogger(__name__)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
_VIDEO_EXT = {".mov", ".mp4", ".m4v"}


def _format_local(dt: datetime) -> str:
    if dt.tzinfo is None:
        local = dt.astimezone()
    else:
        local = dt.astimezone()
    return local.strftime("%b %d, %Y %I:%M:%S %p")


def format_unsend_message(event: UnsendEvent) -> str:
    text = event.text.strip() or "(no text — attachment only)"
    lines = [
        "Unsent iMessage",
        "",
        f"From: {event.sender}",
    ]
    if event.chat != event.sender:
        lines.append(f"Chat: {event.chat}")
    lines.extend(
        [
            f"Sent: {_format_local(event.sent_at)}",
            f"Detected: {_format_local(event.detected_at)}",
            "",
            "Message:",
            text,
        ]
    )
    if event.attachment_paths:
        lines.append("")
        lines.append(f"Attachments: {len(event.attachment_paths)}")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @classmethod
    def from_config(cls) -> "TelegramNotifier | None":
        from imsg_keep_deletes.config import load_config

        cfg = load_config()
        if not cfg.telegram_enabled:
            return None
        return cls(cfg.telegram_bot_token, cfg.telegram_chat_id)

    def notify(self, event: UnsendEvent) -> None:
        self.send_message(format_unsend_message(event))
        for path in event.attachment_paths:
            self._send_attachment(path)

    def send_message(self, text: str) -> None:
        self._api_post("sendMessage", {"chat_id": self.chat_id, "text": text})

    def send_test(self) -> None:
        self.send_message(
            "imsg-keep-deletes is connected.\n"
            "You'll get a message here whenever someone unsends to you.\n\n"
            "Try /status or /help."
        )

    def get_updates(self, offset: int = 0, timeout: int = 0) -> list[dict]:
        query = urlencode({"offset": offset, "timeout": timeout})
        payload = self._api_get(f"getUpdates?{query}")
        return payload.get("result", [])

    def _send_attachment(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.is_file():
            logger.warning("Attachment missing for Telegram: %s", path)
            return

        ext = path.suffix.lower()
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        if ext in _IMAGE_EXT:
            method = "sendPhoto"
            field = "photo"
        elif ext in _VIDEO_EXT:
            method = "sendVideo"
            field = "video"
        else:
            method = "sendDocument"
            field = "document"

        self._api_post_multipart(
            method,
            fields={"chat_id": self.chat_id},
            files={field: (path.name, data, mime)},
        )

    def _api_get(self, method: str) -> dict:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        request = Request(url, method="GET")
        return self._execute(request)

    def _api_post(self, method: str, payload: dict) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        self._execute(request)

    def _api_post_multipart(
        self,
        method: str,
        fields: dict,
        files: dict[str, tuple[str, bytes, str]],
    ) -> None:
        boundary = uuid.uuid4().hex
        body = bytearray()

        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            )
            body.extend(str(value).encode())
            body.extend(b"\r\n")

        for key, (filename, data, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{key}"; '
                    f'filename="{filename}"\r\n'
                ).encode()
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(data)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode())

        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        request = Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        self._execute(request)

    def _execute(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc}") from exc

        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload
