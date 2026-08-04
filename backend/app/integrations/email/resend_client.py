import asyncio

import resend

from app.core.config import get_settings


class EmailClient:
    """§11.10 — Resend, chosen for free-tier headroom + DX fit for this
    project's low-volume transactional use (username recovery, password
    reset, registration-complete). The SDK is sync, so calls run in a
    thread to avoid blocking the event loop."""

    def __init__(self) -> None:
        settings = get_settings()
        resend.api_key = settings.resend_api_key
        self._from = settings.email_from_address

    async def send_registration_complete(self, *, to_email: str, username: str) -> None:
        # §11.2 確定: body contains only the username, nothing else.
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": self._from,
                "to": [to_email],
                "subject": "Social Link AI — 登録完了",
                "text": f"ご登録ありがとうございます。\n\nユーザー名: {username}",
            },
        )

    async def send_username_reminder(self, *, to_email: str, username: str) -> None:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": self._from,
                "to": [to_email],
                "subject": "Social Link AI — ユーザー名のお知らせ",
                "text": f"お問い合わせのユーザー名は以下の通りです。\n\nユーザー名: {username}",
            },
        )

    async def send_password_reset(self, *, to_email: str, reset_url: str) -> None:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": self._from,
                "to": [to_email],
                "subject": "Social Link AI — パスワード再設定",
                "text": (
                    "以下のリンクからパスワードを再設定してください。"
                    "このリンクは一定時間で無効になります。\n\n" + reset_url
                ),
            },
        )
