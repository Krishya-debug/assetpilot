"""Weekly digest: wraps the latest briefing and (optionally) emails it.

If SMTP settings are unset, the digest is written to output/ only — so the
scheduled GitHub Actions run works with zero email configuration.
"""
from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from . import config


def build_digest(briefing_markdown: str) -> str:
    header = (
        f"# AssetPilot Weekly Digest — {datetime.now():%B %d, %Y}\n\n"
        "Automated run. Numbers below come from the deterministic risk "
        "model; see the method note at the end.\n\n---\n\n"
    )
    return header + briefing_markdown


def save_digest(digest: str) -> str:
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    path = config.OUTPUT_DIR / f"digest_{datetime.now():%Y-%m-%d}.md"
    path.write_text(digest, encoding="utf-8")
    return str(path)


def email_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.DIGEST_TO)


def send_email(digest: str) -> None:
    msg = MIMEText(digest, "plain", "utf-8")
    msg["Subject"] = f"AssetPilot Weekly Digest — {datetime.now():%Y-%m-%d}"
    msg["From"] = config.DIGEST_FROM
    msg["To"] = config.DIGEST_TO

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.DIGEST_FROM, [config.DIGEST_TO], msg.as_string())
