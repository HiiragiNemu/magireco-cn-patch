#!/usr/bin/env python3
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class MediaDefaults178Contract(unittest.TestCase):
    def test_modern_native_command_migrates_once(self):
        s=(ROOT/"magica/js/_common/nativeCommand.js").read_text(encoding="utf-8")
        self.assertIn("DATA_SET_DOWNLOAD_CONFIG:26", s)
        self.assertIn("applyCnMediaDefaults178", s)
        self.assertIn('setDownloadConfig({voice:1,movie:2})', s)
        self.assertIn('setDownloadDeleteConfig({voice:0,movie:0})', s)
        self.assertIn('media_defaults_v178', s)
        self.assertIn('CNLocalState', s)

    def test_legacy_command_bridge_has_same_contract(self):
        s=(ROOT/"magica/js/_common/nativeCommand2.js").read_text(encoding="utf-8")
        self.assertIn("DATA_SET_DOWNLOAD_CONFIG: 26", s)
        self.assertIn("SCENE_SET_CONF_DELETE_DATA: 223", s)
        self.assertIn("applyCnMediaDefaults178", s)
        self.assertIn("b.setDownloadConfig({voice:1, movie:2})", s)
        self.assertIn("b.setDownloadDeleteConfig({voice:0, movie:0})", s)

    def test_config_page_starts_from_cn_full_media_defaults(self):
        s=(ROOT/"magica/js/view/config/ConfigTopView.js").read_text(encoding="utf-8")
        self.assertIn(
            "this.resourceConfig.voice=1;this.resourceConfig.deleteVoice=0;"
            "this.resourceConfig.movie=2;this.resourceConfig.deleteMovie=0;", s
        )
        self.assertNotIn(
            "this.resourceConfig.voice=0;this.resourceConfig.deleteVoice=0;"
            "this.resourceConfig.movie=1;this.resourceConfig.deleteMovie=1;", s
        )

if __name__ == "__main__":
    unittest.main()
