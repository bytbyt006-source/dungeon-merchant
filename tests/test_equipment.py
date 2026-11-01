"""Equipment ownership, quality, identification, theft and timed combat."""
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

class EquipmentTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.save=Path(self.folder.name)/"save.json"
  self.g=Game(ROOT/"assets",self.save,random.Random(7));stock_shop(self.g)

 def visitor(self):
  self.g.finish_market();self.g.arrive();self.g.inspect_belongings()
  c=self.g.customer()
  c["belongings"]=[self.g.make_gear("greatsword","common"),self.g.make_gear("chainmail","common")]
  for gear in c["belongings"]:gear["identified"]=False
  c["health"]=85
  return c

 def test_quality_has_correct_affix_counts_and_requirements(self):
  for quality,counts,requirement in [("common",{0},0),("magic",{1,2},3),("rare",{3,4},6),("legendary",{4},10)]:
   gear=self.g.make_gear("ring",quality)
   self.assertIn(len(gear["affixes"]),counts)
   self.assertEqual(self.g.gear_public(gear)["requirement"],requirement)
   self.assertTrue((ROOT/self.g.gear_public(gear)["src"]).exists())

 def test_common_equip_consumes_one_item_and_swapping_conserves_ownership(self):
  self.g.state["player"].update(strength=4,dexterity=3)
  before=self.g.state["warehouse"]["greatsword"]
  self.g.action("equip_gear",{"item_id":"greatsword"})
  self.assertEqual(self.g.state["warehouse"]["greatsword"],before-1)
  self.assertEqual(self.g.player_stats()["interval"],3.2)
  self.g.action("equip_gear",{"item_id":"bow"})
  self.assertEqual(self.g.player_stats()["interval"],1.8)
  self.assertEqual(len(self.g.state["equipment_bag"]),1)
  self.g.action("unequip_gear",{"slot":"weapon"})
  self.assertEqual(len(self.g.state["equipment_bag"]),2)
  self.assertIsNone(self.g.state["loadout"]["weapon"])

 def test_two_accessory_slots_are_independent(self):
  self.g.equip_gear(item_id="ring",slot="accessory1")
  self.g.equip_gear(item_id="amulet",slot="accessory2")
  self.assertEqual(self.g.state["loadout"]["accessory1"]["item_id"],"ring")
  self.assertEqual(self.g.state["loadout"]["accessory2"]["item_id"],"amulet")
  before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action("equip_gear",{"item_id":"ring","slot":"weapon"})
  self.assertEqual(self.g.state,before)

 def test_wisdom_gates_identification_and_wearing(self):
  gear=self.g.make_gear("staff","legendary");gear["identified"]=False
  self.g.state["equipment_bag"].append(gear)
  with self.assertRaises(ValueError):self.g.action("identify_gear",{"gear_id":gear["id"]})
  self.assertFalse(self.g.public()["equipment"]["bag"][0]["identified"])
  self.assertEqual(self.g.public()["equipment"]["bag"][0]["affixes"],[])
  self.g.gain_xp(200)
  for _ in range(3):self.g.action("learn_skill",{"skill":"scholar"})
  self.g.action("identify_gear",{"gear_id":gear["id"]})
  self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state["loadout"]["weapon"]["quality"],"legendary")

 def test_equipment_modifiers_change_attributes_and_talent_effects(self):
  gear=self.g.make_gear("ring","magic")
  gear["affixes"]=[{"stat":"eloquence","value":2,"text":"test"},{"name":"Connected","stat":"talent_supplier","value":1,"text":"test"}]
  self.g.state["player"].update(wisdom=10,dexterity=4);self.g.state["equipment_bag"].append(gear)
  self.g.equip_gear(gear_id=gear["id"])
  self.assertEqual(self.g.effective_eloquence(),5)
  self.assertEqual(self.g.merchant_price(100),95)

 def test_merchant_unique_gear_cannot_be_bought_twice(self):
  gear=self.g.state["caravan"]["gear_stock"][0]
  self.g.state["gold"]=10000
  self.g.action("buy_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state["equipment_bag"][0]["id"],gear["id"])
  before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action("buy_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state,before)

 def test_successful_theft_transfers_one_item_and_persists(self):
  c=self.visitor();gear=c["belongings"][0]
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":gear["id"]})
  self.assertNotIn(gear,c["belongings"])
  self.assertEqual(self.g.state["equipment_bag"][0]["id"],gear["id"])
  loaded=Game(ROOT/"assets",self.save)
  with self.assertRaises(ValueError):loaded.action("steal_gear",{"gear_id":gear["id"]})
  self.assertEqual(len(loaded.state["equipment_bag"]),1)

 def test_patient_customer_can_insult_instead_of_attacking(self):
  c=self.visitor();c.update(personality="patient",mood=4)
  with patch.object(self.g.rng,"randint",return_value=1),patch.object(self.g.rng,"randrange",return_value=99):
   self.g.steal_gear(c["belongings"][0]["id"])
  self.assertIsNone(self.g.state["combat"])
  self.assertEqual(c["grudge"],1)
  self.assertEqual(c["reaction"],"Insulted")

 def test_angry_impatient_customer_can_attack(self):
  c=self.visitor();c.update(personality="impatient",mood=0)
  with patch.object(self.g.rng,"randint",return_value=1),patch.object(self.g.rng,"randrange",return_value=0):
   self.g.action("steal_gear",{"gear_id":c["belongings"][0]["id"]})
  self.assertEqual(self.g.state["combat"]["status"],"threatened")
  for action,payload in [("leave",{}),("skip_day",{}),("equip_gear",{"item_id":"bow"})]:
   with self.assertRaises(ValueError):self.g.action(action,payload)

 def test_stronger_player_can_intimidate_the_caught_customer(self):
  self.g.state["player"].update(strength=4,dexterity=3)
  c=self.visitor();c.update(personality="impatient",mood=0)
  self.g.equip_gear(item_id="greatsword");self.g.equip_gear(item_id="plate_armour")
  c["belongings"]=[]
  item=self.g.make_gear("charm","common");c["belongings"].append(item)
  with patch.object(self.g.rng,"randint",return_value=1):self.g.steal_gear(item["id"])
  self.assertEqual(c["reaction"],"Intimidated")
  self.assertIsNone(self.g.state["combat"])

 def test_attacks_resolve_in_order_and_defeated_enemy_cannot_hit(self):
  self.g.state["player"].update(strength=4,dexterity=3)
  c=self.visitor();self.g.equip_gear(item_id="greatsword");c["health"]=1
  with patch("combat.time.time",return_value=100):self.g.start_combat(c)
  fight=self.g.state["combat"];fight.update(player_next=101,enemy_next=102)
  before=self.g.state["player_health"]
  with patch("combat.time.time",return_value=102.5):self.g.combat_tick()
  self.assertEqual(fight["status"],"victory")
  self.assertEqual(self.g.state["player_health"],before)
  self.assertTrue(c["defeated"])

 def test_defeat_without_worn_gear_preserves_gold_and_sleep_restores_health(self):
  c=self.visitor();self.g.state["player_health"]=1
  with patch("combat.time.time",return_value=100):self.g.start_combat(c)
  fight=self.g.state["combat"];fight.update(enemy_next=101,player_next=102)
  gold=self.g.state["gold"]
  with patch("combat.time.time",return_value=101.5):
   self.g.combat_tick();self.g.combat_tick()
  self.assertEqual(fight["status"],"defeat")
  self.assertEqual(self.g.state["gold"],gold)
  self.assertEqual(fight["lost_equipment"],[])
  self.g.action("rest",{})
  self.assertEqual(self.g.state["player_health"],self.g.player_stats()["max_hp"])

 def test_higher_defense_reduces_damage(self):
  self.g.state["player"].update(strength=4,dexterity=3)
  c=self.visitor();self.g.equip_gear(item_id="plate_armour")
  with patch("combat.time.time",return_value=100):self.g.start_combat(c)
  fight=self.g.state["combat"];fight.update(enemy_next=101,player_next=102)
  expected=max(1,round(self.g.customer_stats(c)["attack"]-self.g.player_stats()["defense"]*.5))
  with patch("combat.time.time",return_value=101.5):self.g.combat_tick()
  self.assertEqual(self.g.state["player_health"],100-expected)

 def test_carried_and_player_expedition_affixes_affect_commission(self):
  c=self.visitor();self.g.leave()
  before=self.g.commission_preview(c["id"],"mine")["bonus"]
  c["belongings"][0]["affixes"]=[{"stat":"expedition","value":2,"text":"test"}]
  self.assertEqual(self.g.commission_preview(c["id"],"mine")["bonus"],before+2)

 def test_active_combat_reload_resumes_without_offline_damage(self):
  c=self.visitor();self.g.start_combat(c);self.g.save()
  loaded=Game(ROOT/"assets",self.save)
  with patch("combat.time.time",return_value=loaded.state["combat"]["last_tick"]+.1):loaded.combat_tick()
  self.assertEqual(loaded.state["player_health"],100)
  self.assertEqual(loaded.state["combat"]["status"],"active")

 def test_retreat_check_ends_fight_without_awarding_stolen_items(self):
  c=self.visitor();self.g.start_combat(c)
  before=len(self.g.state["equipment_bag"])
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("flee_combat",{})
  self.assertEqual(self.g.state["combat"]["status"],"escaped")
  self.assertEqual(len(self.g.state["equipment_bag"]),before)
  self.g.action("leave",{})
  self.assertIsNone(self.g.state["current_id"])

 def test_accessories_can_be_retail_goods_but_not_expedition_weapons(self):
  for slot in range(4):self.g.return_stock(slot)
  self.g.place_stock(0,"ring",2,"fixed",25)
  self.g.finish_market();self.g.arrive()
  self.assertEqual(self.g.customer()["wants"],"ring")
  with self.assertRaises(ValueError):self.g._loan_slot("ring")

 def test_temporary_talent_bonus_does_not_prevent_learning_base_ranks(self):
  self.g.state["loadout"]["accessory1"]=self.g.make_gear("ring","magic")
  self.g.state["loadout"]["accessory1"]["affixes"]=[{"name":"Connected","stat":"talent_supplier","value":1,"text":"test"}]
  self.g.gain_xp(200)
  for _ in range(3):self.g.action("learn_skill",{"skill":"supplier"})
  self.assertEqual(self.g.state["skills"]["ranks"]["supplier"],3)
  self.assertEqual(self.g.skill_rank("supplier"),3)

 def test_quality_increases_numbers_without_adding_attribute_types(self):
  from equipment import BASE
  families=set()
  for item_id in BASE:
   previous=None;keys=None
   for quality in ["common","magic","rare","legendary"]:
    req=self.g.wear_requirements(self.g.make_gear(item_id,quality))
    families.add(len(req))
    if keys is None:keys=set(req)
    self.assertEqual(set(req),keys)
    if previous:self.assertTrue(all(req[k]>previous[k] for k in keys))
    previous=req
  self.assertEqual(families,{1,2,3})
  self.assertEqual(self.g.wear_requirements(self.g.make_gear("staff","legendary")),{"wisdom":10})
  self.assertEqual(self.g.wear_requirements(self.g.make_gear("longsword","magic")),{"strength":4,"dexterity":4})

 def test_strength_training_increases_attack_and_health(self):
  before=self.g.player_stats()
  self.g.action("learn_skill",{"skill":"strength_training"})
  after=self.g.player_stats()
  self.assertEqual(after["strength"],before["strength"]+3)
  self.assertEqual(after["attack"],before["attack"]+6)
  self.assertEqual(after["max_hp"],before["max_hp"]+30)
  self.assertEqual(after["hp"],before["hp"]+30)

 def test_attribute_requirements_cannot_be_met_by_items_own_bonus(self):
  gear=self.g.make_gear("greatsword","magic")
  gear["affixes"]=[{"name":"Brawny","stat":"strength","value":20,"text":"Strength +20"}]
  self.g.state["equipment_bag"].append(gear)
  before=copy.deepcopy(self.g.state)
  with self.assertRaisesRegex(ValueError,"Strength 5"):
   self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state,before)
  self.g.action("learn_skill",{"skill":"strength_training"})
  self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.player_stats()["strength"],25)

 def test_removing_strength_support_cannot_break_armour_requirements(self):
  self.g.state["player"]["wisdom"]=4
  gear=self.g.make_gear("amulet","magic")
  gear["affixes"]=[{"name":"Brawny","stat":"strength","value":2,"text":"Strength +2"}]
  self.g.state["equipment_bag"].append(gear)
  self.g.action("equip_gear",{"gear_id":gear["id"],"slot":"accessory1"})
  self.g.action("equip_gear",{"item_id":"plate_armour"})
  before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action("unequip_gear",{"slot":"accessory1"})
  self.assertEqual(self.g.state,before)

 def test_legacy_worn_items_that_no_longer_qualify_are_preserved(self):
  gear=self.g.make_gear("plate_armour","common")
  self.g.state["loadout"]["armour"]=gear
  self.g.state.pop("wear_requirements_version")
  self.g.save()
  loaded=Game(ROOT/"assets",self.save)
  self.assertIsNone(loaded.state["loadout"]["armour"])
  self.assertEqual([g["id"] for g in loaded.state["equipment_bag"]],[gear["id"]])
  loaded.save();again=Game(ROOT/"assets",self.save)
  self.assertEqual(len(again.state["equipment_bag"]),1)

 def test_physical_gear_identification_only_requires_wisdom(self):
  c=self.visitor();gear=self.g.make_gear("hammer","magic");gear["identified"]=False
  c["belongings"]=[gear]
  self.g.state["player"].update(wisdom=3,strength=2)
  self.g.action("identify_gear",{"gear_id":gear["id"]})
  self.assertTrue(c["belongings"][0]["identified"])
  visible=self.g.public()["customer"]["belongings"][0]
  self.assertEqual(visible["requirements"],{"strength":5})
  self.assertFalse(visible["equip_options"]["weapon"])

 def test_unidentified_stolen_gear_can_be_worn_when_attributes_are_sufficient(self):
  c=self.visitor()
  gear=self.g.make_gear("hammer","magic");gear["identified"]=False
  gear["affixes"]=[{"name":"Mighty","stat":"attack","value":4,"text":"Attack +4"}]
  c["belongings"]=[gear]
  self.g.state["player"]["strength"]=5
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":gear["id"]})
  self.assertTrue(self.g.public()["equipment"]["bag"][0]["equip_options"]["weapon"])
  with self.assertRaises(ValueError):self.g.action("identify_gear",{"gear_id":gear["id"]})
  self.g.action("equip_gear",{"gear_id":gear["id"]})
  worn=self.g.public()["equipment"]["loadout"]["weapon"]
  self.assertFalse(worn["identified"])
  self.assertEqual(worn["affixes"],[])
  self.assertEqual(self.g.player_stats()["attack"],23+10+4)
  self.g.state["player"]["wisdom"]=3
  self.g.action("identify_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.public()["equipment"]["loadout"]["weapon"]["affixes"],gear["affixes"])

 def test_unidentified_owned_gear_still_requires_wearing_attributes(self):
  gear=self.g.make_gear("hammer","magic");gear["identified"]=False
  self.g.state["equipment_bag"].append(gear)
  before=copy.deepcopy(self.g.state)
  with self.assertRaisesRegex(ValueError,"Strength 5"):
   self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state,before)

 def test_common_gear_needs_no_identification_and_legacy_flags_are_upgraded(self):
  gear=self.g.make_gear("longsword","common");gear["identified"]=False
  self.g.state["equipment_bag"].append(gear)
  self.assertTrue(self.g.public()["equipment"]["bag"][0]["identified"])
  self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.g.save();loaded=Game(ROOT/"assets",self.save)
  self.assertTrue(loaded.state["loadout"]["weapon"]["identified"])
  self.assertEqual(loaded.state["loadout"]["weapon"]["quality"],"common")

 def test_bought_equipment_only_checks_wearing_attributes(self):
  gear=self.g.make_gear("hammer","magic");gear.update(identified=False,price=84)
  self.g.state["caravan"]["gear_stock"]=[gear]
  self.g.state["player"]["strength"]=5
  self.g.action("buy_gear",{"gear_id":gear["id"]})
  self.g.action("equip_gear",{"gear_id":gear["id"]})
  self.assertEqual(self.g.state["loadout"]["weapon"]["id"],gear["id"])

 def test_successful_theft_allows_another_attempt_with_higher_difficulty(self):
  c=self.visitor();first,second=c["belongings"]
  start_dc=self.g.theft_difficulty(c,first)
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":first["id"]})
  self.assertTrue(self.g.public()["customer"]["can_steal"])
  self.assertEqual(self.g.theft_difficulty(c,second),start_dc+2)
  expected=self.g.theft_chance(c,second)
  self.assertEqual(self.g.public()["customer"]["belongings"][0]["steal_chance"],expected)
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":second["id"]})
  self.assertEqual(len(self.g.state["equipment_bag"]),2)
  self.assertEqual(c["theft_attempts"],2)

 def test_caught_theft_can_be_retried_but_trade_remains_blocked(self):
  c=self.visitor();c.update(personality="patient",mood=4)
  first,second=c["belongings"]
  with patch.object(self.g.rng,"randint",return_value=1),patch.object(self.g.rng,"randrange",return_value=99):
   self.g.action("steal_gear",{"gear_id":first["id"]})
  self.assertTrue(self.g.public()["customer"]["can_steal"])
  self.assertTrue(self.g.public()["customer"]["trade_blocked"])
  self.assertGreater(self.g.theft_difficulty(c,second),10)
  loaded=Game(ROOT/"assets",self.save)
  self.assertTrue(loaded.public()["customer"]["can_steal"])
  with patch.object(loaded.rng,"randint",return_value=20):loaded.action("steal_gear",{"gear_id":second["id"]})
  self.assertEqual(len(loaded.state["equipment_bag"]),1)
  self.assertEqual(loaded.customer()["theft_attempts"],2)
  self.assertTrue(loaded.public()["customer"]["trade_blocked"])

 def test_repeat_theft_survives_reload_and_attempt_pressure_resets_next_visit(self):
  c=self.visitor();first,second=c["belongings"]
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":first["id"]})
  loaded=Game(ROOT/"assets",self.save)
  self.assertEqual(loaded.theft_attempt_count(loaded.customer()),1)
  self.assertTrue(loaded.public()["customer"]["can_steal"])
  with patch.object(loaded.rng,"randint",return_value=20):loaded.action("steal_gear",{"gear_id":second["id"]})
  loaded.customer()["visits"]+=1
  self.assertEqual(loaded.theft_attempt_count(loaded.customer()),0)

 def test_legacy_successful_theft_no_longer_locks_remaining_items(self):
  c=self.visitor();c["theft_visit"]=c["visits"]
  self.assertTrue(self.g.public()["customer"]["can_steal"])
  self.assertEqual(self.g.theft_attempt_count(c),1)
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":c["belongings"][0]["id"]})
  self.assertEqual(c["theft_attempts"],2)

 def test_ongoing_fight_blocks_theft_but_escape_allows_it_again(self):
  c=self.visitor();self.g.start_combat(c)
  self.assertFalse(self.g.public()["customer"]["can_steal"])
  with self.assertRaises(ValueError):self.g.action("steal_gear",{"gear_id":c["belongings"][0]["id"]})
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("flee_combat",{})
  self.assertTrue(self.g.public()["customer"]["can_steal"])
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("steal_gear",{"gear_id":c["belongings"][0]["id"]})
  self.assertEqual(len(self.g.state["equipment_bag"]),1)

 def test_avoidance_half_percent_per_point_and_bounds(self):
  for stat,chance in [(0,0),(1,.5),(17,8.5),(200,100),(250,100),(-2,0)]:
   self.assertEqual(self.g.avoidance_chance(stat),chance)

 def strike_fixture(self,side):
  c=self.visitor()
  with patch("combat.time.time",return_value=100):self.g.start_combat(c)
  fight=self.g.state["combat"];fight.update(player_next=101 if side=="player" else 103,enemy_next=101 if side=="enemy" else 103)
  return c,fight

 def test_dodge_precedes_block_and_does_not_remove_health(self):
  c,fight=self.strike_fixture("enemy");health=self.g.state["player_health"]
  with patch("combat.time.time",return_value=101),patch.object(self.g.rng,"random",return_value=0) as roll:
   self.g.combat_tick()
  self.assertEqual(roll.call_count,1)
  self.assertEqual(self.g.state["player_health"],health)
  self.assertEqual(fight["events"][-1]["outcome"],"dodge")
  self.assertEqual(fight["events"][-1]["damage"],0)

 def test_block_after_failed_dodge_and_no_duplicate_poll_event(self):
  c,fight=self.strike_fixture("player");health=c["health"]
  with patch("combat.time.time",return_value=101),patch.object(self.g.rng,"random",side_effect=[.999,0]):
   self.g.combat_tick();self.g.combat_tick()
  self.assertEqual(c["health"],health)
  self.assertEqual(fight["event_seq"],1)
  self.assertEqual(fight["events"][0]["outcome"],"block")
  self.assertEqual(len(fight["events"]),1)

 def test_hit_event_matches_damage_weapon_and_exact_probability_boundary(self):
  c,fight=self.strike_fixture("enemy");health=self.g.state["player_health"]
  stats=self.g.player_stats()
  with patch("combat.time.time",return_value=101),patch.object(self.g.rng,"random",side_effect=[stats["dexterity"]*.005,stats["defense"]*.005]):self.g.combat_tick()
  event=fight["events"][0]
  self.assertEqual(event["outcome"],"hit")
  self.assertEqual(event["weapon"],"greatsword")
  self.assertEqual(health-self.g.state["player_health"],event["damage"])

 def test_confrontation_waits_without_damage_even_after_a_long_pause(self):
  c=self.visitor();self.g.confront_customer(c);before=(c["health"],self.g.state["player_health"])
  with patch("combat.time.time",return_value=9999999999):self.g.combat_tick()
  self.assertEqual((c["health"],self.g.state["player_health"]),before)
  self.assertEqual(self.g.state["combat"]["events"],[])
  for action in ["leave","skip_day","steal_gear","equip_gear"]:
   with self.assertRaises(ValueError):self.g.action(action,{})

 def test_mercy_personality_and_mood_change_chance(self):
  c=self.visitor();c["mood"]=2
  values=[]
  for personality in ["patient","proud","impatient"]:
   c["personality"]=personality;self.g.confront_customer(c)
   values.append(self.g.public()["combat"]["mercy"]["chance"])
  self.assertGreater(values[0],values[1]);self.assertGreater(values[1],values[2])
  base=self.g.mercy_difficulty(c);c["mood"]=0
  self.assertEqual(self.g.mercy_difficulty(c),base+2)

 def test_successful_mercy_ends_threat_without_damage_and_cannot_reroll(self):
  c=self.visitor();self.g.confront_customer(c)
  with patch.object(self.g.rng,"randint",return_value=20):self.g.action("beg_mercy",{})
  self.assertEqual(self.g.state["combat"]["status"],"spared")
  self.assertTrue(self.g.state["last_roll"]["success"])
  self.assertEqual(self.g.state["player_health"],100)
  with self.assertRaises(ValueError):self.g.action("beg_mercy",{})
  with self.assertRaises(ValueError):self.g.action("fight",{})
  self.g.action("leave",{})

 def test_failed_mercy_waits_for_roll_display_before_starting_attacks(self):
  c=self.visitor();c["personality"]="impatient";self.g.confront_customer(c)
  with patch.object(self.g.rng,"randint",return_value=1):self.g.action("beg_mercy",{})
  self.assertEqual(self.g.state["combat"]["status"],"ready")
  with patch("combat.time.time",return_value=9999999999):self.g.combat_tick()
  self.assertEqual(self.g.state["player_health"],100)
  with self.assertRaises(ValueError):self.g.action("beg_mercy",{})
  with patch("combat.time.time",return_value=1000):self.g.action("fight",{})
  fight=self.g.state["combat"]
  self.assertEqual(fight["status"],"active")
  self.assertEqual(fight["enemy_next"],1000+fight["enemy_interval"])
  with self.assertRaises(ValueError):self.g.action("fight",{})

 def test_pending_confrontation_and_failed_plea_survive_reload(self):
  c=self.visitor();c["personality"]="impatient";self.g.confront_customer(c);self.g.save()
  loaded=Game(ROOT/"assets",self.save)
  self.assertEqual(loaded.state["combat"]["status"],"threatened")
  with patch.object(loaded.rng,"randint",return_value=1):loaded.action("beg_mercy",{})
  again=Game(ROOT/"assets",self.save)
  self.assertEqual(again.state["combat"]["status"],"ready")
  self.assertEqual(again.state["player_health"],100)

 def test_defeat_takes_one_or_two_worn_items_exactly_once(self):
  for count in [1,2]:
   with self.subTest(count=count):
    self.g=Game(ROOT/"assets",self.save,random.Random(7),load_existing=False);stock_shop(self.g)
    c=self.visitor();self.g.state["loadout"]={slot:None for slot in ["weapon","armour","accessory1","accessory2"]}
    for slot,item in [("weapon","longsword"),("armour","leather_armour"),("accessory1","ring")]:self.g.state["loadout"][slot]=self.g.make_gear(item,"common")
    original={g["id"] for g in self.g.state["loadout"].values() if g}
    bag=self.g.make_gear("staff","magic");self.g.state["equipment_bag"]=[bag]
    self.g.state["player_health"]=1;gold=self.g.state["gold"]
    with patch("combat.time.time",return_value=100):self.g.start_combat(c)
    fight=self.g.state["combat"];fight.update(enemy_next=101,player_next=102)
    with patch("combat.time.time",return_value=101.5),patch.object(self.g.rng,"random",return_value=.999),patch.object(self.g.rng,"randint",return_value=count):
     self.g.combat_tick();self.g.combat_tick()
    lost={g["id"] for g in fight["lost_equipment"]}
    remaining={g["id"] for g in self.g.state["loadout"].values() if g}
    self.assertEqual(len(lost),count);self.assertEqual(lost|remaining,original);self.assertFalse(lost&remaining)
    self.assertEqual({g["id"] for g in c["purchased_gear"]},lost)
    self.assertEqual(self.g.state["equipment_bag"],[bag]);self.assertEqual(self.g.state["gold"],gold)
    self.assertEqual(len(self.g.public()["combat"]["lost_equipment"]),count)
    self.g.save();loaded=Game(ROOT/"assets",self.save)
    self.assertEqual({g["id"] for g in loaded.public()["combat"]["lost_equipment"]},lost)

 def test_defeat_with_only_one_equipped_item_never_takes_two(self):
  c=self.visitor();g=self.g.make_gear("longsword","common");self.g.state["loadout"]["weapon"]=g;self.g.state["player_health"]=1
  with patch("combat.time.time",return_value=100):self.g.start_combat(c)
  self.g.state["combat"].update(enemy_next=101,player_next=102)
  with patch("combat.time.time",return_value=101.5),patch.object(self.g.rng,"random",return_value=.999),patch.object(self.g.rng,"randint",return_value=2):self.g.combat_tick()
  self.assertEqual(len(self.g.state["combat"]["lost_equipment"]),1)
  self.assertIsNone(self.g.state["loadout"]["weapon"])

 def test_zero_health_only_allows_rest_and_advances_exactly_one_day(self):
  c=self.visitor();self.g.state["player_health"]=0
  for action in ["leave","skip_day","next_day","inspect","learn_skill","equip_gear","combat_tick"]:
   with self.assertRaisesRegex(ValueError,"rest"):self.g.action(action,{})
  day=self.g.state["day"];gold=self.g.state["gold"]
  self.g.action("rest",{})
  self.assertEqual(self.g.state["day"],day+1)
  self.assertEqual(self.g.state["player_health"],self.g.player_stats()["max_hp"])
  self.assertIsNone(self.g.state["current_id"]);self.assertIsNone(self.g.state["combat"])
  self.assertIsNone(self.g.state["day_summary"]);self.assertFalse(self.g.state["daily"]["closed"])
  self.assertEqual(self.g.state["gold"],gold)
  with self.assertRaises(ValueError):self.g.action("rest",{})
  self.assertEqual(self.g.state["day"],day+1)

 def test_forced_rest_still_settles_rent_and_debt_at_month_end(self):
  self.visitor();self.g.state.update(day=28,gold=5000,player_health=0)
  self.g.action("rest",{})
  self.assertEqual(self.g.state["day"],29)
  self.assertEqual(self.g.state["gold"],3800)
  self.assertEqual(self.g.state["loan"]["balance"],19000)
  self.assertEqual(len(self.g.state["day_history"]),1)
  self.assertTrue(self.g.state["caravan"]["open"])

 def test_rest_from_already_closed_day_does_not_charge_twice(self):
  self.g.finish_market();self.g.state.update(day=7,gold=500)
  self.g.skip_day();self.g.state["player_health"]=0
  self.g.action("rest",{})
  self.assertEqual(self.g.state["day"],8)
  self.assertEqual(self.g.state["gold"],300)
  self.assertEqual(len(self.g.state["day_history"]),1)
