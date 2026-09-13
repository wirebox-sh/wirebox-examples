"""Runtime configuration for wirebox-browser-use."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    wirebox_api_key: str = os.getenv("WIREBOX_API_KEY", "").strip()
    wirebox_email: str = os.getenv("WIREBOX_EMAIL", "").strip()
    wirebox_api_url: str = os.getenv("WIREBOX_API_URL", "https://api.wirebox.sh/v1").rstrip("/")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_api_base: str = os.getenv("OPENAI_API_BASE", os.getenv("OPENAI_BASE_URL", "")).strip()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    browser_use_api_key: str = os.getenv("BROWSER_USE_API_KEY", "").strip()
    llm_model: str = os.getenv("LLM_MODEL", "").strip()

    def validate_llm(self) -> None:
        if not self.openai_api_key and not self.anthropic_api_key and not self.browser_use_api_key:
            raise ValueError(
                "Missing LLM API key. Please provide at least one in your .env file: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or BROWSER_USE_API_KEY."
            )


settings = Settings()
