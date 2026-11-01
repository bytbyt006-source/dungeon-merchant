"""Final debt unlock, nemesis battle, and wanted-criminal spoils."""
import copy,random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
from final_boss import BOSS_ID
from shop_fixture import stock_shop
class FinaleWantedTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  self.g.state['creation']={'completed':True,'points':0,'allocated':{}}

 def unlock(self):
  self.g.state['loan'].update(balance=0,principal_paid=20000);self.g.check_ending()
 def wanted(self):
  stock_shop(self.g);self.g.finish_market();self.g.arrive();c=self.g.customer();c['wanted']=True
  return c
 def test_all_six_outlaw_portraits_are_wanted_and_other_portraits_are_not(self):
  outlaws=[p for p in self.g.portraits if '_outlaw' in p['weapon']]
  self.assertEqual(len(outlaws),6)
  for portrait in self.g.portraits:
   c=self.g._new_customer([portrait]);self.assertEqual(c['wanted'],'_outlaw' in portrait['weapon'])
 def test_paid_loan_unlocks_boss_and_preparation_without_ending(self):
  with self.assertRaises(ValueError):self.g.action('begin_final_battle',{})
  self.unlock();self.assertIsNone(self.g.public()['ending'])
  self.assertEqual(self.g.public()['final_boss']['status'],'waiting')
  self.g.action('acknowledge_boss',{});self.assertTrue(self.g.state['final_boss']['introduced'])
  self.g.check_ending();self.assertEqual(self.g.state['final_boss']['attempts'],0)
 def test_boss_stats_are_fixed_and_second_phase_is_stronger(self):
  self.unlock();self.g.action('begin_final_battle',{});c=self.g.customer();first=self.g.customer_stats(c)
  self.g.state['player']['strength']=100
  self.assertEqual(self.g.customer_stats(c),first)
  c['health']=210;second=self.g.customer_stats(c)
  self.assertGreater(second['attack'],first['attack']);self.assertLess(second['interval'],first['interval'])
  self.assertFalse(self.g.can_attempt_theft(c));self.assertFalse(self.g.can_buy_belongings(c))
  self.assertNotIn(BOSS_ID,[p['id'] for p in self.g.commission_board()['roster']])
 def test_boss_victory_is_the_only_new_ending_and_survives_reload(self):
  self.unlock();self.g.action('begin_final_battle',{});c=self.g.customer();c['health']=1
  fight=self.g.state['combat'];fight.update(player_next=101,enemy_next=103,last_tick=100)
  with patch('combat.time.time',return_value=101),patch.object(self.g.rng,'random',return_value=.999):self.g.action('combat_tick',{})
  self.assertEqual(fight['status'],'victory');self.assertTrue(self.g.public()['ending']['nemesis_defeated'])
  loaded=Game(ROOT/'assets',self.path);self.assertTrue(loaded.public()['ending']['nemesis_defeated'])
  with self.assertRaises(ValueError):loaded.action('begin_final_battle',{})
 def test_boss_defeat_rest_and_retry_preserve_paid_loan(self):
  self.unlock();self.g.action('begin_final_battle',{});self.g.state['player_health']=1
  fight=self.g.state['combat'];fight.update(player_next=103,enemy_next=101,last_tick=100)
  with patch('combat.time.time',return_value=101),patch.object(self.g.rng,'random',return_value=.999):self.g.action('combat_tick',{})
  self.assertEqual(fight['status'],'defeat');self.assertIsNone(self.g.public()['ending'])
  self.g.action('rest',{});self.assertEqual(self.g.state['daily']['served'],0)
  self.assertEqual(self.g.state['loan']['balance'],0);self.g.action('begin_final_battle',{})
  self.assertEqual(self.g.customer()['health'],420);self.assertEqual(self.g.state['final_boss']['attempts'],2)
 def test_final_duel_escape_returns_to_preparation(self):
  self.unlock();self.g.action('begin_final_battle',{})
  with patch.object(self.g.rng,'randint',return_value=20):self.g.action('flee_combat',{})
  self.assertIsNone(self.g.state['current_id']);self.assertEqual(self.g.state['final_boss']['status'],'waiting')
  self.assertIsNone(self.g.public()['ending']);self.g.action('begin_final_battle',{})
 def test_boss_execution_occurs_on_fourth_strike(self):
  self.unlock();self.g.action('begin_final_battle',{});fight=self.g.state['combat'];self.g.state['player_health']=1000
  fight.update(player_next=1000,enemy_next=101,last_tick=100)
  for i in range(4):
   now=fight['enemy_next']
   with patch('combat.time.time',return_value=now),patch.object(self.g.rng,'random',return_value=.999):self.g.combat_tick()
  events=fight['events'];self.assertFalse(events[2]['charged']);self.assertTrue(events[3]['charged'])
  self.assertGreater(events[3]['damage'],events[2]['damage']);self.assertEqual(events[3]['weapon'],'greatsword')
 def test_wanted_victory_transfers_all_gear_cash_and_bounty_once(self):
  c=self.wanted();ids={g['id'] for g in c['belongings']};cash=c['budget'];gold=self.g.state['gold']
  self.g.action('attack_wanted',{});c['health']=1;fight=self.g.state['combat'];fight.update(player_next=101,enemy_next=103,last_tick=100)
  with patch('combat.time.time',return_value=101),patch.object(self.g.rng,'random',return_value=.999):self.g.action('combat_tick',{})
  self.assertEqual(self.g.state['gold'],gold)
  self.assertEqual(self.g.state['equipment_bag'],[])
  with self.assertRaises(ValueError):self.g.action('leave',{})
  self.g.save();self.g=Game(ROOT/'assets',self.path)
  self.g.action('collect_combat_rewards',{})
  self.assertEqual(self.g.state['gold'],gold+cash+100)
  with self.assertRaises(ValueError):self.g.action('collect_combat_rewards',{})
  self.assertEqual({g['id'] for g in self.g.state['equipment_bag']},ids)
  self.assertEqual(c['belongings'],[]);self.assertEqual(c['budget'],0)
  before=copy.deepcopy(self.g.state);self.g.combat_tick();self.assertEqual(self.g.state,before)
  with self.assertRaises(ValueError):self.g.action('attack_wanted',{})
  self.assertEqual(len(self.g.combat_public()['rewards']['equipment']),len(ids))
 def test_ordinary_customer_cannot_be_attacked_for_bounty(self):
  c=self.wanted();c['wanted']=False;before=copy.deepcopy(self.g.state)
  with self.assertRaises(ValueError):self.g.action('attack_wanted',{})
  self.assertEqual(self.g.state,before)
 def test_pending_pouch_blocks_wanted_attack(self):
  c=self.wanted();self.g.state['deal']={'status':'payment','agreed':1,'item_id':c['wants']}
  with self.assertRaises(ValueError):self.g.action('attack_wanted',{})
 def test_old_wanted_flag_is_inferred_from_portrait_on_reload(self):
  outlaw=next(p for p in self.g.portraits if '_outlaw' in p['weapon'])
  c=self.g._new_customer([outlaw]);c.pop('wanted');self.g.save()
  loaded=Game(ROOT/'assets',self.path);self.assertTrue(loaded.state['customers'][c['id']]['wanted'])
 def test_legacy_debt_only_ending_becomes_final_boss_entrance(self):
  self.unlock();self.g.state['ending']={'day':1,'gold':1000,'repaid':20000,'visits':0};self.g.save()
  loaded=Game(ROOT/'assets',self.path);self.assertIsNone(loaded.public()['ending']);self.assertEqual(loaded.public()['final_boss']['status'],'waiting')

 def test_boss_has_a_separate_png_and_never_replaces_random_portraits(self):
  path=ROOT/'assets/characters/final_boss_malrec.png'
  self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual(len(self.g.portraits),42)
