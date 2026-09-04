"""Release guard for the PostgreSQL migration runner's simple `;` splitter.

Until the runner is replaced with a real SQL lexer, migration line comments must
not contain semicolons: PostgreSQL receives each split fragment separately and a
semicolon inside `-- ...` can turn the tail of the comment into invalid SQL.
"""

from pathlib import Path
import unittest


MIGRATIONS = Path(__file__).resolve().parents[1] / "ops" / "migrations"


class PostgresMigrationHygieneTests(unittest.TestCase):
    def test_line_comments_do_not_contain_semicolons(self):
        failures = []
        for path in sorted(MIGRATIONS.glob("*.sql")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "--" not in line:
                    continue
                comment = line.split("--", 1)[1]
                if ";" in comment:
                    failures.append(f"{path.name}:{lineno}: {line.strip()}")
        self.assertEqual(
            failures,
            [],
            "PostgreSQL migration runner splits on ';'; semicolons in -- comments break clean startup:\n"
            + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
