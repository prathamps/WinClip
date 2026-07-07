from winclip.adapters.driven.json_settings import JsonSettingsRepository
from winclip.domain import Settings


class TestJsonSettings:
    def test_missing_file_yields_defaults(self, tmp_path):
        repo = JsonSettingsRepository(tmp_path / "settings.json")
        assert repo.load() == Settings()

    def test_roundtrip(self, tmp_path):
        repo = JsonSettingsRepository(tmp_path / "settings.json")
        custom = Settings(max_items=10, capture_images=False, auto_paste=False)
        repo.save(custom)
        assert repo.load() == custom

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{not json")
        assert JsonSettingsRepository(path).load() == Settings()

    def test_unknown_keys_are_ignored(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text('{"max_items": 7, "from_the_future": true}')
        assert JsonSettingsRepository(path).load().max_items == 7

    def test_invalid_values_fall_back_to_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text('{"max_items": -5}')
        assert JsonSettingsRepository(path).load() == Settings()
