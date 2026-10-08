"""Text extraction helpers, cleaning and chunking."""

import unittest

from tests import _env  # noqa: F401  (must be first: sets isolated data folders)
from studio.services.chunking import chunk_text, split_sentences
from studio.services.cleaning import CleaningOptions, clean_text
from studio.services.extraction import extract
from studio.errors import ExtractionError


class CleaningTests(unittest.TestCase):
    def test_dehyphenates_and_joins_wrapped_lines(self):
        raw = "This is a long sen-\ntence that was wrapped\nby a PDF export.\n\n12\n\nNext paragraph."
        cleaned = clean_text(raw)
        self.assertIn("sentence that was wrapped by a PDF export.", cleaned)
        self.assertNotIn("\n12\n", cleaned)
        self.assertIn("Next paragraph.", cleaned)

    def test_page_number_variants_removed(self):
        cleaned = clean_text("Hello world.\n\nPage 4 of 10\n\n- 5 -\n\nGoodbye.")
        self.assertNotIn("Page 4", cleaned)
        self.assertNotIn("- 5 -", cleaned)

    def test_markdown_stripped(self):
        md = "# Title\n\nSome **bold** and *italic* text with a [link](http://x.y) and `code`.\n\n- first\n- second\n\n```\nskip me\n```\n"
        out = clean_text(md, CleaningOptions(strip_markdown=True))
        self.assertIn("Title.", out)
        self.assertIn("Some bold and italic text with a link and code.", out)
        self.assertIn("first.", out)
        self.assertNotIn("skip me", out)
        self.assertNotIn("**", out)

    def test_urls_optional(self):
        out = clean_text("See https://example.com/page now.", CleaningOptions(remove_urls=True))
        self.assertNotIn("https", out)

    def test_normalises_whitespace_and_control_chars(self):
        out = clean_text("a  b\x00​c   d\r\ne")
        self.assertEqual(out.replace("\n", " "), "a bc d e")


class ChunkingTests(unittest.TestCase):
    def test_respects_max_and_keeps_all_text(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(200))
        chunks = chunk_text(text, 300)
        self.assertTrue(all(len(c.text) <= 300 for c in chunks))
        self.assertEqual(" ".join(c.text for c in chunks), text)
        self.assertEqual([c.index for c in chunks], list(range(len(chunks))))

    def test_abbreviations_and_decimals_do_not_split(self):
        sentences = split_sentences("Dr. Smith paid 3.14 dollars. He left. Mr. Jones stayed.")
        self.assertEqual(sentences, ["Dr. Smith paid 3.14 dollars.", "He left.", "Mr. Jones stayed."])

    def test_very_long_sentence_is_split(self):
        text = ("word " * 400).strip() + "."
        chunks = chunk_text(text, 200)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c.text) <= 200 for c in chunks))

    def test_paragraph_boundaries_flagged(self):
        chunks = chunk_text("First paragraph here.\n\nSecond paragraph here.", 450)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(c.ends_paragraph for c in chunks))

    def test_empty_text(self):
        self.assertEqual(chunk_text("   \n\n  ", 450), [])


class ExtractionTests(unittest.TestCase):
    def test_txt_encodings(self):
        self.assertEqual(extract("a.txt", "héllo".encode("utf-8")).text, "héllo")
        self.assertEqual(extract("a.txt", "héllo".encode("cp1252")).text, "héllo")

    def test_markdown_kind(self):
        self.assertEqual(extract("notes.markdown", b"# Hi\n\nthere").kind, "md")

    def test_empty_and_unsupported(self):
        with self.assertRaises(ExtractionError):
            extract("a.txt", b"   \n ")
        with self.assertRaises(ExtractionError):
            extract("a.exe", b"abc")

    def test_corrupt_pdf_gives_friendly_error(self):
        with self.assertRaises(ExtractionError):
            extract("a.pdf", b"not a pdf")


if __name__ == "__main__":
    unittest.main()
