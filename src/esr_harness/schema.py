"""Export syntactic schemas from the executable contract (runtime checks remain required)."""
import json
from pathlib import Path
from .protocol import SCHEMAS, STATE_SCHEMA, AUDIT_SCHEMA, obj


def export(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    schemas = {"state.schema.json": STATE_SCHEMA, "audit.schema.json": AUDIT_SCHEMA,
               "actions.schema.json": {"oneOf": [obj({"action": {"enum": [name]}, "arguments": schema})
                                                  for name, schema in SCHEMAS.items()]}}
    for name, schema in schemas.items():
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
        (directory/name).write_text(json.dumps(schema, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser(description="Export current syntactic schemas, not semantic certificates")
    p.add_argument("directory")
    export(p.parse_args().directory)
