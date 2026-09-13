"""Command-line entrypoint for wirebox-browser-use."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from src.agent import run_wirebox_agent
from src.client import WireboxClient
from src.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wirebox-cli")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wirebox + Browser Use: Autonomous web agent with sovereign email inboxes.",
    )
    parser.add_argument(
        "task",
        nargs="?",
        default="Go to firecrawl.dev, sign up for a free account using my Wirebox email, verify the OTP code, and fetch the API key.",
        help="The natural language task for the agent to execute.",
    )
    parser.add_argument(
        "--email",
        type=str,
        default="",
        help="Wirebox email address to use (defaults to WIREBOX_EMAIL env var).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Wirebox API key (defaults to WIREBOX_API_KEY env var).",
    )
    parser.add_argument(
        "--human-email",
        type=str,
        default="",
        help="Human overseer email to use for automatic zero-friction agent signup.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default False to show live browser window).",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=40,
        help="Maximum agent execution steps (default 40).",
    )
    parser.add_argument(
        "--browser-stay-open",
        action="store_true",
        help="Keep the browser window open after task completion (ideal for video recording and inspection).",
    )
    parser.add_argument(
        "--setup-window",
        action="store_true",
        help="Open a browser window now so you can resize and position it before recording.",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()

    if args.setup_window:
        from src.agent import setup_window_layout
        await setup_window_layout()
        return

    api_key = args.api_key or settings.wirebox_api_key
    email_address = args.email or settings.wirebox_email
    client = WireboxClient(api_key=api_key, base_url=settings.wirebox_api_url)

    # If no credentials found in env or CLI args, perform autonomous self-signup!
    if not api_key or not email_address:
        print("\n⚡️ No Wirebox credentials detected.")
        human_email = args.human_email
        if not human_email:
            try:
                human_email = input("Enter your email for agent oversight verification: ").strip()
            except EOFError:
                human_email = "agent-operator@example.com"

        if not human_email:
            print("❌ Human email required for agent self-signup. Aborting.")
            sys.exit(1)

        print(f"🚀 Registering a fresh autonomous Wirebox mailbox for '{human_email}'...")
        try:
            signup_res = await client.signup(
                human_email=human_email,
                display_name="Browser Use Assistant",
            )
            api_key = signup_res.get("api_key", "")
            email_address = signup_res.get("email_address", "")
            print(f"✅ Mailbox provisioned: \033[1;32m{email_address}\033[0m")
            print(f"🔑 Scoped API key: {api_key[:12]}...")
            print("💡 Tip: Save these to your .env file as WIREBOX_API_KEY and WIREBOX_EMAIL.\n")
        except Exception as err:
            print(f"❌ Failed to auto-register Wirebox mailbox: {err}")
            sys.exit(1)

    print("=" * 60)
    print("🤖 Wirebox + Browser Use Autonomous Agent")
    print(f"📬 Mailbox Address : {email_address}")
    print(f"🎯 Target Goal     : {args.task}")
    print(f"🖥️  Browser Mode    : {'Headless' if args.headless else 'Live GUI (Visible)'}")
    if args.browser_stay_open:
        print("📌 Stay Open       : Enabled (browser will not close)")
    print("=" * 60 + "\n")

    try:
        result = await run_wirebox_agent(
            task=args.task,
            client=client,
            mailbox_address=email_address,
            headless=args.headless,
            max_steps=args.steps,
            browser_stay_open=args.browser_stay_open,
        )
        print("\n" + "=" * 60)
        print("🎉 Task Completed! Agent Output:")
        print("=" * 60)
        print(result)
        print("=" * 60 + "\n")
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user.")
    except Exception as err:
        print(f"\n❌ Execution error: {err}")
        sys.exit(1)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
