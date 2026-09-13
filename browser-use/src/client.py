"""Native asynchronous client for the Wirebox Edge REST API."""

from __future__ import annotations

import asyncio
import time
from typing import Any
import httpx


class WireboxClient:
    """Lightweight, typed async client for Wirebox identities and mailboxes."""

    def __init__(self, api_key: str = "", base_url: str = "https://api.wirebox.sh/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "wirebox-browser-use/0.1.0",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def signup(
        self,
        human_email: str,
        display_name: str = "Browser Agent",
        note_to_human: str = "Autonomous browser agent registering for internet tasks.",
    ) -> dict[str, str]:
        """Self-register a new agent identity and mailbox without prior credentials.

        Returns:
            dict containing 'api_key' and 'email_address'.
        """
        url = f"{self.base_url}/agent-signup"
        payload = {
            "human_email": human_email,
            "display_name": display_name,
            "note_to_human": note_to_human,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            self.api_key = data.get("api_key", "")
            return data

    async def list_messages(
        self,
        mailbox_address: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List messages in the specified mailbox."""
        url = f"{self.base_url}/mailboxes/{mailbox_address}/messages"
        params = {"limit": limit}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=self._get_headers())
            resp.raise_for_status()
            data = resp.json()
            return data.get("messages", [])

    async def get_message(
        self,
        mailbox_address: str,
        message_id: str,
    ) -> dict[str, Any]:
        """Fetch full details (including full text_body and html_body) of a message."""
        url = f"{self.base_url}/mailboxes/{mailbox_address}/messages/{message_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()

    async def send_message(
        self,
        mailbox_address: str,
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> dict[str, Any]:
        """Send an outbound email from the agent's mailbox."""
        url = f"{self.base_url}/mailboxes/{mailbox_address}/messages"
        payload: dict[str, Any] = {
            "recipients": {"to": to},
            "subject": subject,
            "body_text": body_text,
        }
        if body_html:
            payload["body_html"] = body_html

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=self._get_headers())
            resp.raise_for_status()
            return resp.json()

    async def wait_for_email(
        self,
        mailbox_address: str,
        subject_contains: str | None = None,
        from_contains: str | None = None,
        timeout_seconds: int = 60,
        poll_interval: float = 2.0,
    ) -> dict[str, Any] | None:
        """Poll the mailbox until an email matching criteria arrives or timeout expires.

        This is ideal for automated registration flows where the agent expects a verification
        code or magic link email.
        """
        deadline = time.monotonic() + timeout_seconds
        subj_filter = subject_contains.lower() if subject_contains else None
        from_filter = from_contains.lower() if from_contains else None

        while time.monotonic() < deadline:
            try:
                messages = await self.list_messages(mailbox_address, limit=10)
                for msg in messages:
                    subj = str(msg.get("subject", "")).lower()
                    from_addr = str(msg.get("from", "")).lower()

                    matches_subj = not subj_filter or subj_filter in subj
                    matches_from = not from_filter or from_filter in from_addr

                    # If sender matches and subject has common auth words (confirm, verify, code, otp, etc.), match it!
                    is_auth_email = any(w in subj for w in ["confirm", "verify", "code", "otp", "magic", "signup", "login", "welcome", "activation"])
                    if (matches_from and (matches_subj or is_auth_email)) or (matches_subj and not from_filter):
                        msg_id = msg.get("id")
                        if msg_id:
                            # Fetch complete body
                            full_msg = await self.get_message(mailbox_address, msg_id)
                            return full_msg
            except Exception:
                pass  # Keep waiting on transient network glitch

            await asyncio.sleep(poll_interval)

        return None
