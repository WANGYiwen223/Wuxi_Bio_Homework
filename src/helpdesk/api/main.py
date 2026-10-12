from pathlib import Path

from helpdesk.api.app import create_app
from helpdesk.bootstrap.runtime import Runtime

ROOT = Path(__file__).resolve().parents[3]
app = create_app(Runtime.local(ROOT), ROOT / "ui")
