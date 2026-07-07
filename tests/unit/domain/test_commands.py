from winclip.domain import CommandHistoryPolicy

HISTORY = [
    "docker ps",
    "git status",
    "docker compose up -d",
    "npm install",
    "sudo docker restart web",
    "ls -la",
    "PORT=8080 node server.js",
    "git status",  # duplicate — only the later one should remain
    "docker ps",  # duplicate
    "kubectl get pods",
]


class TestToolOf:
    def setup_method(self):
        self.policy = CommandHistoryPolicy()

    def test_first_token_is_the_tool(self):
        assert self.policy.tool_of("docker ps -a") == "docker"

    def test_wrappers_are_skipped(self):
        assert self.policy.tool_of("sudo docker restart web") == "docker"
        assert self.policy.tool_of("sudo -E env FOO=1 npm ci") == "npm"

    def test_env_var_prefixes_are_skipped(self):
        assert self.policy.tool_of("PORT=8080 node server.js") == "node"

    def test_paths_reduce_to_basename(self):
        assert self.policy.tool_of("/usr/local/bin/k3s kubectl get nodes") == "k3s"
        assert self.policy.tool_of("./scripts/install.sh") == "install.sh"

    def test_shell_noise_is_ignored(self):
        assert self.policy.tool_of("cd ..") is None
        assert self.policy.tool_of("ls -la") is None
        assert self.policy.tool_of("") is None

    def test_unbalanced_quotes_do_not_crash(self):
        assert self.policy.tool_of("echo 'unterminated") == "echo"


class TestEntries:
    def setup_method(self):
        self.policy = CommandHistoryPolicy()

    def test_most_recent_first_and_deduplicated(self):
        entries = self.policy.entries(HISTORY)
        commands = [e.command for e in entries]
        assert commands[0] == "kubectl get pods"
        assert commands.count("git status") == 1
        assert commands.count("docker ps") == 1
        # "ls -la" is shell noise and dropped entirely.
        assert "ls -la" not in commands

    def test_duplicate_keeps_most_recent_position(self):
        entries = self.policy.entries(HISTORY)
        commands = [e.command for e in entries]
        # The most recent "docker ps" (index 8) is newer than
        # "npm install" (index 3).
        assert commands.index("docker ps") < commands.index("npm install")


class TestToolRanking:
    def setup_method(self):
        self.policy = CommandHistoryPolicy()

    def test_counts_are_aggregated_per_tool(self):
        tools = {u.tool: u for u in self.policy.tools(HISTORY)}
        assert tools["docker"].count == 3
        assert tools["git"].count == 1

    def test_frequent_tools_rank_first(self):
        ranked = [u.tool for u in self.policy.tools(HISTORY)]
        assert ranked[0] == "docker"

    def test_recent_burst_beats_stale_volume(self):
        # "old" used 5 times long ago; "new" used 3 times recently.
        history = ["old build"] * 5 + ["filler xyz"] * 200 + ["new deploy"] * 3
        ranked = [u.tool for u in self.policy.tools(history)]
        assert ranked.index("new") < ranked.index("old")


class TestCommandsFor:
    def setup_method(self):
        self.policy = CommandHistoryPolicy()

    def test_filter_by_tool(self):
        docker = self.policy.commands_for(HISTORY, "docker")
        assert {e.tool for e in docker} == {"docker"}
        assert len(docker) == 3

    def test_no_tool_means_everything(self):
        assert len(self.policy.commands_for(HISTORY, None)) == 7

    def test_query_filters_case_insensitively(self):
        result = self.policy.commands_for(HISTORY, None, query="COMPOSE")
        assert [e.command for e in result] == ["docker compose up -d"]
