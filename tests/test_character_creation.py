"""Five starting points are validated, saved once, and never granted to old saves."""
import copy,random,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from game import Game
class CharacterCreationTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'save.json';self.g=Game(ROOT/'assets',self.path,random.Random(7),load_existing=False)
 def test_fresh_character_has_five_points_and_cannot_skip_creation(self):
  creation=self.g.public()['creation'];self.assertFalse(creation['completed']);self.assertEqual(creation['points'],5)
  for action in ['finish_intro','finish_market','merchant_buy','learn_skill','arrive']:
   with self.assertRaises(ValueError):self.g.action(action,{})
  self.assertEqual(self.g.state['gold'],1000)
 def test_balanced_allocation_changes_exactly_five_attributes_and_persists(self):
  base=copy.deepcopy(self.g.state['player']);choices={key:1 for key in ['strength','dexterity','wisdom','eloquence','luck']}
  self.g.action('allocate_attributes',{'allocation':choices})
  for key,value in choices.items():self.assertEqual(self.g.state['player'][key],base[key]+value)
  self.assertEqual(self.g.player_stats()['max_hp'],110);self.assertEqual(self.g.state['player_health'],110)
  self.assertEqual(self.g.state['creation']['points'],0);self.assertTrue(self.g.has_progress())
  loaded=Game(ROOT/'assets',self.path);self.assertEqual(loaded.state['player'],self.g.state['player']);self.assertTrue(loaded.state['creation']['completed'])
  loaded.action('finish_intro',{});self.assertTrue(loaded.public()['intro_seen'])
 def test_invalid_allocations_are_atomic(self):
  for choices in [None,[],{'strength':4},{'strength':6},{'strength':5,'attack':0},{'strength':True,'luck':4},{'strength':-1,'luck':6},{'strength':2.5,'luck':2.5},{'strength':'5'}]:
   before=copy.deepcopy(self.g.state)
   with self.assertRaises(ValueError):self.g.action('allocate_attributes',{'allocation':choices})
   self.assertEqual(self.g.state,before)
 def test_confirm_cannot_be_replayed_or_changed_after_reload(self):
  self.g.action('allocate_attributes',{'allocation':{'strength':5}});self.assertEqual(self.g.state['player_health'],150)
  for g in [self.g,Game(ROOT/'assets',self.path)]:
   before=copy.deepcopy(g.state)
   with self.assertRaises(ValueError):g.action('allocate_attributes',{'allocation':{'luck':5}})
   self.assertEqual(g.state,before)
 def test_old_campaign_keeps_original_attributes_and_has_no_pending_points(self):
  self.g.state.pop('creation');self.g.state['player'].update(strength=7,dexterity=6,wisdom=5,eloquence=4,luck=3);self.g.state['gold']=123;self.g.save()
  loaded=Game(ROOT/'assets',self.path)
  self.assertEqual(loaded.state['player'],self.g.state['player']);self.assertEqual(loaded.state['gold'],123)
  self.assertTrue(loaded.state['creation']['completed']);self.assertEqual(loaded.state['creation']['points'],0)
  with self.assertRaises(ValueError):loaded.action('allocate_attributes',{'allocation':{'luck':5}})
 def test_new_game_resets_allocation_and_preserves_old_campaign_backup(self):
  self.g.action('allocate_attributes',{'allocation':{'wisdom':5}});self.g.action('new_game',{})
  self.assertEqual(self.g.state['player']['wisdom'],2);self.assertFalse(self.g.state['creation']['completed']);self.assertEqual(self.g.state['creation']['points'],5)
  backups=list(self.path.parent.glob('save-backup-*.json'));self.assertEqual(len(backups),1)
  archived=Game(ROOT/'assets',backups[0]);self.assertEqual(archived.state['player']['wisdom'],7)
 def test_pending_creation_survives_saving_and_reloading(self):
  self.g.action('save',{});loaded=Game(ROOT/'assets',self.path)
  self.assertFalse(loaded.state['creation']['completed']);self.assertEqual(loaded.state['creation']['points'],5)
