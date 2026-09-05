"""HTML image references shared by lint, package building, and previews."""
import unittest

from _tools import load

media = load("_card_media")


class TestCardMedia(unittest.TestCase):
    def test_html_attribute_variations(self):
        for tag in ('<img src = "folder/a.png">', "<IMG SRC = 'folder/a.png'>",
                    '<img src=folder/a.png>', '<img\nsrc\t=\t"folder/a.png" />'):
            with self.subTest(tag=tag):
                self.assertEqual(media.local_image_sources(tag), ["folder/a.png"])
                rendered = media.rewrite_local_images(tag, lambda _: "a.png")
                self.assertEqual(media.local_image_sources(rendered), ["a.png"])
                self.assertNotIn("folder/", rendered)

    def test_uses_actual_src_not_data_attributes_comments_or_script(self):
        markup = ('''<!-- <img src="comment.png"> -->'''
                  '''<script>const x='<img src="script.png">';</script>'''
                  '''<img data-src="lazy.png" title="src='title.png'" src="real.png">''')
        self.assertEqual(media.local_image_sources(markup), ["real.png"])

    def test_preserves_unrelated_html_and_decodes_attribute_entities(self):
        markup = '''before\n<IMG class='card' SRC = 'folder/a&amp;b.png' data-src="other.png">after'''
        self.assertEqual(media.local_image_sources(markup), ["folder/a&b.png"])
        self.assertEqual(media.rewrite_local_images(markup, lambda _: "a&b.png"),
                         markup.replace("folder/", ""))
        # No wholesale HTML serialization: unchanged fields keep GUID inputs.
        self.assertEqual(media.rewrite_local_images(markup, lambda p: p), markup)

    def test_remote_empty_and_data_sources_are_not_local(self):
        markup = ('<img src="https://example/a.png"><img src=//example/a.png>'
                  '<img src="DATA:image/png;base64,AA=="><img src=""><img src>')
        self.assertEqual(media.local_image_sources(markup), [])
        self.assertEqual(media.rewrite_local_images(markup, lambda _: "changed"), markup)

    def test_first_duplicate_src_matches_browser_behavior(self):
        self.assertEqual(media.local_image_sources('<img src="first.png" src="second.png">'),
                         ["first.png"])


if __name__ == "__main__":
    unittest.main()
