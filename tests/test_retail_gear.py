"""Unique enchanted retail goods and authoritative sale-price limits."""
import copy
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from game import Game
from shop_fixture import stock_shop

class RetailGearTests(unittest.TestCase):
 def setUp(self):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
  self.save=Path(folder.name)/"save.json"
  self.g=Game(ROOT/"assets",self.save,random.Random(7));stock_shop(self.g)
  self.gear=self.g.make_gear("book","magic");self.gear["paid_cost"]=36
  self.g.state["equipment_bag"].append(self.gear)
  self.sku="gear_"+self.gear["id"]

 def stock(self,mode="fixed"):
  self.g.action("stock_gear",{"gear_id":self.gear["id"]})
  for slot in range(4):self.g.action("return_stock",{"slot":slot})
  item=self.g.item(self.sku)
  price=self.g.sale_cap(item,mode)
  self.g.action("place_stock",{"slot":0,"item_id":self.sku,"quantity":1,"mode":mode,"price":price})
  return price

 def test_staging_preserves_quality_affixes_and_separates_white_goods(self):
  original=copy.deepcopy(self.gear)
  ordinary=self.g.state["warehouse"]["book"]
  self.g.action("stock_gear",{"gear_id":self.gear["id"]})
  item=self.g.item(self.sku)
  self.assertEqual(item["base_id"],"book")
  self.assertEqual(item["gear"],original)
  self.assertEqual(self.g.state["warehouse"][self.sku],1)
  self.assertEqual(self.g.state["warehouse"]["book"],ordinary)
  self.assertEqual(self.g.state["equipment_bag"],[])
  public=next(x for x in self.g.public()["stock"] if x["id"]==self.sku)
  self.assertEqual(public["quality"],"magic")
  self.assertEqual(public["affixes"],original["affixes"])
  self.assertTrue((ROOT/public["wear"]["src"]).is_file())
  with self.assertRaises(ValueError):self.g.action("stock_gear",{"gear_id":self.gear["id"]})

 def test_suitable_customer_buys_unique_fixed_item_and_shelf_empties(self):
  price=self.stock();before=self.g.state["gold"]
  self.g.action("finish_market",{});self.g.action("arrive",{})
  c=self.g.customer()
  self.assertEqual(c["wants"],self.sku)
  self.assertEqual(c["weapon_type"],"prayer_book")
  self.g.action("begin",{"item_id":self.sku})
  self.g.action("prepare_payment",{});self.g.action("collect_payment",{})
  self.assertEqual(self.g.state["gold"],before+price)
  self.assertIsNone(self.g.state["shelves"][0])
  self.assertEqual(c["purchased_gear"][0]["id"],self.gear["id"])
  self.assertEqual(c["purchased_gear"][0]["affixes"],self.gear["affixes"])
  loaded=Game(ROOT/"assets",self.save)
  self.assertEqual(loaded.state["warehouse"][self.sku],0)
  with self.assertRaises(ValueError):loaded.action("collect_payment",{})

 def test_bargain_can_sell_at_label_cap_and_absolute_offer_bound_is_enforced(self):
  cap=self.stock("bargain")
  self.g.action("finish_market",{});self.g.action("arrive",{});self.g.action("begin",{"item_id":self.sku})
  before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action("quote",{"price":self.g.quote_cap(self.g.item(self.sku))+1})
  self.assertEqual(self.g.state,before)
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("quote",{"price":cap})
  self.assertEqual(self.g.state["deal"]["status"],"agreed")

 def test_equipping_a_registered_unique_item_does_not_consume_white_stock(self):
  self.stock();self.g.action("return_stock",{"slot":0})
  self.g.state["player"].update(strength=3,wisdom=4)
  ordinary=self.g.state["warehouse"]["book"]
  self.g.action("equip_gear",{"item_id":self.sku})
  self.assertEqual(self.g.state["loadout"]["weapon"]["id"],self.gear["id"])
  self.assertEqual(self.g.state["warehouse"]["book"],ordinary)
  self.assertEqual(self.g.state["warehouse"][self.sku],0)
  self.g.action("unequip_gear",{"slot":"weapon"})
  self.g.action("stock_gear",{"gear_id":self.gear["id"]})
  self.assertEqual(self.g.state["warehouse"][self.sku],1)
  self.assertEqual(len([x for x in self.g.state["stock"] if x["id"]==self.sku]),1)

 def test_stolen_gear_keeps_zero_cost_and_uses_appraised_price_bounds(self):
  self.gear["paid_cost"]=0;self.stock()
  public=next(x for x in self.g.public()["stock"] if x["id"]==self.sku)
  self.assertEqual(public["cost"],0)
  self.assertEqual(public["pricing_reference"],36)
  self.assertEqual(public["price_caps"],{"fixed":41,"bargain":54})

 def test_unidentified_staged_gear_can_be_identified_without_wearing_it(self):
  self.gear["identified"]=False
  self.g.action("stock_gear",{"gear_id":self.gear["id"]})
  self.g.state["player"]["wisdom"]=3
  self.g.action("identify_gear",{"gear_id":self.gear["id"]})
  self.assertTrue(self.g.item(self.sku)["gear"]["identified"])

 def test_price_caps_round_down_and_reject_labels_atomically(self):
  item=self.g.item("longsword")
  self.assertEqual(self.g.sale_cap(item,"fixed"),40)
  self.assertEqual(self.g.sale_cap(item,"bargain"),52)
  for mode,price in [("fixed",41),("bargain",53)]:
   before=copy.deepcopy(self.g.state)
   with self.assertRaises(ValueError):self.g.action("place_stock",{"slot":1,"item_id":"longsword","quantity":1,"mode":mode,"price":price})
   self.assertEqual(self.g.state,before)

 def test_price_caps_follow_actual_discounted_purchase_cost(self):
  g=Game(ROOT/"assets",self.save,load_existing=False)
  g.action("allocate_attributes",{"allocation":{"luck":5}})
  g.action("learn_skill",{"skill":"supplier"})
  g.action("merchant_buy",{"item_id":"greatsword","quantity":1})
  item=g.item("greatsword")
  self.assertEqual(g.sale_reference(item),57)
  self.assertEqual(g.sale_cap(item,"fixed"),65)
  self.assertEqual(g.sale_cap(item,"bargain"),85)

 def test_higher_markup_is_harder_and_preview_matches_actual_roll(self):
  self.g.finish_market();self.g.arrive();c=self.g.customer()
  c.update(budget=1000,mood=2,personality="patient",buying_style="practical",urgency="prepared",observed=[])
  self.g.item("longsword")["cost"]=100
  self.g.state["deal"]={"item_id":"longsword","status":"negotiating","offer":80,"failures":0,"last_quote":None,"round":0}
  prices=[100,115,150];previews=[self.g.negotiation_preview(price) for price in prices]
  self.assertTrue(previews[0]["difficulty"]<previews[1]["difficulty"]<previews[2]["difficulty"])
  self.assertTrue(previews[0]["success_percent"]>previews[1]["success_percent"]>previews[2]["success_percent"])
  with patch.object(self.g.rng,"randint",return_value=20):self.g.quote(150)
  self.assertEqual(self.g.state["last_roll"]["difficulty"],previews[-1]["difficulty"])

 def test_old_overpriced_labels_are_capped_without_losing_goods_or_gold(self):
  self.g.item("greatsword").update(mode="fixed",price=9999)
  self.g.state["shelf_settings"]["greatsword"]={"mode":"fixed","price":9999,"quantity":3}
  before=copy.deepcopy(self.g.state);self.g.save()
  loaded=Game(ROOT/"assets",self.save)
  self.assertEqual(loaded.item("greatsword")["price"],69)
  self.assertEqual(loaded.state["gold"],before["gold"])
  self.assertEqual(loaded.state["warehouse"],before["warehouse"])
  self.assertEqual(loaded.item("greatsword")["quantity"],3)

 def test_forgiving_curve_has_90_percent_near_15_percent_markup(self):
  self.g.finish_market();self.g.arrive();c=self.g.customer()
  c.update(budget=1000,mood=2,personality="proud",buying_style="practical",urgency="prepared",observed=[])
  self.g.item("longsword")["cost"]=100
  initial={"item_id":"longsword","status":"negotiating","offer":80,"failures":0,"last_quote":None,"round":0}
  self.g.state["deal"]=copy.deepcopy(initial)
  for price,chance in [(100,100),(115,90),(120,90),(130,80),(140,70),(150,60)]:
   self.assertEqual(self.g.negotiation_preview(price)["success_percent"],chance)
  successes=0
  for raw in range(1,21):
   self.g.state["deal"]=copy.deepcopy(initial);c["mood"]=2
   with patch.object(self.g.rng,"randint",return_value=raw):self.g.quote(115)
   successes+=int(self.g.state["last_roll"]["success"])
  self.assertEqual(successes,18)

 def jackpot_fixture(self):
  self.g.finish_market();self.g.arrive();c=self.g.customer()
  c.update(budget=2000,mood=2,personality="proud",buying_style="practical",urgency="prepared",observed=[])
  c["willingness"]["longsword"]=300
  self.g.item("longsword")["cost"]=100
  self.g.state["deal"]={"item_id":"longsword","status":"negotiating","offer":80,"agreed":None,"failures":0,"last_quote":None,"round":0}
  return copy.deepcopy(self.g.state["deal"])

 def test_higher_quotes_decline_to_zero_without_a_probability_floor(self):
  initial=self.jackpot_fixture()
  for price,chance in [(115,90),(150,60),(175,50),(200,40),(225,30),(250,20),(275,10),(285,5),(288,0),(1000,0)]:
   self.assertEqual(self.g.negotiation_preview(price)["success_percent"],chance)
  for price,expected in [(285,1),(288,0)]:
   wins=0
   for raw in range(1,21):
    self.g.state["deal"]=copy.deepcopy(initial);self.g.customer()["mood"]=2
    with patch.object(self.g.rng,"randint",return_value=raw) as die:self.g.quote(price)
    die.assert_called_once_with(1,20)
    wins+=int(self.g.state["last_roll"]["success"])
    self.assertNotIn("luck_check",self.g.state["last_roll"])
   self.assertEqual(wins,expected)

 def test_high_price_agreement_survives_save_and_pays_the_full_price_once(self):
  self.jackpot_fixture()
  before=self.g.state["gold"]
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("quote",{"price":200})
  self.assertEqual(self.g.state["deal"]["agreed"],200)
  loaded=Game(ROOT/"assets",self.save)
  self.assertEqual(loaded.state["deal"]["agreed"],200)
  loaded.action("prepare_payment",{});loaded.action("collect_payment",{})
  self.assertEqual(loaded.state["gold"],before+200)
  self.assertEqual(loaded.customer()["budget"],1800)
  with self.assertRaises(ValueError):loaded.action("collect_payment",{})

 def test_natural_20_does_not_override_an_impossible_price(self):
  self.jackpot_fixture()
  with patch.object(self.g.rng,"randint",return_value=20) as die:self.g.quote(1000)
  die.assert_called_once_with(1,20)
  self.assertFalse(self.g.state["last_roll"]["success"])
  self.assertEqual(self.g.state["deal"]["status"],"negotiating")

 def test_excessive_failed_asks_do_not_give_free_massive_counteroffers(self):
  self.jackpot_fixture();initial=copy.deepcopy(self.g.state)
  with patch.object(self.g.rng,"randint",return_value=1):self.g.quote(150)
  normal=self.g.state["deal"]["offer"]
  self.g.state=initial
  with patch.object(self.g.rng,"randint",return_value=1):self.g.quote(2000)
  self.assertEqual(self.g.state["deal"]["offer"],normal)

 def test_offer_slider_bound_respects_money_and_unaffordable_asks_have_zero_odds(self):
  self.jackpot_fixture();self.g.customer()["budget"]=600
  limit=self.g.public()["deal"]["quote_cap"]
  self.assertLessEqual(limit,601)
  self.assertEqual(self.g.negotiation_preview(limit)["success_percent"],0)
  self.assertEqual(self.g.negotiation_preview(600)["success_percent"],0)
  self.assertEqual(self.g.negotiation_preview(601)["success_percent"],0)
  with patch.object(self.g.rng,"randint") as roll:self.g.quote(601)
  roll.assert_not_called()
