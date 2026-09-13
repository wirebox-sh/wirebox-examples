"""Agent orchestration for Browser Use + Wirebox."""

from __future__ import annotations

import logging
import os
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from browser_use.agent import Agent
from browser_use.browser import BrowserSession

from src.client import WireboxClient
from src.config import settings
from src.tools import build_wirebox_controller

logger = logging.getLogger("wirebox-browser-use")

SYSTEM_PROMPT_TEMPLATE = """
You are an autonomous AI agent equipped with a real Chromium web browser and a sovereign Wirebox email inbox.

## Your Telecom & Identity:
- Sovereign Email Address: {email}
- You fully own and control this email address. You can receive, read, wait for, and send emails through Wirebox.

## Behavioral Guidelines:
1. **Account Signups & Authentication**:
   - Whenever a website or service prompts for an email address, ALWAYS use your Wirebox address: `{email}`.
   - Never use fake or placeholder emails. Your address is live on the internet and ready to receive real email.

2. **Email Verification Codes (OTP) & Confirmation Links (Magic Links)**:
   - When a website displays "We sent a verification code to your email" or prompts to check email for a confirmation link:
   - Call the `wait_for_email` tool. Tip: match `from_contains` (e.g. `wait_for_email(from_contains="firecrawl")`) rather than guessing an exact subject line.
   - Look at the returned email content:
     * If `detected_links` contains a confirmation URL (e.g. `https://.../verify?token=...`), IMMEDIATELY use the `navigate` tool to open that link in the browser to complete account activation!
     * If the email contains a numeric OTP code (e.g. 6 digits), enter the code into the input field on the page.

3. **Autonomous Navigation**:
   - Think step-by-step.
   - If asked to sign up and extract an API key (e.g. on Firecrawl or Linear), navigate to the API Keys / Settings / Dashboard section after login, create or copy the key, and output it in your final summary.
"""


def create_llm(model_name: str = "") -> Any:
    """Instantiate the appropriate LLM client based on available credentials."""
    model = model_name or settings.llm_model

    # 1. DeepSeek (either explicit model name or deepseek base_url)
    if "deepseek" in model.lower() or "deepseek" in settings.openai_api_base.lower():
        from browser_use.llm import ChatDeepSeek
        return ChatDeepSeek(
            model=model if "deepseek" in model.lower() else "deepseek-chat",
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base or "https://api.deepseek.com/v1",
        )

    # 2. Browser Use Cloud LLM (if BROWSER_USE_API_KEY is provided and model is bu-)
    if settings.browser_use_api_key and (not model or "bu-" in model.lower()):
        from browser_use.llm import ChatBrowserUse
        return ChatBrowserUse(
            model=model or "bu-2-0",
            api_key=settings.browser_use_api_key,
        )

    # 3. Anthropic Claude (if ANTHROPIC_API_KEY is provided)
    if settings.anthropic_api_key and ("claude" in model.lower() or not settings.openai_api_key):
        from browser_use.llm import ChatAnthropic
        return ChatAnthropic(
            model=model if "claude" in model else "claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
        )

    # 4. OpenAI / Compatible (if OPENAI_API_KEY is provided)
    if settings.openai_api_key:
        from browser_use.llm import ChatOpenAI
        return ChatOpenAI(
            model=model if model and not model.startswith("bu-") else "gpt-4o",
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base or None,
        )

    # 5. Fallback validation if no keys exist
    settings.validate_llm()


def ensure_profile_available(profile_dir: str) -> None:
    """Terminate lingering Chrome processes using profile_dir and clear stale Singleton locks.

    Chromium refuses to bind a fresh remote debugging CDP port to an existing user data directory
    if a previous Chrome instance is still holding the directory or locks.
    """
    import subprocess
    import shutil

    # 1. Terminate any previous Chrome process attached to this specific profile
    try:
        subprocess.run(
            ["pkill", "-f", profile_dir],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # 2. Clean up stale SingletonLock / SingletonSocket symlinks
    for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock_path = os.path.join(profile_dir, lock_name)
        if os.path.islink(lock_path) or os.path.exists(lock_path):
            try:
                os.unlink(lock_path)
            except Exception:
                pass


async def run_wirebox_agent(
    task: str,
    client: WireboxClient,
    mailbox_address: str,
    headless: bool = False,
    max_steps: int = 40,
    browser_stay_open: bool = False,
) -> str:
    """Execute a web browsing task with autonomous Wirebox email verification.

    Args:
        task: Natural language goal for the agent (e.g., 'Sign up on firecrawl.dev and get an API key').
        client: Authenticated WireboxClient instance.
        mailbox_address: Agent's active Wirebox email.
        headless: If True, runs browser without GUI. False displays the live browser window.
        max_steps: Maximum number of execution steps before terminating.
        browser_stay_open: If True, keeps browser window open after completion.

    Returns:
        The final result text produced by the agent.
    """
    logger.info("Initializing Wirebox agent for %s", mailbox_address)

    # 1. Build Controller with Wirebox email actions
    controller = build_wirebox_controller(client, mailbox_address)

    # 2. Build system prompt with agent's real email
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(email=mailbox_address)

    # 3. Configure browser session with persistent profile for window position memory
    profile_dir = os.path.expanduser("~/.cache/wirebox/browser-profile")
    os.makedirs(profile_dir, exist_ok=True)
    ensure_profile_available(profile_dir)

    browser_session = BrowserSession(
        user_data_dir=profile_dir,
        headless=headless,
        disable_security=False,
        enable_default_extensions=False,
        keep_alive=browser_stay_open,
    )

    # 4. Resolve LLM
    llm = create_llm(settings.llm_model)

    # 5. Determine vision capability
    use_vision = True
    if hasattr(llm, "provider") and llm.provider == "deepseek":
        use_vision = False
    elif "deepseek" in getattr(llm, "model", "").lower():
        use_vision = False

    # 6. Instantiate Browser Use Agent
    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session,
        controller=controller,
        use_vision=use_vision,
        extend_system_message=system_prompt,
    )

    try:
        logger.info("Starting browser agent run for task: %s", task)
        history = await agent.run(max_steps=max_steps)
        final_text = history.final_result() or "Task completed."
        return final_text
    finally:
        if not browser_stay_open:
            await browser_session.close()
        else:
            logger.info("Browser window remains open (--browser-stay-open enabled).")


async def setup_window_layout() -> None:
    """Launch a browser window and pause so the user can position and resize it before recording."""
    profile_dir = os.path.expanduser("~/.cache/wirebox/browser-profile")
    os.makedirs(profile_dir, exist_ok=True)
    ensure_profile_available(profile_dir)

    print("\n" + "=" * 60)
    print("🖥️  Wirebox Browser Window Setup")
    print("=" * 60)
    print("Launching browser window...")
    session = BrowserSession(
        user_data_dir=profile_dir,
        headless=False,
        disable_security=False,
        enable_default_extensions=False,
    )
    await session.start()
    print("\n✅ Browser window is open!")
    print("👉 Drag and resize the browser window to your desired position (e.g. right 50-60% of screen).")
    print("👉 Align your terminal on the left side.")
    print("-" * 60)
    try:
        input("Press [Enter] here once you're satisfied with the window layout...")
    except (EOFError, KeyboardInterrupt):
        pass
    await session.close()
    print("🎉 Window layout saved! Future agent runs will open at this exact position.\n")
