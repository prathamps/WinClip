"""Contract tests for the shell-history adapter."""

from winclip.adapters.driven.shell_history import ShellHistorySource


def make_home(tmp_path):
    (tmp_path / ".local" / "share" / "fish").mkdir(parents=True)
    return tmp_path


class TestShellHistorySource:
    def test_reads_bash_history(self, tmp_path):
        home = make_home(tmp_path)
        (home / ".bash_history").write_text("docker ps\ngit status\n")
        assert ShellHistorySource(home).recent_commands() == [
            "docker ps",
            "git status",
        ]

    def test_reads_zsh_plain_and_extended_formats(self, tmp_path):
        home = make_home(tmp_path)
        (home / ".zsh_history").write_text(
            ": 1699999999:0;kubectl get pods\n"
            "plain command\n"
            ": 1700000000:5;docker compose up\n"
        )
        assert ShellHistorySource(home).recent_commands() == [
            "kubectl get pods",
            "plain command",
            "docker compose up",
        ]

    def test_zsh_multiline_commands_keep_first_line_only(self, tmp_path):
        home = make_home(tmp_path)
        (home / ".zsh_history").write_text(
            ": 1700000000:0;echo one \\\n"
            "two\n"
            ": 1700000001:0;git log\n"
        )
        assert ShellHistorySource(home).recent_commands() == [
            "echo one",
            "git log",
        ]

    def test_reads_fish_history(self, tmp_path):
        home = make_home(tmp_path)
        (home / ".local" / "share" / "fish" / "fish_history").write_text(
            "- cmd: npm run build\n"
            "  when: 1700000000\n"
            "- cmd: cargo test\n"
            "  when: 1700000001\n"
        )
        assert ShellHistorySource(home).recent_commands() == [
            "npm run build",
            "cargo test",
        ]

    def test_merges_all_shells_and_missing_files_are_fine(self, tmp_path):
        home = make_home(tmp_path)
        (home / ".bash_history").write_text("from bash\n")
        # no zsh, no fish content
        assert ShellHistorySource(home).recent_commands() == ["from bash"]

    def test_empty_home_yields_empty_history(self, tmp_path):
        assert ShellHistorySource(make_home(tmp_path)).recent_commands() == []
