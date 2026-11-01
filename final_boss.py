"""The family nemesis appears after debt repayment; victory completes the story."""
import copy
BOSS_ID="nemesis_malrec_veyne"
BOSS_NAME="Lord Malrec Veyne"
class FinaleMixin:
 def prepare_finale(self):
  """Unlock the nemesis after repayment and end the story only after victory."""
  loan=self.state['loan']
  if loan['balance'] or loan['interest_arrears']:return
  # Earlier debt-only endings become the entrance to the final chapter.
  if self.state.get('ending') and not self.state['ending'].get('nemesis_defeated'):self.state.pop('ending')
  if not self.state.get('final_boss'):
   self.state['final_boss']={'status':'waiting','introduced':False,'attempts':0,'unlocked_day':self.state['day']}
  if self.state['final_boss']['status']=='defeated' and not self.state.get('ending') and (self.state.get('combat') or {}).get('rewards',{}).get('claimed',True):
   self.state['ending']={'day':self.state['day'],'gold':self.state['gold'],'repaid':loan['original'],'visits':self.state['total_visits'],'nemesis_defeated':True,'nemesis':BOSS_NAME}

 def boss_stats(self,c):
  enraged=c.get('health',420)<=210
  return {'max_hp':420,'hp':max(0,min(420,c.get('health',420))),'attack':54 if enraged else 46,'defense':28,'interval':2.0 if enraged else 2.4,'strength':14,'dexterity':10,'wisdom':10}

 def finale_public(self):
  finale=copy.deepcopy(self.state.get('final_boss'))
  if finale:finale.update(name=BOSS_NAME,portrait='assets/characters/final_boss_malrec.png',max_hp=420,attack=46,defense=28,interval=2.4)
  return finale

 def acknowledge_boss(self):
  if not self.state.get('final_boss'):raise ValueError('Your nemesis has not arrived.')
  self.state['final_boss']['introduced']=True

 def begin_final_battle(self):
  self.require_peace();finale=self.state.get('final_boss')
  if not finale or finale['status']!='waiting':raise ValueError('The final duel is not available.')
  if self.state['current_id'] is not None:raise ValueError('See your customer out before the final duel.')
  c=self.state['customers'].get(BOSS_ID)
  if c is None:
   c={'id':BOSS_ID,'name':BOSS_NAME,'race':'Human','sex':'male','portrait':'final_boss_malrec.png','equipment':'blackened noble plate and an executioner greatsword','personality':'proud','wealth':'wealthy','budget':0,'mood':0,'visits':1,'purchases':[],'actions':[],'known':[],'wants':None,'destination':'the ruins of your family estate','willingness':{},'refused':[],'weapon_type':'greatsword','profession':'The Oathbreaker','armour':'Blackened plate with a broken-sun crest.','accessories':'The signet of House Veyne.','belongings':[],'purchased_gear':[],'final_boss':True,'wanted':False}
   self.state['customers'][BOSS_ID]=c
  c.update(health=420,defeated=False)
  finale.update(status='active',introduced=True,attempts=finale['attempts']+1)
  self.state['caravan']['open']=False;self.state['current_id']=BOSS_ID
  self.start_combat(c);self.state['combat'].update(final_boss=True,phase=1,enemy_strikes=0)
  self.state['combat']['logs']=[BOSS_NAME+': Your debt is gone. Your bloodline ends tonight.']
  self.state['message']='The man who ruined your family stands before you.'

 def attack_wanted(self):
  self.require_peace();c=self.customer()
  if not c.get('wanted') or c.get('defeated'):raise ValueError('This person is not a wanted criminal you can attack.')
  if self.state.get('deal') and self.state['deal']['status']=='payment':raise ValueError('Collect the payment first.')
  c['mood']=0;self.start_combat(c)
  self.state['combat']['logs']=['You confront '+c['name']+' over the bounty.']
  c['actions'][-1]='I attacked them to claim their bounty.'

 def claim_combat_spoils(self,c,combat):
  if not (c.get('wanted') or c.get('final_boss')):return
  gear=copy.deepcopy(c.get('belongings',[])+c.get('purchased_gear',[]))
  for item in gear:item['paid_cost']=0
  gold=max(0,c.get('budget',0))+(100 if c.get('wanted') else 0)
  c['budget']=0;c['belongings']=[];c['purchased_gear']=[]
  combat['rewards']={'gold':gold,'equipment':gear,'claimed':not (gold or gear)}
  combat['logs'].append('The spoils are yours.')

 def collect_combat_rewards(self):
  """Claim pending spoils once; old saves without a flag were already paid."""
  combat=self.state.get('combat')
  if not combat or combat['status']!='victory':raise ValueError('There are no spoils to collect.')
  rewards=combat.get('rewards')
  # Missing flags belong to older saves whose rewards were already granted.
  if not rewards or rewards.get('claimed',True):raise ValueError('These spoils have already been collected.')
  self.state['gold']+=rewards['gold']
  self.state['equipment_bag'].extend(copy.deepcopy(rewards['equipment']))
  rewards['claimed']=True
  self.state['message']='Spoils collected.'
