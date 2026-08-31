import json
import unittest
from pathlib import Path


class SchemaAssetTests(unittest.TestCase):
    def test_json_schema_is_valid_json_and_versioned(self):
        path = Path(__file__).parents[1] / "schemas" / "thought-dna-0.1.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], "thought-dna/0.1")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("relation", schema["$defs"])
        self.assertIn("provenance", schema["$defs"])


if __name__ == "__main__":
    unittest.main()
