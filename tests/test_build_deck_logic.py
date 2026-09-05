"""Host tests for the pure (stdlib) logic of tools/build_deck.py.

build_deck imports genanki at module load, so on a host without genanki the
module cannot even be imported. A minimal fake genanki is injected into
sys.modules ONLY for the duration of the load (and only if the real one is
absent), then removed again — so test_build_smoke.py still decides genanki
availability for itself. This lets the pure logic (stable_id, box clamping,
cloze numbering) be tested on the host and in CI regardless of genanki.
"""
from html.parser import HTMLParser
import sys
import types
import unittest

from _tools import load


def _fake_genanki():
    m = types.ModuleType("genanki")

    class Model:
        CLOZE = 1

        def __init__(self, model_id, name, **kw):
            self.model_id, self.name, self.kw = model_id, name, kw

    class Deck:
        def __init__(self, deck_id, name, description=""):
            self.deck_id, self.name, self.description = deck_id, name, description
            self.notes = []

        def add_note(self, note):
            self.notes.append(note)

    class Note:
        def __init__(self, model=None, fields=None, tags=None, guid=None):
            self.model, self.fields, self.tags, self.guid = model, fields, tags, guid

    class Package:
        def __init__(self, decks):
            self.decks, self.media_files = decks, []

        def write_to_file(self, path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("fake")

    def guid_for(*args):
        return "guid-" + ":".join(str(a) for a in args)

    m.Model, m.Deck, m.Note, m.Package, m.guid_for = Model, Deck, Note, Package, guid_for
    return m


try:
    import genanki  # noqa: F401  (real dependency present, e.g. in CI/container)
    bd = load("build_deck")
except ImportError:
    _prev = sys.modules.get("genanki")
    sys.modules["genanki"] = _fake_genanki()
    try:
        bd = load("build_deck")
    finally:  # leave sys.modules as we found it — do not poison other test modules
        if _prev is None:
            sys.modules.pop("genanki", None)
        else:
            sys.modules["genanki"] = _prev


class TestStableIdFreeze(unittest.TestCase):
    # These IDs are baked into every user's Anki collection (note-type and deck
    # IDs). A change means a refactor silently drifted the seed strings or the
    # hashing — which would create DUPLICATE note types on re-import and
    # disconnect already-learned decks. If this test fails, do NOT edit the
    # numbers to make it pass: find what changed stable_id and revert it.
    FROZEN = {
        "anki-karten:basic-model:v1": 1776014608,
        "anki-karten:cloze-model:v1": 786786125,
        "anki-karten:typein-model:v1": 761558241,
        "anki-karten:reversed-model:v1": 110796264,
        "anki-karten:occlusion-model:v1": 1990443147,
    }

    def test_frozen_seed_values(self):
        for seed, expected in self.FROZEN.items():
            self.assertEqual(bd.stable_id(seed), expected, seed)

    def test_model_objects_carry_the_frozen_ids(self):
        self.assertEqual(bd.BASIC_MODEL.model_id, self.FROZEN["anki-karten:basic-model:v1"])
        self.assertEqual(bd.CLOZE_MODEL.model_id, self.FROZEN["anki-karten:cloze-model:v1"])
        self.assertEqual(bd.TYPEIN_MODEL.model_id, self.FROZEN["anki-karten:typein-model:v1"])
        self.assertEqual(bd.REVERSED_MODEL.model_id, self.FROZEN["anki-karten:reversed-model:v1"])
        self.assertEqual(bd.OCCLUSION_MODEL.model_id, self.FROZEN["anki-karten:occlusion-model:v1"])

    def test_deterministic(self):
        self.assertEqual(bd.stable_id("some deck"), bd.stable_id("some deck"))

    def test_within_anki_32bit_range(self):
        for seed in ("a", "deck:Example", "Ümläüt::Deck", "x" * 200):
            v = bd.stable_id(seed)
            self.assertGreaterEqual(v, 1)
            self.assertLessEqual(v, 2**31 - 1)


class TestClozeNumbers(unittest.TestCase):
    def test_collects_sorted_unique(self):
        self.assertEqual(bd._cloze_numbers("a {{c2::x}} b {{c1::y}} {{c2::z}}"), [1, 2])

    def test_none_without_deletions(self):
        self.assertEqual(bd._cloze_numbers("no deletions here"), [])


class TestBoxStyleClamp(unittest.TestCase):
    def test_padding_never_leaves_0_1(self):
        # A region flush against every edge: the padded box must stay within 0..1.
        style = bd._box_style({"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0})
        import re
        vals = [float(p) for p in re.findall(r"([\d.]+)%", style)]
        self.assertTrue(all(0.0 <= v <= 100.0001 for v in vals), style)


class TestOcclusionTargets(unittest.TestCase):
    REGIONS = [
        {"label": "INPUT", "x": .1, "y": .2, "w": .2, "h": .1},
        {"label": "OUTPUT", "x": .6, "y": .2, "w": .2, "h": .1},
    ]

    @staticmethod
    def masks(markup):
        class Masks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.items = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if "io-mask" in attrs.get("class", "").split():
                    self.items.append(attrs)

        parser = Masks()
        parser.feed(markup)
        return parser.items

    def render(self, target, mode, reveal=False):
        return bd._occlusion_html("diagram.png", self.REGIONS, target, mode,
                                  reveal, "Name the queried block.", "")

    def test_hide_all_questions_identify_different_targets_without_revealing_labels(self):
        fronts = [self.render(target, "hide-all") for target in range(2)]
        self.assertNotEqual(fronts[0], fronts[1])
        for target, front in enumerate(fronts):
            with self.subTest(target=target):
                masks = self.masks(front)
                self.assertEqual(len(masks), 2)  # Both answers remain hidden.
                active = [m for m in masks if "io-mask-target" in m["class"].split()]
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0]["style"], bd._box_style(self.REGIONS[target]))
                self.assertEqual(active[0]["aria-label"], "Question region")
                self.assertIn(">?</span>", front)  # A non-color cue identifies the target.
                for region in self.REGIONS:
                    self.assertNotIn(region["label"], front)

    def test_hide_all_answer_reveals_only_the_queried_region(self):
        for target in range(2):
            with self.subTest(target=target):
                back = self.render(target, "hide-all", reveal=True)
                masks = self.masks(back)
                self.assertEqual(len(masks), 1)
                self.assertEqual(masks[0]["style"], bd._box_style(self.REGIONS[1-target]))
                self.assertNotIn("io-mask-target", back)
                self.assertIn(self.REGIONS[target]["label"], back)
                self.assertNotIn(self.REGIONS[1-target]["label"], back)

    def test_hide_one_keeps_only_its_target_masked(self):
        for target in range(2):
            with self.subTest(target=target):
                front = self.render(target, "hide-one")
                masks = self.masks(front)
                self.assertEqual(len(masks), 1)
                self.assertEqual(masks[0]["style"], bd._box_style(self.REGIONS[target]))
                self.assertNotIn("io-mask-target", front)
                self.assertEqual(self.masks(self.render(target, "hide-one", reveal=True)), [])


if __name__ == "__main__":
    unittest.main()
