"""Tests for graph.py — LangGraph workflow structure."""

from graph import graph, should_retry


class TestShouldRetry:
    def test_retries_when_no_conflicts_and_low_iterations(self, sample_state):
        sample_state["conflicts"] = []
        sample_state["iterations"] = 1
        assert should_retry(sample_state) == "fetch_news"

    def test_proceeds_when_conflicts_found(self, sample_state):
        sample_state["conflicts"] = ["conflict"]
        sample_state["iterations"] = 1
        assert should_retry(sample_state) == "generate_report"

    def test_proceeds_when_max_iterations(self, sample_state):
        sample_state["conflicts"] = []
        sample_state["iterations"] = 2
        assert should_retry(sample_state) == "generate_report"


class TestGraphStructure:
    def test_has_all_nodes(self):
        node_names = set(graph.nodes.keys())
        expected = {"fetch_news", "analyze_news", "find_conflicts", "generate_report", "__start__"}
        assert expected.issubset(node_names)
