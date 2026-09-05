"""Human names for people who are not using their own (2026-09-05).

`person-e44cc785bd402c06` is not a way to meet anyone. It reads as a case
number, and in a service whose whole purpose is introductions it makes the
first thing you learn about a stranger the least human thing about them.

The second test class is the one that matters most: the display label is what
other participants see, and federated sign-in was putting the provider's real
name there.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.identity.pseudonyms import (  # noqa: E402
    FIGURES,
    ORDINALS,
    QUALITIES,
    combinations,
    generate,
    is_pseudonym,
)


class VocabularyTests(unittest.TestCase):
    def test_the_space_is_large_enough_to_be_worth_calling_a_space(self):
        self.assertGreater(combinations(), 10_000)

    def test_no_word_appears_twice(self):
        self.assertEqual(len(QUALITIES), len(set(QUALITIES)))
        self.assertEqual(len(FIGURES), len(set(FIGURES)))

    def test_every_word_is_a_plain_capitalised_word(self):
        for word in QUALITIES + FIGURES:
            self.assertTrue(word.isalpha(), word)
            self.assertTrue(word[0].isupper(), word)
            self.assertEqual(word, word.strip())

    def test_a_pseudonym_never_implies_a_gender_or_a_body(self):
        """A pseudonym must not accidentally describe the person given it."""
        forbidden = {
            "man", "woman", "boy", "girl", "lady", "gentleman", "sir", "madam",
            "king", "queen", "prince", "princess", "father", "mother", "son",
            "daughter", "old", "young", "fat", "thin", "tall", "short",
            "black", "white", "brown", "yellow", "red",
        }
        for word in QUALITIES + FIGURES:
            self.assertNotIn(word.lower(), forbidden, word)


class RecognitionTests(unittest.TestCase):
    def test_it_recognises_its_own_names(self):
        for _ in range(50):
            self.assertTrue(is_pseudonym(generate()))

    def test_it_recognises_an_ordinal_form(self):
        self.assertTrue(is_pseudonym(f"{QUALITIES[0]} {FIGURES[0]} {ORDINALS[0]}"))

    def test_it_does_not_mistake_anything_else_for_one(self):
        for other in ("person-e44cc785bd402c06", "guest-63de7c", "Dmitry Parshkov",
                      "Ada", "", "   ", "Quiet", "Quiet Lantern the Hundredth",
                      "Quiet person-abc", None, 42):
            self.assertFalse(is_pseudonym(other), repr(other))


class UniquenessTests(unittest.TestCase):
    """Two people meeting under the same name, in a service built for
    introductions, would be worse than an ugly name."""

    def test_it_avoids_every_name_already_taken(self):
        taken = {generate() for _ in range(200)}
        for _ in range(200):
            self.assertNotIn(generate(taken), taken)

    def test_a_collection_and_a_predicate_are_both_accepted(self):
        taken = {generate()}
        self.assertNotIn(generate(taken), taken)
        self.assertNotIn(generate(taken.__contains__), taken)

    def test_a_crowded_space_falls_back_to_an_ordinal_not_a_number(self):
        """Everything is taken except ordinal forms."""
        def crowded(name: str) -> bool:
            return not any(name.endswith(ordinal) for ordinal in ORDINALS)

        name = generate(crowded)
        self.assertTrue(is_pseudonym(name), name)
        self.assertTrue(any(name.endswith(o) for o in ORDINALS), name)
        self.assertNotRegex(name, r"\d")

    def test_it_refuses_rather_than_repeat_a_name(self):
        with self.assertRaises(RuntimeError):
            generate(lambda _name: True)


class WhatOthersSeeTests(unittest.TestCase):
    def setUp(self):
        from src.product.server import build_runtime
        self.runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=False)
        self.identity = self.runtime.identity

    def test_the_provider_name_never_becomes_the_display_label(self):
        creds = self.identity.sign_in_federated(
            provider="google", subject="s1", email="ada@example.test",
            email_verified=True, display_label="Ada Lovelace")
        label = self.identity.backend.get_user(creds.user_id).display_label
        self.assertTrue(is_pseudonym(label), label)
        self.assertNotIn("Ada", label)
        self.assertNotIn("Lovelace", label)

    def test_the_real_name_is_kept_where_only_its_owner_can_read_it(self):
        creds = self.identity.sign_in_federated(
            provider="google", subject="s1", email="ada@example.test",
            email_verified=True, display_label="Ada Lovelace")
        self.assertEqual(self.identity.identity_claims(creds.user_id)["name"],
                         "Ada Lovelace")

    def test_an_account_without_a_sign_in_still_gets_a_name(self):
        creds = self.identity.register_guest()
        label = self.identity.backend.get_user(creds.user_id).display_label
        self.assertTrue(is_pseudonym(label), label)
        self.assertNotIn("guest-", label)

    def test_two_accounts_never_share_a_name(self):
        labels = set()
        for _ in range(40):
            creds = self.identity.register_guest()
            label = self.identity.backend.get_user(creds.user_id).display_label
            self.assertNotIn(label, labels)
            labels.add(label)


class BackfillTests(unittest.TestCase):
    """Accounts created before this existed still carry the wrong label, and
    for federated accounts that label is the person's real name."""

    def setUp(self):
        from src.product.server import build_runtime
        self.runtime = build_runtime(
            ":memory:", allowed_origins=frozenset({"http://127.0.0.1"}), seed=False)
        self.identity = self.runtime.identity

    def _label(self, user_id):
        return self.identity.backend.get_user(user_id).display_label

    def _assign(self, mode):
        from src.product.server import startup_assign_pseudonyms
        return startup_assign_pseudonyms(self.runtime,
                                         {"RESONANCE_ASSIGN_PSEUDONYMS": mode})

    def test_unset_does_nothing_at_all(self):
        from src.product.server import startup_assign_pseudonyms
        self.assertIsNone(startup_assign_pseudonyms(self.runtime, {}))

    def test_report_counts_without_renaming_anyone(self):
        creds = self.identity.register("Dmitry Parshkov")
        result = self._assign("report")
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["assigned"], 1)
        self.assertEqual(self._label(creds.user_id), "Dmitry Parshkov")

    def test_a_real_name_is_replaced_by_a_pseudonym(self):
        creds = self.identity.register("Dmitry Parshkov")
        self._assign("1")
        self.assertTrue(is_pseudonym(self._label(creds.user_id)))

    def test_an_account_that_already_has_one_is_left_alone(self):
        creds = self.identity.register_guest()
        before = self._label(creds.user_id)
        result = self._assign("1")
        self.assertEqual(result["assigned"], 0)
        self.assertEqual(self._label(creds.user_id), before)

    def test_running_it_twice_changes_nothing_the_second_time(self):
        self.identity.register("Dmitry Parshkov")
        self.identity.register("guest-63de7c")
        self.assertEqual(self._assign("1")["assigned"], 2)
        self.assertEqual(self._assign("1")["assigned"], 0)

    def test_it_never_hands_two_accounts_the_same_name(self):
        for index in range(30):
            self.identity.register(f"legacy-{index}")
        self._assign("1")
        labels = [str(u.display_label) for u in self.runtime.live.repo.list_users()]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertTrue(all(is_pseudonym(name) for name in labels))


if __name__ == "__main__":
    unittest.main()
