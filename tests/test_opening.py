"""Campaign opening state and non-destructive new-game archiving."""
import copy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game import Game
from shop_fixture import stock_shop


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.save = Path(self.folder.name) / "save.json"
        self.g = Game(ROOT / "assets", self.save, random.Random(7))

    def test_fresh_campaign_has_no_free_goods_and_buying_survives_reload(self):
        self.assertEqual(sum(self.g.state["warehouse"].values()), 0)
        self.assertTrue(all(item["quantity"] == 0 for item in self.g.state["stock"]))
        self.assertEqual(self.g.state["shelves"], [None] * 4)
        self.g.action("allocate_attributes",{"allocation":{"luck":5}})
        self.g.action("merchant_buy", {"item_id": "longsword", "quantity": 2})
        self.assertEqual(self.g.state["gold"], 930)
        self.assertEqual(sum(self.g.state["warehouse"].values()), 2)
        self.g.action("place_stock", {"slot": 0, "item_id": "longsword", "quantity": 1, "mode": "bargain", "price": 52})
        restored = Game(ROOT / "assets", self.save)
        self.assertEqual(restored.state["warehouse"]["longsword"], 1)
        self.assertEqual(sum(i["quantity"] for i in restored.state["stock"]), 1)
        self.assertEqual(sum(restored.state["warehouse"].values()), 1)

    def test_prologue_completion_does_not_spend_gold_or_advance_time(self):
        self.assertFalse(self.g.public()["has_progress"])
        self.g.action("allocate_attributes",{"allocation":{"luck":5}})
        before = copy.deepcopy(self.g.state)
        self.g.action("finish_intro", {})
        self.assertTrue(self.g.public()["intro_seen"])
        self.assertTrue(self.g.public()["has_progress"])
        for key in ("gold", "day", "loan", "warehouse", "customers", "shelves", "daily"):
            self.assertEqual(self.g.state[key], before[key])
        self.assertTrue(Game(ROOT / "assets", self.save).public()["intro_seen"])

    def test_new_game_archives_pending_payment_and_resets_campaign(self):
        stock_shop(self.g)
        self.g.action("finish_market", {})
        self.g.action("arrive", {})
        self.g.customer()["budget"] = 1000
        self.g.customer()["willingness"]["longsword"] = 1000
        self.g.action("begin", {"item_id": "longsword"})
        self.g.action("prepare_payment", {})
        original = copy.deepcopy(self.g.state)
        self.g.action("new_game", {})
        backups = list(self.save.parent.glob("save-backup-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8")), original)
        self.assertEqual(self.g.state["gold"], 1000)
        self.assertEqual(self.g.state["day"], 1)
        self.assertIsNone(self.g.state["current_id"])
        self.assertFalse(self.g.state["intro_seen"])
        self.assertEqual(sum(self.g.state["warehouse"].values()), 0)
        self.assertTrue(all(item["quantity"] == 0 for item in self.g.state["stock"]))
        self.assertEqual(self.g.state["shelves"], [None] * 4)
        restored = Game(ROOT / "assets", backups[0])
        self.assertEqual(restored.state["deal"]["status"], "payment")
        self.assertEqual(restored.state["customers"], original["customers"])

    def test_existing_campaign_is_recognized_without_modifying_its_money(self):
        self.g.state["day"] = 8
        self.g.state["gold"] = 731
        self.g.state.pop("intro_seen")
        self.g.save()
        restored = Game(ROOT / "assets", self.save)
        self.assertTrue(restored.public()["has_progress"])
        self.assertTrue(restored.public()["intro_seen"])
        self.assertEqual(restored.state["gold"], 731)
        self.assertEqual(restored.state["day"], 8)

    def test_backup_write_failure_keeps_original_campaign(self):
        self.g.action("allocate_attributes",{"allocation":{"luck":5}})
        self.g.action("finish_market", {})
        original = copy.deepcopy(self.g.state)
        original_file = self.save.read_bytes()
        with patch.object(Path, "write_text", side_effect=OSError("Disk is full")):
            with self.assertRaises(OSError):
                self.g.action("new_game", {})
        self.assertEqual(self.g.state, original)
        self.assertEqual(self.save.read_bytes(), original_file)


if __name__ == "__main__":
    unittest.main()
