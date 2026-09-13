"""Browser Use Controller actions for Wirebox autonomous email management."""

from __future__ import annotations

import json
from typing import Any
from pydantic import BaseModel, Field
from browser_use.controller import Controller
from browser_use.agent.views import ActionResult
from src.client import WireboxClient


class CheckInboxArgs(BaseModel):
    limit: int = Field(
        default=10,
        description="Number of recent emails to list from the inbox (default 10).",
    )


class ReadEmailArgs(BaseModel):
    message_id: str = Field(
        description="The unique message ID to read (e.g. 'msg_...').",
    )


class WaitForEmailArgs(BaseModel):
    subject_contains: str | None = Field(
        default=None,
        description="Substring or keyword to match in email subject (e.g. 'verification', 'otp', 'welcome').",
    )
    from_contains: str | None = Field(
        default=None,
        description="Substring or keyword to match sender address or name (e.g. 'noreply@firecrawl.dev').",
    )
    timeout_seconds: int = Field(
        default=45,
        description="Max seconds to wait and poll for the email (default 45s).",
    )


class SendEmailArgs(BaseModel):
    to: list[str] = Field(
        description="List of recipient email addresses.",
    )
    subject: str = Field(
        description="Subject line of the email.",
    )
    body_text: str = Field(
        description="Plain-text body of the email.",
    )


class GetAgentEmailArgs(BaseModel):
    pass


import re


def _format_message_content(msg: dict[str, Any]) -> dict[str, Any]:
    text_content = msg.get("text") or msg.get("text_body") or msg.get("snippet", "")
    html_content = msg.get("html") or msg.get("html_body") or ""

    # Extract clean URLs from text and HTML to make confirmation/magic links trivial to use
    combined = f"{text_content}\n{html_content}"
    raw_urls = re.findall(r'https?://[^\s<>"\'()]+', combined)
    detected_links: list[str] = []
    for u in raw_urls:
        clean_url = u.rstrip(".,;:\"')[]<>")
        # Decode HTML entities if present (&amp; -> &)
        clean_url = clean_url.replace("&amp;", "&")
        if clean_url and clean_url not in detected_links:
            detected_links.append(clean_url)

    return {
        "id": msg.get("id"),
        "from": msg.get("from"),
        "subject": msg.get("subject"),
        "text": text_content,
        "text_body": text_content,
        "snippet": msg.get("snippet"),
        "detected_links": detected_links,
        "created_at": msg.get("created_at"),
    }


def build_wirebox_controller(
    client: WireboxClient,
    mailbox_address: str,
) -> Controller:
    """Construct a Browser Use Controller equipped with Wirebox email capabilities."""
    controller = Controller()

    @controller.registry.action(
        "Get the agent's sovereign Wirebox email address",
        param_model=GetAgentEmailArgs,
    )
    async def get_agent_email(params: GetAgentEmailArgs) -> ActionResult:
        return ActionResult(
            extracted_content=f"Your official Wirebox email address is: {mailbox_address}",
            long_term_memory=f"Agent mailbox address: {mailbox_address}",
        )

    @controller.registry.action(
        "List recent emails in the agent's Wirebox mailbox",
        param_model=CheckInboxArgs,
    )
    async def check_inbox(params: CheckInboxArgs) -> ActionResult:
        messages = await client.list_messages(mailbox_address, limit=params.limit)
        if not messages:
            return ActionResult(extracted_content="Your inbox is currently empty.")

        summaries = []
        for m in messages:
            summaries.append({
                "id": m.get("id"),
                "from": m.get("from"),
                "subject": m.get("subject"),
                "snippet": m.get("snippet"),
                "created_at": m.get("created_at"),
            })
        return ActionResult(extracted_content=json.dumps(summaries, indent=2))

    @controller.registry.action(
        "Read the full content of an email by message ID (includes text and detected confirmation links)",
        param_model=ReadEmailArgs,
    )
    async def read_email(params: ReadEmailArgs) -> ActionResult:
        try:
            msg = await client.get_message(mailbox_address, params.message_id)
            formatted = _format_message_content(msg)
            return ActionResult(extracted_content=json.dumps(formatted, indent=2))
        except Exception as err:
            return ActionResult(error=f"Failed to fetch message {params.message_id}: {str(err)}")

    @controller.registry.action(
        "Wait and poll for an incoming email matching criteria (e.g. OTP code or confirmation link)",
        param_model=WaitForEmailArgs,
    )
    async def wait_for_email(params: WaitForEmailArgs) -> ActionResult:
        email = await client.wait_for_email(
            mailbox_address,
            subject_contains=params.subject_contains,
            from_contains=params.from_contains,
            timeout_seconds=params.timeout_seconds,
        )
        if not email:
            return ActionResult(
                extracted_content=(
                    f"Timed out after {params.timeout_seconds}s waiting for email matching "
                    f"subject='{params.subject_contains}', from='{params.from_contains}'."
                )
            )

        formatted = _format_message_content(email)
        formatted["status"] = "received"
        return ActionResult(
            extracted_content=json.dumps(formatted, indent=2),
            long_term_memory=f"Received email '{email.get('subject')}' from {email.get('from')}",
        )

    @controller.registry.action(
        "Send an outbound email from the agent's Wirebox address",
        param_model=SendEmailArgs,
    )
    async def send_email(params: SendEmailArgs) -> ActionResult:
        try:
            res = await client.send_message(
                mailbox_address,
                to=params.to,
                subject=params.subject,
                body_text=params.body_text,
            )
            return ActionResult(
                extracted_content=f"Email sent successfully. Message ID: {res.get('id', 'sent')}",
                long_term_memory=f"Sent email to {params.to} with subject '{params.subject}'",
            )
        except Exception as err:
            return ActionResult(error=f"Failed to send email: {str(err)}")

    return controller
