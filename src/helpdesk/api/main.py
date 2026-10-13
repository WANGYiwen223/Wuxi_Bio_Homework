from pathlib import Path

from helpdesk.api.app import create_app
from helpdesk.bootstrap.runtime import Runtime
from helpdesk.observability.events import configure_logging

ROOT = Path(__file__).resolve().parents[3]
runtime = Runtime.local(ROOT)
configure_logging(runtime.settings.run_dir)
app = create_app(runtime, ROOT / "ui")
