"""Save the API contract without starting an HTTP server."""
import json
from pathlib import Path
from services.api.app.main import app

path = Path(__file__).resolve().parents[1] / 'artifacts/openapi.json'
path.write_text(json.dumps(app.openapi(), indent=2))
print(f'Exported {len(app.openapi()["paths"])} OpenAPI routes')

