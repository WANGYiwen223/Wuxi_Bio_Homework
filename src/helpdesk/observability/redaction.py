"""Conservative redaction for transcripts and diagnostic messages."""

import re


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9_.-]+)\b", "[REDACTED]", text, flags=re.I)
    return re.sub(r"(?i)\b(password|passwd|otp|api[_ -]?key)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
