# Part of PraetorX. See LICENSE file for full copyright and licensing details.
"""Guards for the App Store listing — the most customer-visible text we ship.

A listing goes stale silently. These tests fail when the page claims a version
the changelog does not know, stops short of the shipped version, points at
images that are not there, or drifts from the store's icon and screenshot
requirements. Template: nextcloud_attachment_sync/tests/test_listing_page.py.
"""
import ast
import pathlib
import re
import struct

from odoo.tests import TransactionCase, tagged

MODULE_ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTING = MODULE_ROOT / "static" / "description" / "index.html"
VERSION_RE = re.compile(r"\b19\.0\.\d+\.\d+\.\d+\b")


@tagged("praetorx_ai_providers", "aip_listing", "post_install", "-at_install")
class TestListingPage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = LISTING.read_text(encoding="utf-8")
        cls.manifest = ast.literal_eval((MODULE_ROOT / "__manifest__.py").read_text(encoding="utf-8"))
        cls.changelog = (MODULE_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_listing_exists(self):
        self.assertTrue(LISTING.is_file())

    def test_no_version_badge_in_the_hero(self):
        hero = self.html.split("<!-- TAB", 1)[0]
        self.assertNotIn("v19.0.", hero, "Versions-Abzeichen im Kopfbereich — der Store zeigt die Manifest-Version selbst.")

    def test_every_version_mentioned_actually_exists(self):
        for version in sorted(set(VERSION_RE.findall(self.html))):
            with self.subTest(version=version):
                self.assertIn(f"[{version}]", self.changelog, f"Die Seite nennt {version}, das CHANGELOG nicht.")

    def test_no_version_is_newer_than_the_module(self):
        current = tuple(int(p) for p in self.manifest["version"].split("."))
        for version in sorted(set(VERSION_RE.findall(self.html))):
            with self.subTest(version=version):
                self.assertLessEqual(tuple(int(p) for p in version.split(".")), current)

    def test_the_current_version_is_on_the_page(self):
        self.assertIn(self.manifest["version"], self.html,
                      f"Die Release-History nennt {self.manifest['version']} nicht — sie ist stehengeblieben.")

    def test_every_declared_image_exists(self):
        for relative in self.manifest.get("images", []):
            with self.subTest(image=relative):
                self.assertTrue((MODULE_ROOT / relative).is_file(), f"__manifest__.py listet {relative}, die Datei fehlt.")

    def test_banner_is_the_store_tile(self):
        self.assertEqual(self.manifest["images"][0], "static/description/banner.png")

    def test_the_listing_shows_the_product(self):
        shots = sorted((MODULE_ROOT / "static" / "description").glob("screenshot_*.png"))
        self.assertTrue(3 <= len(shots) <= 5, f"{len(shots)} Screenshots — gefordert sind 3 bis 5.")
        declared = set(self.manifest.get("images", []))
        for shot in shots:
            with self.subTest(shot=shot.name):
                self.assertIn(f"static/description/{shot.name}", declared, f"{shot.name} ist nicht in `images` deklariert.")
                self.assertIn(shot.name, self.html, f"{shot.name} wird auf der Seite nicht gezeigt.")

    def test_the_app_icon_matches_the_store_specification(self):
        icon = MODULE_ROOT / "static" / "description" / "icon.png"
        header = icon.read_bytes()[:26]
        self.assertEqual(header[12:16], b"IHDR")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual((width, height), (256, 256), f"icon.png ist {width}x{height}.")
        self.assertEqual(header[25], 6, "icon.png ist nicht RGBA.")

    def test_no_internal_references(self):
        without_comments = re.sub(r"<!--.*?-->", "", self.html, flags=re.S)
        for pattern in (r"ADR-\d+", r"\b\w+\.py\b", r"\(#\d{3,4}\)"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, without_comments), f"Interner Verweis ({pattern}) auf der Verkaufsseite.")

    def test_no_external_assets(self):
        self.assertNotIn("<script", self.html.lower())
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', self.html):
            with self.subTest(url=url):
                self.assertTrue(url.startswith(("https://praetorx.net", "https://syntaxandsabotage.io")), f"Externe Ressource: {url}")

    def test_claims_stay_honest(self):
        text = re.sub(r"<[^>]+>", " ", self.html).lower()
        for forbidden in ('guarantees compliance', 'certified'):
            self.assertNotIn(forbidden, text, f"Unhaltbare Zusage auf der Seite: '{forbidden}'")

    def test_faq_has_at_least_five_questions(self):
        faq = self.html.split("<!-- TAB: FAQ -->", 1)[1].split("<!-- TAB:", 1)[0]
        self.assertGreaterEqual(faq.count("<h4"), 5, "Weniger als fünf FAQ-Fragen.")

    def test_legal_footer(self):
        self.assertIn("Anbieter: Lars Weiler", self.html)
        self.assertIn("syntaxandsabotage.io/impressum", self.html)
