// Commission menus use public state and server-calculated expedition terms.
let commissionRegion='mine',commissionAdventurer=null,commissionWeapon=null,commissionArmour=null,commissionRelic=false,commissionDeep=false,commissionPreviewVersion=0;
function commissionChoice(text,selected,handler,unavailable=false){
 const button=element('button',text);button.type='button';button.setAttribute('aria-pressed',String(selected));
 button.dataset.unavailable=String(unavailable);button.disabled=busy||unavailable;button.onclick=handler;return button;
}
function relicArt(id){const image=element('img',undefined,'relic-art');image.src='assets/relics/'+id+'.png';image.alt='';return image;}
let relicActionRegion='mine';
function renderCommissions(){
 if(!state?.commission_board)return;
 const board=state.commission_board;if($('#relicActionsDialog').open)renderRelicActions();
 $('#commissionsOpen').replaceChildren(uiIcon('map'),document.createTextNode('Commissions'+(board.ready?' · '+board.ready+' ready':'')));$('#commissionsOpen').classList.add('label-icon-button');
 if(!$('#commissionDialog').open)return;
 const region=board.regions.find(r=>r.id===commissionRegion);
 const roster=board.roster.find(c=>c.id===commissionAdventurer);
 if(!roster?.available){commissionAdventurer=null;commissionWeapon=null;commissionArmour=null;commissionRelic=false;}
 const locations=$('#commissionRegions');locations.replaceChildren();
 board.regions.forEach(r=>{
  const button=commissionChoice('',r.id===commissionRegion,()=>{commissionRegion=r.id;commissionDeep=false;commissionRelic=false;renderCommissions();controls();},!r.unlocked);
  button.setAttribute('aria-label',r.name);
  button.classList.add('location-card');button.title=r.description+(r.unlocked?'':' · Discover the previous route first');
  const thumbnail=element('img',undefined,'location-thumbnail');thumbnail.src='assets/locations/'+r.id+'.png';thumbnail.alt='';button.append(thumbnail);
  const body=element('div',undefined,'location-card-body');body.append(element('strong',r.name));
  const stats=element('div',undefined,'icon-stat-row');stats.append(iconStat('coin',r.fee,'Commission fee in gold'),iconStat('clock',r.days,'Travel days'));
  if(!r.unlocked){const lock=uiIcon('lock');lock.classList.add('location-lock');button.append(lock);stats.append(iconStat('lock','Locked','Discover the previous route first'));}
  body.append(stats);const loot=element('div',undefined,'region-rewards');loot.title='Possible rewards';loot.append(uiIcon('chest'));
  r.loot.forEach(id=>{const item=state.stock.find(i=>i.id===id),image=itemIcon(item);image.title=item.name;loot.append(image);});body.append(loot);
  for(const unique of r.unique_rewards||[]){const image=element('img',undefined,'item-icon');image.src=unique.src;image.alt='';image.title=unique.name;image.classList.add('unique-reward');loot.append(image);}
  const treasure=relicArt(r.id);treasure.title=r.relic;loot.append(treasure);button.append(body);locations.append(button);
 });
 const depth=$('#commissionDepth');depth.replaceChildren();
 depth.append(commissionChoice('Regular route',!commissionDeep,()=>{commissionDeep=false;renderCommissions();controls();}),commissionChoice(region.deep_unlocked?'Deeper route · double loot':'Deeper route · keep 2 relics to unlock',commissionDeep,()=>{commissionDeep=true;renderCommissions();controls();},!region.deep_unlocked));
 depth.querySelectorAll('button').forEach((button,index)=>{const label=button.textContent;button.setAttribute('aria-label',label);button.title=label;button.replaceChildren(uiIcon(index===0?'map':region.deep_unlocked?'chest':'lock'),document.createTextNode(index===0?'Regular':'Depths · ×2'));button.classList.add('label-icon-button');});
 const people=$('#commissionRoster');people.replaceChildren();
 if(!board.roster.length)people.append(element('p','No adventurers known yet. Serve your first customer.','muted'));
 board.roster.forEach(c=>{
  const button=commissionChoice('',c.id===commissionAdventurer,()=>{commissionAdventurer=c.id;commissionWeapon=null;commissionArmour=null;commissionRelic=false;renderCommissions();controls();},!c.available);
  button.setAttribute('aria-label',c.name+' · '+c.profession);
  const portrait=element('img');portrait.src='assets/characters/'+c.portrait;portrait.alt='';
  button.append(portrait,element('strong',c.name),element('span',c.profession));const stats=element('div',undefined,'icon-stat-row');stats.append(iconStat('star','+'+c.skill,'Skill'),iconStat('trophy',c.wins+'/'+c.attempts,'Successful expeditions'));if(!c.available)stats.append(iconStat('clock',c.id===state.customer?.id?'Serving':'Away','Currently unavailable'));button.append(stats);people.append(button);
 });
 $('#commissionPreparation').hidden=!commissionAdventurer;
 if(commissionAdventurer){
  const c=board.roster.find(c=>c.id===commissionAdventurer),gear=$('#commissionGear');gear.replaceChildren();
  for(const slot of ['weapon','armour']){
   const section=element('section',undefined,'loan-slot'),heading=element('h4',slot==='weapon'?'WEAPON':'ARMOUR','storage-label'),choices=element('div',undefined,'loan-slot-options');
   section.append(heading,choices);gear.append(section);
   const selected=slot==='weapon'?commissionWeapon:commissionArmour;
   const select=id=>{if(slot==='weapon')commissionWeapon=id;else commissionArmour=id;renderCommissions();controls();};
   choices.append(commissionChoice(slot==='weapon'?'No weapon':'No armour',!selected,()=>select(null)));
   c.gear.filter(id=>{const item=state.stock.find(x=>x.id===id);return (id==='shield'||item.category==='armour'?'armour':'weapon')===slot;}).forEach(id=>{
    const item=state.stock.find(x=>x.id===id),stored=state.warehouse[id];
    const button=commissionChoice('',id===selected,()=>select(id),stored<1);
    button.setAttribute('aria-label','Loan '+item.name);button.append(itemIcon(item),element('strong',item.name),iconStat('warehouse',stored,'In storage'),iconStat('shield','+2','Expedition bonus'));choices.append(button);
   });
  }
  $('#commissionRelic').replaceChildren(relicArt(region.id),iconStat('shield','+3','Expedition bonus'),element('small','×'+region.owned));$('#commissionRelic').classList.add('label-icon-button');$('#commissionRelic').setAttribute('aria-label','Lend '+region.relic+' · +3 · Owned: '+region.owned);
  $('#commissionRelicOptions').hidden=region.owned<1;$('#commissionRelicOptions').title=region.relic+' · Actions';
  $('#commissionRelic').setAttribute('aria-pressed',String(commissionRelic));$('#commissionRelic').dataset.unavailable=String(region.owned<1);$('#commissionRelic').disabled=busy||region.owned<1;
  $('#commissionRisks').replaceChildren(element('small','On failure:'),iconStat('gear',board.gear_loss_percent+'% each','Independent loss chance per loaned item'),iconStat('relic',board.relic_loss_percent+'%','Loaned relic loss chance'));
  updateCommissionTerms();
 }else{commissionPreviewVersion++;$('#dispatchCommission').dataset.unavailable='true';}
 const reports=$('#expeditionReports');reports.replaceChildren();
 if(!board.missions.length)reports.append(element('p','No expeditions commissioned.','muted'));
 board.missions.slice().reverse().forEach(m=>{
  const r=board.regions.find(r=>r.id===m.region_id),card=element('article',undefined,'expedition-report');
  card.dataset.missionId=m.id;const image=element('img',undefined,'report-thumbnail');image.src='assets/locations/'+r.id+'.png';image.alt='';card.append(image,element('strong',m.name+' · '+r.name+(m.deep?' · Depths':'')));
  if(m.status==='away'){const stats=element('div',undefined,'icon-stat-row');stats.append(iconStat('clock',Math.max(0,m.due_day-state.calendar.day)+' days','Time remaining'),iconStat('coin',m.fee,'Fee paid'));card.append(stats);}
  else{
   const result=element('div',undefined,'expedition-outcome '+(m.success?'success':'failure'));result.append(uiIcon(m.success?'check':'cross'),document.createTextNode(m.success?'Success':'Failed'));card.append(result);
   if(!m.success&&(m.collectible_items||[]).length)card.append(element('h4','Your equipment','storage-label'));
   const rewards=element('div',undefined,'report-rewards');
   (m.collectible_items||[]).forEach(drop=>{
    const view=element(drop.key==='relic'?'button':'div',undefined,'reward-stack');view.dataset.collectibleKey=drop.key;if(drop.quality)view.dataset.quality=drop.quality;if(drop.key==='relic'){view.type='button';view.setAttribute('aria-label',drop.name+' · Actions');view.onclick=()=>openRelicActions(r.id);}
    const art=element('img',undefined,'item-icon');art.src=drop.src;art.alt='';
    view.append(art,element('strong',drop.name),element('span','×'+drop.quantity));rewards.append(view);
   });card.append(rewards);
   (m.loaned_equipment||[]).filter(loan=>!loan.returned).forEach(loan=>{const item=state.stock.find(x=>x.id===loan.item_id),line=element('div',undefined,'loan-return-line failure');line.append(itemIcon(item),uiIcon('cross'),element('small',item.name));card.append(line);});
   if(m.status==='returned'){const collect=element('button',undefined,'primary label-icon-button');const label=m.success?'Collect':(m.collectible_items||[]).length?'Recover equipment':'Close report';collect.append(uiIcon(m.success?'chest':'check'),document.createTextNode(label));collect.setAttribute('aria-label',label);collect.title=label;collect.onclick=()=>act('claim_commission',{mission_id:m.id});card.append(collect);}
   else {const check=uiIcon('check');check.setAttribute('aria-label','Collected');card.append(check);}
  }reports.append(card);
 });

}
async function updateCommissionTerms(){
 const version=++commissionPreviewVersion;$('#commissionTerms').textContent='Planning the expedition…';$('#dispatchCommission').dataset.unavailable='true';$('#dispatchCommission').disabled=true;
 try{
  const p=await request({action:'commission_preview',customer_id:commissionAdventurer,region_id:commissionRegion,weapon:commissionWeapon,armour:commissionArmour,use_relic:commissionRelic,deep:commissionDeep});
  if(version!==commissionPreviewVersion||!$('#commissionDialog').open)return;
  const stats=element('div',undefined,'commission-stats');stats.append(iconStat('shield',p.success_percent+'%','Success chance'),iconStat('coin',p.fee,'Commission fee in gold'),iconStat('clock',p.days+' days','Time to return'),iconStat('chest',p.drop_slots,'Independent loot slots on success'));
  $('#commissionTerms').replaceChildren(stats);
  $('#dispatchCommission').replaceChildren(uiIcon('map'),document.createTextNode('Send'),uiIcon('arrow'));$('#dispatchCommission').classList.add('label-icon-button');$('#dispatchCommission').setAttribute('aria-label','Fund expedition');$('#dispatchCommission').title='Fund expedition · '+p.fee+' gold';
  $('#dispatchCommission').dataset.unavailable=String(!p.can_afford||state.daily.closed||state.commission_board.missions.filter(m=>m.status==='away').length>=3);controls();
 }catch(e){if(version===commissionPreviewVersion)$('#commissionTerms').textContent=e.message;}
}
$('#commissionsOpen').onclick=()=>{$('#commissionStatus').textContent='';$('#commissionDialog').showModal();renderCommissions();controls();};
$('#commissionsClose').onclick=()=>{$('#commissionDialog').close();commissionPreviewVersion++;};
$('#commissionRelic').onclick=()=>{commissionRelic=!commissionRelic;renderCommissions();controls();};
$('#dispatchCommission').onclick=()=>act('dispatch_commission',{customer_id:commissionAdventurer,region_id:commissionRegion,weapon:commissionWeapon,armour:commissionArmour,use_relic:commissionRelic,deep:commissionDeep});
if(state)renderCommissions();

function openRelicActions(id){relicActionRegion=id;$('#relicActionStatus').textContent='';renderRelicActions();$('#relicActionsDialog').showModal();controls();}
function renderRelicActions(){
 const r=state.commission_board.regions.find(r=>r.id===relicActionRegion);
 $('#relicInfoTitle').textContent=r.relic;$('#relicInfoArt').src='assets/relics/'+r.id+'.png';$('#relicInfoOwned').textContent='Owned: '+r.owned;
 $('#relicInfoUse').replaceChildren(iconStat('shield','+3','Lend on the matching route'),iconStat('map',r.name,'Matching destination'));
 const sell=$('#sellRelic');iconAction(sell,'coin','Sell 1 · '+r.sell_price+' gold',r.sell_price);sell.append(uiIcon('arrow'));sell.dataset.unavailable=String(r.owned<1||state.daily.closed);
 const unlock=$('#unlockRelicDepth');iconAction(unlock,r.deep_unlocked?'check':'lock',r.deep_unlocked?'Depths unlocked':'Spend 2 · unlock depths',r.deep_unlocked?null:'2');if(!r.deep_unlocked)unlock.append(uiIcon('arrow'),uiIcon('map'));unlock.dataset.unavailable=String(r.owned<2||r.deep_unlocked);
}
$('#commissionRelicOptions').onclick=()=>openRelicActions(commissionRegion);
$('#relicActionsClose').onclick=()=>$('#relicActionsDialog').close();
$('#sellRelic').onclick=()=>act('sell_relic',{region_id:relicActionRegion});
$('#unlockRelicDepth').onclick=()=>act('unlock_deep_route',{region_id:relicActionRegion});
