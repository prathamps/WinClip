import pytest

from winclip.application import ActivateSnippet, QueryCommands
from winclip.domain import CommandHistoryPolicy, Settings


class FakeCommandSource:
    def __init__(self, commands: list[str]) -> None:
        self.commands = commands
        self.reads = 0

    def recent_commands(self) -> list[str]:
        self.reads += 1
        return self.commands


@pytest.fixture
def activate(writer, injector, settings_repo) -> ActivateSnippet:
    return ActivateSnippet(writer, injector, settings_repo)


class TestActivateSnippet:
    def test_copies_and_pastes_text(self, activate, writer, injector):
        result = activate.activate_text("🚀")
        assert writer.texts == ["🚀"]
        assert injector.paste_count == 1
        assert result.copied and result.pasted

    def test_honours_auto_paste_off(self, activate, injector, settings_repo):
        settings_repo.save(Settings(auto_paste=False))
        result = activate.activate_text("Ω")
        assert injector.paste_count == 0
        assert result.copied and not result.pasted


class TestQueryCommands:
    def make(self, settings_repo, commands=("docker ps", "npm install")):
        source = FakeCommandSource(list(commands))
        return source, QueryCommands(
            source, CommandHistoryPolicy(), settings_repo
        )

    def test_lists_tools_and_commands(self, settings_repo):
        _, query = self.make(settings_repo)
        assert [u.tool for u in query.tools()] == ["docker", "npm"]
        assert [e.command for e in query.commands("npm")] == ["npm install"]

    def test_query_filter_passthrough(self, settings_repo):
        _, query = self.make(settings_repo)
        assert [e.command for e in query.commands(None, "PS")] == ["docker ps"]

    def test_privacy_switch_disables_source_entirely(self, settings_repo):
        settings_repo.save(Settings(show_commands=False))
        source, query = self.make(settings_repo)
        assert query.tools() == []
        assert query.commands(None) == []
        assert source.reads == 0, "history files must not be read when disabled"
