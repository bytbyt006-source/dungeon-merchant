// Equipment is transferred and combat is resolved by the Python rules.
let equipmentView='player',combatPolling=false,combatSnapshotAt=0;
function equipmentCard(g,owner){
 const card=element('article',undefined,'gear-card');card.dataset.quality=g.quality;
 const head=element('div',undefined,'gear-card-heading'),art=element('img');art.src=g.src;art.alt='';
 head.append(art,element('strong',g.name));card.append(head);
 const info=element('div',undefined,'gear-properties');info.append(element('span',g.quality[0].toUpperCase()+g.quality.slice(1)));
 if(g.attack)info.append(iconStat('gear',g.attack,'Attack'));
 if(g.defense)info.append(iconStat('shield',g.defense,'Defense'));
 if(g.interval)info.append(iconStat('clock',g.interval+'s','Attack interval'));
 card.append(info);
 const requirements=element('div',undefined,'wear-requirements');requirements.append(element('small','Requires'));
 for(const [stat,value] of Object.entries(g.requirements||{})){const target=g.slot==='accessory'?'accessory1':g.slot;const missing=state.equipment.stats[stat]<value||(g.equip_failures?.[target]||[]).some(f=>f.slot===target&&f.stat===stat);const label=element('span',stat[0].toUpperCase()+stat.slice(1)+' '+value,missing?'requirement-missing':'requirement-met');label.title=stat+': '+state.equipment.stats[stat]+' / '+value;requirements.append(label);}
 if(Object.keys(g.requirements||{}).length)card.append(requirements);
 if(!g.identified){const needed=g.identification_wisdom??g.requirement;card.append(element('small','Identify · Wisdom '+needed,state.equipment.stats.wisdom<needed?'requirement-missing':'muted'));}
 const affixes=element('ul',undefined,'gear-affixes');
 if(g.identified){g.affixes.forEach(a=>affixes.append(element('li',a.text)));}
 else affixes.append(element('li','Unidentified','muted'));
 card.append(affixes);
 const buttons=element('div',undefined,'gear-actions');
 const add=(label,handler,disabled=false)=>{const button=element('button',label);button.type='button';button.dataset.unavailable=String(disabled);button.disabled=busy||disabled;button.onclick=handler;buttons.append(button);return button;};
 if(owner==='customer'){
  const buy=add('',()=>act('buy_belonging',{gear_id:g.id}),!state.customer.can_buy_belongings||state.gold<g.buy_price);
  buy.replaceChildren(uiIcon('coin'),document.createTextNode(g.buy_price+' '),uiIcon('check'));buy.setAttribute('aria-label','Buy '+g.name+' for '+g.buy_price+' gold');buy.title='Buy';
  if(!g.identified)add('Identify',()=>act('identify_gear',{gear_id:g.id}),state.equipment.stats.wisdom<(g.identification_wisdom??g.requirement));
  const steal=add('Steal',()=>{$('#equipmentDialog').close();act('steal_gear',{gear_id:g.id});},!state.customer.can_steal);
  steal.classList.add('steal-action');if(g.steal_chance!==undefined){steal.append(document.createTextNode(' · '+g.steal_chance+'%'));steal.title='D20 + Dexterity + Luck · Difficulty '+g.steal_difficulty;}
 }else if(owner==='bag'||owner==='stock'){
  if(!g.identified)add('Identify',()=>act('identify_gear',{gear_id:g.id}),state.equipment.stats.wisdom<(g.identification_wisdom??g.requirement));
  const stored=owner!=='stock'||state.warehouse[g.stock_id||g.item_id]>0;
  const wearSlots=g.slot==='accessory'?['accessory1','accessory2']:[g.slot];
  for(const slot of wearSlots){
   const failures=g.equip_failures?.[slot]||[];
   const label=slot==='accessory1'?'Wear · I':slot==='accessory2'?'Wear · II':'Equip';
   const button=add(label,()=>act('equip_gear',owner==='stock'?{item_id:g.stock_id||g.item_id,slot}:{gear_id:g.id,slot}),!stored||!g.equip_options?.[slot]);
   if(failures.length)button.title=failures.map(f=>f.stat[0].toUpperCase()+f.stat.slice(1)+': '+f.available+' / '+f.required).join(' · ');
  }
  if(!stored)card.append(element('p','No items in storage.','equip-blocked-reason'));
  else if(!wearSlots.some(slot=>g.equip_options?.[slot])){
   const failures=g.equip_failures?.[wearSlots[0]]||[];
   if(failures.length)card.append(element('p',failures.map(f=>f.stat[0].toUpperCase()+f.stat.slice(1)+': '+f.available+' / '+f.required).join(' · '),'equip-blocked-reason'));
  }
  if(owner==='bag')add('Sell',()=>prepareGearSale(g));
 }else if(owner==='merchant'){
  const buy=add('',()=>act('buy_gear',{gear_id:g.id}),g.price>state.gold);buy.replaceChildren(uiIcon('coin'),document.createTextNode(g.price),uiIcon('check'));buy.setAttribute('aria-label','Buy '+g.name+' for '+g.price+' gold');
 }
 if(owner==='worn'&&!g.identified)add('Identify',()=>act('identify_gear',{gear_id:g.id}),state.equipment.stats.wisdom<(g.identification_wisdom??g.requirement));
 card.append(buttons);return card;
}
async function prepareGearSale(gear){
 const id='gear_'+gear.id;
 await act('stock_gear',{gear_id:gear.id});
 if(!(state.warehouse[id]>0))return;
 $('#equipmentDialog').close();
 if(!$('#warehouseDialog').open)$('#warehouseDialog').showModal();
 warehouseItem=id;warehouseMode=null;
 restoreShelfSettings(state.stock.find(item=>item.id===id));
 renderWarehouse();renderEquipment();controls();
 $('#shelfForm').scrollIntoView({block:'nearest',behavior:prefersReducedMotion()?'instant':'smooth'});
}
function renderEquipment(){
 if(!state?.equipment)return;
 $('#potionCount').textContent=state.warehouse.life_potion||0;
 const stats=state.equipment.stats,combat=state.combat,fighting=combat?.status==='active';
 $('#playerVitals').replaceChildren(element('span',stats.hp+' / '+stats.max_hp+' HP'),iconStat('shield',stats.defense,'Defense'));
 const hp=element('progress');hp.max=stats.max_hp;hp.value=stats.hp;hp.setAttribute('aria-label','Your health');$('#playerVitals').append(hp);
 const visible=!!combat&&!!state.customer&&!['threatened','ready'].includes(combat.status);
 $('#playerVitals').hidden=visible;
 const playerHud=$('#playerCombatHud');playerHud.hidden=!visible;
 const enemy=$('#enemyVitals');enemy.hidden=!visible;
 const panel=$('#combatPanel');panel.hidden=!visible;
 $('#shopScene').classList.toggle('in-battle',visible);
 $('#shopScene').classList.toggle('boss-battle',!!combat?.final_boss&&visible);
 $('#combatChest').hidden=!(visible&&combat?.status==='victory'&&combat.rewards?.claimed===false);
 $('#finishCombat').hidden=!(visible&&['victory','escaped','spared'].includes(combat.status)&&combat.rewards?.claimed!==false&&!state.ending);
 $('#combatRewards').replaceChildren();
 if(combat?.rewards){const rewards=combat.rewards;$('#combatRewards').append(iconStat('coin',rewards.gold,'Gold'));for(const gear of rewards.equipment){const row=element('div',undefined,'combat-reward-item'),art=element('img');art.src=gear.src;art.alt='';row.dataset.quality=gear.quality;row.append(art,element('strong',gear.name));$('#combatRewards').append(row);}}
 if(visible){
  if(combat.final_boss)$('#mood').textContent=combat.phase===2?'Oathbroken Fury':'The Oathbreaker';
  combatSnapshotAt=performance.now();
  const playerBar=element('progress');playerBar.max=stats.max_hp;playerBar.value=stats.hp;playerBar.setAttribute('aria-label','Your combat health');
  $('#playerBattleVitals').replaceChildren(element('strong','YOU · '+stats.hp+' / '+stats.max_hp+' HP'),iconStat('shield',stats.defense,'Your defense'),playerBar);
  const s=combat.enemy,bar=element('progress');bar.max=s.max_hp;bar.value=s.hp;bar.setAttribute('aria-label',combat.name+' health');
  const enemyTimer=element('div');enemyTimer.id='enemyAttackTimer';
  enemy.replaceChildren(element('strong',s.hp+' / '+s.max_hp+' HP'),bar,iconStat('shield',s.defense,'Defense'),enemyTimer);
  const makeTimer=(side,label)=>{const row=element('div',undefined,'attack-timer'),progress=element('progress');progress.max=combat[side+'_interval'];progress.dataset.side=side;progress.setAttribute('aria-label',label+' attack progress');row.append(element('span',label),progress,element('small',''));return row;};
  $('#playerAttackTimer').replaceChildren();
  if(fighting){$('#playerAttackTimer').append(makeTimer('player','Attack'));enemyTimer.append(makeTimer('enemy',combat.final_boss&&(combat.enemy_strikes||0)%4===3?'Execution':'Attack'));}
  $('#combatTimers').replaceChildren();
  if(!fighting)$('#combatTimers').append(element('strong',{victory:'Victory',defeat:'Defeated · Rest until tomorrow',escaped:'Escaped',spared:'Spared'}[combat.status]));
  if($('#combatLog').textContent!==combat.logs.join('')){$('#combatLog').replaceChildren(...combat.logs.map(line=>element('li',line)));$('#combatLog').scrollTop=$('#combatLog').scrollHeight;}$('#fleeCombat').hidden=!fighting;
  $('#deal').hidden=true;
 }
 if(typeof syncBattleFeedback==='function')syncBattleFeedback(state);
 if(typeof syncMusic==='function')syncMusic();
 renderConfrontation();
 if($('#equipmentDialog').open){
  const customer=equipmentView==='customer',c=state.customer;
  if(customer&&!c){$('#equipmentDialog').close();return;}
  $('#equipmentTitle').textContent=customer?c.name.toUpperCase()+' · BELONGINGS':'YOUR EQUIPMENT';
  $('#equipmentStats').replaceChildren(...(customer?[iconStat('shield',c.stats.defense,'Defense'),element('span',c.stats.hp+' HP'),element('span','Strength '+c.stats.strength),element('span','Dexterity '+c.stats.dexterity),element('span','Wisdom '+c.stats.wisdom)]:[element('span',stats.hp+' / '+stats.max_hp+' HP'),iconStat('gear',stats.attack,'Attack'),iconStat('shield',stats.defense,'Defense'),iconStat('clock',stats.interval+'s','Attack interval'),element('span','Strength '+stats.strength),element('span','Dexterity '+stats.dexterity),element('span','Wisdom '+stats.wisdom)]));
  if(!customer)$('#equipmentStats').append(element('span','Eloquence '+state.player.eloquence),element('span','Luck '+state.player.luck));
  $('#equipmentStats').append(element('span','Dodge '+(customer?Math.min(100,c.stats.dexterity*.5):stats.dodge)+'%'),element('span','Block '+Math.min(100,(customer?c.stats:stats).defense*.5)+'%'));
  const slots=$('#equipmentSlots');slots.replaceChildren();slots.hidden=customer;
  if(!customer)for(const [slot,g] of Object.entries(state.equipment.loadout)){
   const box=element('section',undefined,'equipment-slot');box.append(element('h3',{weapon:'WEAPON',armour:'ARMOUR',accessory1:'ACCESSORY I',accessory2:'ACCESSORY II'}[slot]));
   if(g){const card=equipmentCard(g,'worn'),remove=element('button','Unequip');remove.onclick=()=>act('unequip_gear',{slot});card.append(remove);box.append(card);}else box.append(element('span','Empty','muted'));slots.append(box);
  }
  const list=$('#equipmentItems');list.replaceChildren();
  if(customer){c.belongings.forEach(g=>list.append(equipmentCard(g,'customer')));if(c.life_potions){const pot=element('div',undefined,'potion-card');pot.append(itemIcon({id:'life_potion'}),element('strong','Life Potion ×'+c.life_potions));list.append(pot);}}
  else{
   state.equipment.bag.forEach(g=>list.append(equipmentCard(g,'bag')));
   state.stock.filter(item=>item.wear&&state.warehouse[item.id]>0).forEach(item=>{
    const accessory=item.category==='accessory',armour=item.category==='armour'||item.id==='shield';
    const g={...item.wear,stock_id:item.id};
    const card=equipmentCard(g,'stock');card.append(element('small','×'+state.warehouse[item.id]));list.append(card);
   });
   if(!list.children.length)list.append(element('p','No equipment in storage.','muted'));
  }
 }
 if($('#warehouseDialog').open){$('#warehouseGear').hidden=!state.equipment.bag.length;$('#warehouseGearItems').replaceChildren(...state.equipment.bag.map(g=>equipmentCard(g,'bag')));}
 let wares=$('#enchantedWares');
 if(state.caravan.open&&!$('#wares').hidden){if(!wares){wares=element('section');wares.id='enchantedWares';$('#merchantStock').after(wares);}wares.replaceChildren(element('h2','ENCHANTED EQUIPMENT'),...state.caravan.gear_stock.map(g=>equipmentCard(g,'merchant')));}else wares?.remove();
 controls();
}
$('#drinkPotion').onclick=()=>act('drink_potion');
$('#equipmentOpen').prepend(uiIcon('shield'));
$('#belongingsOpen').prepend(uiIcon('scroll'));
$('#equipmentOpen').onclick=()=>{equipmentView='player';$('#equipmentStatus').textContent=state.equipment.notice||'';$('#equipmentDialog').showModal();renderEquipment();};
$('#equipmentClose').onclick=()=>$('#equipmentDialog').close();
$('#belongingsOpen').onclick=async()=>{await act('inspect_belongings');if(state.customer?.belongings_seen){equipmentView='customer';$('#equipmentStatus').textContent='';$('#equipmentDialog').showModal();renderEquipment();}};
$('#combatChest').onclick=()=>act('collect_combat_rewards');
$('#finishCombat').onclick=()=>act('leave');
$('#fleeCombat').onclick=()=>act('flee_combat');
const equipmentBaseControls=controls;
controls=function(){
 equipmentBaseControls();
 const fight=['active','threatened','ready'].includes(state?.combat?.status);
 $('#attackWanted').disabled=busy||fight||!state?.customer?.wanted||state?.customer?.defeated||state?.deal?.status==='payment'||state?.equipment?.stats.hp<=0||phase!=='present';
 $('#equipmentOpen').disabled=busy||fight||phase==='arriving'||phase==='leaving';
 $('#belongingsOpen').disabled=busy||fight||!state?.customer||phase!=='present';
 $('#drinkPotion').disabled=busy||!state||state.equipment.stats.hp<=0||state.equipment.stats.hp>=state.equipment.stats.max_hp||!(state.warehouse?.life_potion>0)||['threatened','ready'].includes(state.combat?.status)||phase==='arriving'||phase==='leaving'||!!state.ending;
 $('#fleeCombat').disabled=busy;
 $('#combatChest').disabled=busy||phase!=='present';
 $('#finishCombat').disabled=busy||phase!=='present';
 if(state?.combat?.rewards?.claimed===false){$('#leave').disabled=true;$('#skipDay').disabled=true;}
 $('#equipmentDialog').querySelectorAll('button').forEach(b=>b.disabled=busy||fight||b.dataset.unavailable==='true');
 if(fight){for(const id of ['menuOpen','saveGame','visitCaravan','skillsOpen','warehouseOpen','commissionsOpen','leave','skipDay','enter'])$('#'+id).disabled=true;document.querySelectorAll('.shop button,.clues button').forEach(b=>b.disabled=true);}
 if(state?.equipment?.stats.hp<=0){for(const id of ['menuOpen','saveGame','visitCaravan','skillsOpen','warehouseOpen','commissionsOpen','equipmentOpen','belongingsOpen','leave','skipDay','enter','nextDay'])$('#'+id).disabled=true;}
 $('#deathMenu').disabled=busy;
 if(state?.customer?.trade_blocked){document.querySelectorAll('.shop button').forEach(b=>{if(!b.textContent.includes('Manage'))b.disabled=true;});}
};
setInterval(()=>{
 if(!state?.combat||state.combat.status!=='active'||$('#titleScreen').open)return;
 const elapsed=(performance.now()-combatSnapshotAt)/1000;
 document.querySelectorAll('#playerAttackTimer progress,#enemyAttackTimer progress').forEach(bar=>{const side=bar.dataset.side,remaining=Math.max(0,state.combat[side+'_remaining']-elapsed);bar.value=Math.max(0,bar.max-remaining);bar.nextElementSibling.textContent=remaining.toFixed(1)+'s';});
},100);
setInterval(async()=>{
 if(busy||combatPolling||!state?.combat||state.combat.status!=='active'||$('#titleScreen').open||document.hidden)return;
 combatPolling=true;
 try{const data=await request({action:'combat_tick'});if(data.state.revision<state.revision)return;state=data.state;if(state.combat.status==='active')renderEquipment();else render();}
 catch(e){$('#error').textContent=e.message;}finally{combatPolling=false;}
},500);

function renderConfrontation(){
 const fight=state?.combat,dialog=$('#confrontationDialog'),waiting=['threatened','ready'].includes(fight?.status);
 if(waiting&&!busy&&!$('#titleScreen').open){
  $('#confrontationText').textContent=fight.name+(fight.status==='ready'?' refuses your plea.':' reaches for a weapon. What will you do?');
  const mercy=fight.mercy;
  $('#mercyOdds').textContent=fight.status==='ready'?'No mercy.':mercy.personality[0].toUpperCase()+mercy.personality.slice(1)+' · D20 + Eloquence '+mercy.bonus+' · '+mercy.chance+'%';
  $('#begMercy').hidden=fight.status!=='threatened';
  if(!dialog.open)dialog.showModal();
 }else if(dialog.open)dialog.close();
 const dead=state?.equipment?.stats.hp<=0&&!state?.ending;
 if(dead&&!busy&&!$('#titleScreen').open){
  const lost=fight?.lost_equipment||[];
  $('#defeatMessage').textContent=lost.length?fight.name+' took your equipment.':'No equipment was taken.';
  $('#defeatLoot').replaceChildren(...lost.map(g=>{const card=element('div',undefined,'defeat-loot-item');card.dataset.quality=g.quality;const image=element('img');image.src=g.src;image.alt='';card.append(image,element('strong',g.name));return card;}));
  if(!$('#deathDialog').open)$('#deathDialog').showModal();
 }
 if(!dead&&$('#deathDialog').open)$('#deathDialog').close();
}
$('#confrontationDialog').addEventListener('cancel',e=>e.preventDefault());
$('#deathDialog').addEventListener('cancel',e=>e.preventDefault());
$('#chooseFight').onclick=()=>{$('#confrontationDialog').close();act('fight');};
$('#begMercy').onclick=()=>{$('#confrontationDialog').close();act('beg_mercy');};
$('#deathMenu').onclick=()=>act('rest');

$('#attackWanted').onclick=()=>act('attack_wanted');
