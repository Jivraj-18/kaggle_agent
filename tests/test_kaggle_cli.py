import unittest

from kaggle_agent.kaggle_cli import parse_json_output


class ParseJsonOutputTests(unittest.TestCase):
    def test_parses_clean_json_array(self):
        self.assertEqual(parse_json_output('[{"a": 1}]', default=[]), [{"a": 1}])

    def test_skips_next_page_token_preamble(self):
        # Real `kaggle competitions leaderboard --show --format json` output when
        # there are more results than --page-size: a plain-text banner line on
        # stdout before the JSON array, which plain json.loads chokes on.
        stdout = (
            "Next Page Token = CfDJ8EgiEKLz2SFKpKvT-xxAYKK8MqgdQWe9VME165oybsW9\n"
            '[\n  {"teamName": "x", "score": "0.1"}\n]\n'
        )
        self.assertEqual(parse_json_output(stdout, default=[]), [{"teamName": "x", "score": "0.1"}])

    def test_empty_stdout_returns_default(self):
        self.assertEqual(parse_json_output("", default=[]), [])
        self.assertEqual(parse_json_output("   ", default=[]), [])

    def test_no_json_marker_returns_default(self):
        self.assertEqual(parse_json_output("No competitions found", default=[]), [])


if __name__ == "__main__":
    unittest.main()
