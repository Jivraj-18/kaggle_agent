import unittest

from kaggle_agent.scout import build_scout_item


class ScoutTests(unittest.TestCase):
    def test_build_scout_item_preserves_raw_row(self):
        row = {
            "ref": "https://www.kaggle.com/competitions/heavy-equipment-selling-price-prediction-challenge",
            "deadline": "2026-07-12T18:25:00",
            "category": "Community",
            "teamCount": 2315,
            "futureKaggleField": {"nested": True},
        }
        item = build_scout_item(row, "entered", 3)
        self.assertEqual(item["slug"], "heavy-equipment-selling-price-prediction-challenge")
        self.assertEqual(item["group"], "entered")
        self.assertEqual(item["source_index"], 3)
        self.assertEqual(item["agent_decision"], "pending")
        self.assertEqual(item["raw"], row)


if __name__ == "__main__":
    unittest.main()
