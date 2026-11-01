"""Server-timed automatic combat and personality-based theft reactions."""
import copy
import time
import uuid
from equipment import QUALITY, BASE

class CombatMixin:
 def can_attempt_theft(self,c):
  fight=self.state.get("combat")
  deal=self.state.get("deal")
  return (not c.get("final_boss") and not c.get("defeated") and c.get("health",1)>0 and self.state["player_health"]>0
          and not (fight and fight["status"] in ("threatened","ready","active")) and not (deal and deal["status"]=="payment"))
 def theft_attempt_count(self,c):
  if c.get("theft_attempt_visit")==c["visits"]:return c.get("theft_attempts",0)
  return int(c.get("theft_visit")==c["visits"])

 def theft_difficulty(self,c,gear):
  return 10+list(QUALITY).index(gear["quality"])*3+max(0,2-c["mood"])+2*self.theft_attempt_count(c)

 def theft_chance(self,c,gear):
  bonus=self.player_stats()["dexterity"]+self.state["player"].get("luck",0)
  return sum(raw+bonus>=self.theft_difficulty(c,gear) for raw in range(1,21))*5
 def steal_gear(self,gear_id):
  """Roll theft with escalating visit pressure, then apply the customer reaction."""
  self.require_peace();c=self.customer();self.ensure_belongings(c)
  if not c.get("belongings_seen"):raise ValueError("Inspect their belongings first.")
  if self.state.get("deal") and self.state["deal"]["status"]=="payment":raise ValueError("Collect the payment first.")
  if not self.can_attempt_theft(c):raise ValueError("You cannot attempt theft right now.")
  gear=next((g for g in c["belongings"]+c.get("purchased_gear",[]) if g["id"]==gear_id),None)
  if not gear:raise ValueError("That item is no longer carried.")
  attempts=self.theft_attempt_count(c)
  dc=self.theft_difficulty(c,gear)
  c.update(theft_visit=c["visits"],theft_attempt_visit=c["visits"],theft_attempts=attempts+1)
  raw=self.rng.randint(1,20);bonus=self.player_stats()["dexterity"]+self.state["player"].get("luck",0)
  success=raw+bonus>=dc
  self.state["last_roll"]={"raw":raw,"bonus":bonus,"attribute":"Dexterity + Luck","total":raw+bonus,"difficulty":dc,"success":success}
  if success:
   (c["belongings"] if gear in c["belongings"] else c["purchased_gear"]).remove(gear);gear["paid_cost"]=0;self.state["equipment_bag"].append(gear)
   c["health"]=min(c["health"],self.customer_stats(c)["max_hp"])
   c["actions"].append("Stole "+self.item(gear["item_id"])["name"]+" without being noticed.")
   self.state["message"]="The item slips into your pack."
   return
  c["grudge"]=c.get("grudge",0)+1
  mood=c["mood"];c["mood"]=max(0,mood-2)
  c["actions"].append("Caught me trying to steal "+self.item(gear["item_id"])["name"]+".")
  player,enemy=self.player_stats(),self.customer_stats(c)
  strength=lambda s:s["attack"]+s["defense"]+s["hp"]/10
  if strength(player)>strength(enemy)*1.35:
   reaction="Keep away from me. I am leaving."
   c["reaction"]="Intimidated"
  elif self.rng.randrange(100)<{"patient":15,"proud":55,"impatient":80}[c["personality"]]+[20,10,0,-10,-20][mood]:
   self.confront_customer(c);return
  else:
   reaction="Thief! You will never have my trust again."
   c["reaction"]="Insulted"
  self.state["deal"]={"status":"declined","item_id":c["wants"],"offer":0,"agreed":None}
  self.state["message"]=reaction;c["trade_blocked_visit"]=c["visits"]

 def confront_customer(self,c):
  self.start_combat(c)
  fight=self.state["combat"];fight["status"]="threatened"
  fight["logs"]=[c["name"]+" reaches for a weapon."]
  c["actions"][-1]="Threatened me after catching a theft."
  self.state["message"]="One last chance to avoid bloodshed."

 def mercy_difficulty(self,c):
  return {"patient":9,"proud":13,"impatient":16}[c["personality"]]+max(0,2-c["mood"])

 def beg_mercy(self):
  """Resolve a personality-dependent D20 plea before attack timers begin."""
  fight=self.state.get("combat")
  if not fight or fight["status"]!="threatened":raise ValueError("You have no chance to plead now.")
  c=self.state["customers"][fight["customer_id"]]
  raw=self.rng.randint(1,20);bonus=self.effective_eloquence();dc=self.mercy_difficulty(c)
  success=raw+bonus>=dc
  self.state["last_roll"]={"raw":raw,"bonus":bonus,"attribute":"Eloquence","total":raw+bonus,"difficulty":dc,"success":success}
  fight["status"]="spared" if success else "ready"
  line="Your plea is accepted. Leave my sight." if success else "No mercy. Defend yourself!"
  fight["logs"].append(line);self.state["message"]=line
  c["reaction"]="Merciful" if success else "Hostile"
  c["actions"].append("Begged for mercy. "+("Was spared." if success else "Was refused."))

 def choose_fight(self):
  fight=self.state.get("combat")
  if not fight or fight["status"] not in ("threatened","ready"):raise ValueError("There is no confrontation to resolve.")
  now=time.time();fight.update(status="active",started=now,last_tick=now)
  for side in ("player","enemy"):fight[side+"_next"]=now+fight[side+"_interval"]
  fight["logs"].append("The fight begins.")
  self.state["message"]="Steel leaves its sheath."

 def start_combat(self,c):
  """Snapshot attack intervals and initialize independent attack deadlines."""
  self.ensure_belongings(c)
  now=time.time();player,enemy=self.player_stats(),self.customer_stats(c)
  self.state["combat"]={"id":uuid.uuid4().hex,"event_seq":0,"events":[],"status":"active","customer_id":c["id"],"player_next":now+player["interval"],
    "enemy_next":now+enemy["interval"],"player_interval":player["interval"],"enemy_interval":enemy["interval"],
    "started":now,"last_tick":now,"logs":[c["name"]+" draws a weapon!"],"flee_after":0}
  self.state["deal"]=None;c["trade_blocked_visit"]=c["visits"]
  c["actions"].append("Attacked me after catching a theft.")
  self.state["message"]="Steel leaves its sheath."

 def avoidance_chance(self,value):
  """Each attribute point grants half a percentage point, capped at 100%."""
  return min(100,max(0,value*.5))

 def combat_tick(self):
  """Resolve due attacks chronologically; stop immediately when either fighter falls."""
  combat=self.state.get("combat")
  if not combat or combat["status"]!="active":return
  c=self.state["customers"][combat["customer_id"]]
  now=time.time()
  gap=now-combat.get("last_tick",now)
  if gap>3:
   combat["player_next"]+=gap-1
   combat["enemy_next"]+=gap-1
  combat["last_tick"]=now
  enemy=self.customer_stats(c)
  if 0<enemy["hp"]<=enemy["max_hp"]*.4 and c.get("life_potions",0)>0 and now>=combat.get("potion_after",0):
   healed=min(40,enemy["max_hp"]-enemy["hp"])
   c["health"]=enemy["hp"]+healed;c["life_potions"]-=1;combat["potion_after"]=now+3
   combat["enemy_next"]=now+combat["enemy_interval"]
   combat["logs"].append(c["name"]+" drinks a Life Potion, restoring "+str(healed)+" health.")
  # Resolve chronologically so a defeated fighter cannot land a later blow.
  for _ in range(100):
   side="player" if combat["player_next"]<=combat["enemy_next"] else "enemy"
   due=combat[side+"_next"]
   if due>now:break
   player,enemy=self.player_stats(),self.customer_stats(c)
   attacker,defender=(player,enemy) if side=="player" else (enemy,player)
   outcome="hit"
   if self.rng.random()*100<self.dodge_percent(defender,side=="enemy"):outcome="dodge"
   elif self.rng.random()*100<self.avoidance_chance(defender["defense"]):outcome="block"
   damage=max(1,round(attacker["attack"]-defender["defense"]*.5)) if outcome=="hit" else 0
   charged=False
   if c.get("final_boss") and side=="enemy":
    combat["enemy_strikes"]=combat.get("enemy_strikes",0)+1
    charged=combat["enemy_strikes"]%4==0
    if charged and outcome=="hit":damage=round(damage*1.35)
   critical=bool(outcome=="hit" and side=="player" and self.skill_rank("critical_strike") and self.rng.random()<.05*self.skill_rank("critical_strike"))
   if critical:damage=round(damage*1.5)
   if side=="player":c["health"]=max(0,c["health"]-damage)
   else:self.state["player_health"]=max(0,self.state["player_health"]-damage)
   weapon=(self.state["loadout"]["weapon"] if side=="player" else next((g for g in c.get("belongings",[]) if BASE[g["item_id"]][0]=="weapon"),None))
   if c.get("final_boss") and side=="enemy":weapon={"item_id":"greatsword"}
   combat["event_seq"]=combat.get("event_seq",0)+1
   combat.setdefault("events",[]).append({"id":combat["event_seq"],"side":side,"damage":damage,"outcome":outcome,"critical":critical,"charged":charged,"weapon":weapon["item_id"] if weapon else "unarmed"})
   combat["events"]=combat["events"][-24:]
   if outcome=="hit":line=("You hit "+c["name"] if side=="player" else c["name"]+" hits you")+" for "+str(damage)+"."
   else:line=(c["name"] if side=="player" else "You")+(" dodges the attack." if outcome=="dodge" else " blocks the attack.")
   if charged:line="Execution! "+line
   combat["logs"].append(line)
   combat["logs"]=combat["logs"][-8:]
   combat[side+"_next"]+=combat[side+"_interval"]
   if c["health"]==0:
    combat["status"]="victory";c["defeated"]=True
    combat["logs"].append(c["name"]+" collapses. The fight is over.")
    c["actions"].append("Lost a fight against me.")
    self.claim_combat_spoils(c,combat)
    if c.get("final_boss"):
     self.state["final_boss"]["status"]="defeated"
     self.check_ending()
    self.gain_xp(25)
    heal=round(self.player_stats()["max_hp"]*.1*self.skill_rank("second_wind"))
    if heal:
     self.state["player_health"]=min(self.player_stats()["max_hp"],self.state["player_health"]+heal)
     combat["logs"].append("Second wind restores "+str(heal)+" health.")
    break
   if c.get("final_boss") and combat.get("phase",1)==1 and c["health"]<=self.boss_stats(c)["max_hp"]/2:
    combat["phase"]=2;combat["enemy_interval"]=2.0
    combat["enemy_next"]=min(combat["enemy_next"],now+2.0)
    combat["logs"].append("Veyne breaks his oath: stronger blows, faster attacks!")
   if self.state["player_health"]==0:
    combat["status"]="defeat"
    if c.get("final_boss"):self.state["final_boss"]["status"]="waiting"
    slots=[slot for slot,gear in self.state["loadout"].items() if gear]
    stolen_slots=self.rng.sample(slots,min(len(slots),self.rng.randint(1,2))) if slots else []
    combat["lost_equipment"]=[]
    for slot in stolen_slots:
     gear=self.state["loadout"][slot];self.state["loadout"][slot]=None
     combat["lost_equipment"].append(copy.deepcopy(gear));c.setdefault("purchased_gear",[]).append(gear)
    names=[self.gear_public(g)["name"] for g in combat["lost_equipment"]]
    combat["logs"].append("You collapse. "+("Taken: "+", ".join(names)+"." if names else "No equipment was taken."))
    c["actions"].append("Robbed me of "+", ".join(names)+"." if names else "Found no equipment to take.")
    c["actions"].append("Defeated me in a fight.");break

 def flee_combat(self):
  self.combat_tick();combat=self.state.get("combat")
  if not combat or combat["status"]!="active":raise ValueError("There is no fight to escape.")
  if time.time()<combat["flee_after"]:raise ValueError("You need a moment before trying again.")
  combat["flee_after"]=time.time()+3
  if self.rng.randint(1,20)+self.player_stats()["dexterity"]>=11:
   combat["status"]="escaped";combat["logs"].append("You retreat behind the counter.")
   if self.customer().get("final_boss"):
    self.state["final_boss"]["status"]="waiting";self.state["current_id"]=None
  else:combat["logs"].append("Your escape is blocked!")

 def combat_public(self):
  combat=copy.deepcopy(self.state.get("combat"))
  if not combat:return None
  now=time.time()
  for side in ["player","enemy"]:combat[side+"_remaining"]=max(0,combat[side+"_next"]-now)
  c=self.state["customers"][combat["customer_id"]]
  combat["enemy"]=self.customer_stats(c);combat["name"]=c["name"]
  combat["lost_equipment"]=[self.gear_public(g) for g in combat.get("lost_equipment",[])]
  if combat.get("rewards"):combat["rewards"]["equipment"]=[self.gear_public(g) for g in combat["rewards"]["equipment"]]
  if combat["status"] in ("threatened","ready"):
   dc=self.mercy_difficulty(c);bonus=self.effective_eloquence()
   combat["mercy"]={"difficulty":dc,"bonus":bonus,"personality":c["personality"],"chance":sum(raw+bonus>=dc for raw in range(1,21))*5}
  return combat
