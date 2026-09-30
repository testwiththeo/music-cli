"""Port of the TypeScript tests/playback-controls.test.ts."""

import unittest

from music_cli.playback_controls import SEEK_SECONDS, is_escape_key, seek_offset_for_key


class PlaybackControlsTest(unittest.TestCase):
    def test_maps_arrow_keys_to_five_second_seek_offsets(self):
        self.assertEqual(seek_offset_for_key(b"\x1b[D"), -SEEK_SECONDS)
        self.assertEqual(seek_offset_for_key(b"\x1b[C"), SEEK_SECONDS)

    def test_does_not_confuse_arrow_key_escape_sequences_with_escape(self):
        self.assertTrue(is_escape_key(b"\x1b"))
        self.assertFalse(is_escape_key(b"\x1b[D"))
        self.assertFalse(is_escape_key(b"\x1b[C"))

    def test_ignores_other_keys(self):
        self.assertIsNone(seek_offset_for_key(b"a"))
        self.assertFalse(is_escape_key(b"\x1b[C"))


if __name__ == "__main__":
    unittest.main()
