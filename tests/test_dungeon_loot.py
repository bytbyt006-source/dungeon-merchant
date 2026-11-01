"""Exclusive expedition rewards retain art, properties and ownership."""
import copy,random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
from dungeon_loot import DUNGEON_GEAR,make_dungeon_gear
from shop_fixture import stock_shop
class DungeonLootTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
  stock_shop(self.g);self.g.finish_market();self.g.arrive();self.cid=self.g.state['current_id'];self.g.leave()

 def test_each_region_only_drops_its_own_unique_items(self):
  for region in self.g.commission_board()['regions']:
   self.assertEqual(len(region['unique_rewards']),2)
   with patch.object(self.g.rng,'randrange',return_value=1):rewards=self.g._roll_commission_loot(region,40)
   self.assertEqual(rewards['equipment_loot'],[]);self.assertEqual(rewards['relic_quantity'],0)
   for gear in rewards['unique_loot']:
    self.assertEqual(DUNGEON_GEAR[gear['signature_id']]['region'],region['id'])
    self.assertEqual(len(gear['affixes']),3);self.assertEqual(gear['quality'],'rare')
   self.assertEqual(len({g['id'] for g in rewards['unique_loot']}),40)

 def test_collect_special_reward_once_and_retain_it_after_reload(self):
  self.g.dispatch_commission(self.cid,'mine');mission=self.g.state['commissions'][-1]
  self.g.state['day']=mission['due_day']
  with patch.object(self.g.rng,'randint',return_value=20),patch.object(self.g.rng,'randrange',return_value=1):self.g._resolve_commissions()
  reward=mission['unique_loot'][0]
  row=self.g.commission_board()['missions'][0]['collectible_items'][0]
  self.assertEqual(row['src'],reward['signature_src']);self.assertEqual(row['name'],reward['signature_name'])
  self.g.action('claim_commission',{'mission_id':mission['id']})
  self.assertEqual(self.g.state['equipment_bag'][0]['id'],reward['id'])
  with self.assertRaises(ValueError):self.g.action('claim_commission',{'mission_id':mission['id']})
  loaded=Game(ROOT/'assets',self.path);self.assertEqual(loaded.state['equipment_bag'][0],reward)

 def test_unique_reward_fortune_duplication_creates_distinct_equipment(self):
  self.g.state['skills']['ranks']['fortune']=3;self.g.dispatch_commission(self.cid,'mine')
  mission=self.g.state['commissions'][-1];self.g.state['day']=mission['due_day']
  with patch.object(self.g.rng,'randint',return_value=20),patch.object(self.g.rng,'randrange',return_value=1):self.g._resolve_commissions()
  self.assertEqual(len(mission['unique_loot']),2)
  self.assertNotEqual(mission['unique_loot'][0]['id'],mission['unique_loot'][1]['id'])
  self.g.claim_commission(mission['id']);self.assertEqual(len(self.g.state['equipment_bag']),2)

 def test_failure_never_grants_unique_rewards(self):
  self.g.dispatch_commission(self.cid,'mine');mission=self.g.state['commissions'][-1]
  mission['difficulty']=100;self.g.state['day']=mission['due_day'];self.g._resolve_commissions()
  self.assertFalse(mission['success']);self.g.claim_commission(mission['id'])
  self.assertEqual(self.g.state['equipment_bag'],[])

 def test_all_six_pieces_can_be_worn_and_stocked_with_identity_intact(self):
  for key in DUNGEON_GEAR:
   with self.subTest(key=key):
    g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
    g.action('allocate_attributes',{'allocation':{'luck':5}})
    g.state['player'].update(strength=20,dexterity=20,wisdom=20)
    gear=make_dungeon_gear(key);g.state['equipment_bag'].append(gear)
    public=g.gear_public(gear);slot='accessory1' if public['slot']=='accessory' else public['slot']
    g.action('equip_gear',{'gear_id':gear['id'],'slot':slot})
    self.assertEqual(g.state['loadout'][slot]['signature_id'],key)
    g.action('unequip_gear',{'slot':slot});g.action('stock_gear',{'gear_id':gear['id']})
    item=g.item('gear_'+gear['id']);self.assertEqual(item['name'],gear['signature_name'])
    self.assertEqual(item['gear']['signature_src'],public['src'])
    g.action('place_stock',{'slot':0,'item_id':item['id'],'quantity':1,'mode':'fixed','price':g.sale_cap(item,'fixed')})
    loaded=Game(ROOT/'assets',self.path)
    self.assertEqual(loaded.item(item['id'])['gear'],gear)
    self.assertEqual(loaded.public()['stock'][-1]['wear']['src'],public['src'])

 def test_each_unique_piece_has_its_own_png_artwork(self):
  paths=set()
  for key in DUNGEON_GEAR:
   view=self.g.gear_public(make_dungeon_gear(key));path=ROOT/view['src']
   self.assertTrue(path.is_file(),str(path));self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
   paths.add(path)
  self.assertEqual(len(paths),6)
