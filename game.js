const $=s=>document.querySelector(s);
let displayedGold=null;
let state=null,token='',busy=false,phase='idle',sound=true,audio=null,audioBus=null,previewTimer=null,previewVersion=0;
const customerArrivalAudio=$('#customerArrivalAudio'),buttonAudio=$('#buttonAudio');
const paymentPouchAudio=$('#paymentPouchAudio'),coinRattleAudio=$('#coinRattleAudio');
[paymentPouchAudio,coinRattleAudio,customerArrivalAudio,buttonAudio].forEach(clip=>{clip.preload='auto';clip.volume=.75;});
const actor=$('#actor');let waresOpen=false,journalOpen=false,journalCustomerId=null;
async function request(payload){const response=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Game-Token':token},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed.');return data;}
async function act(action,extra={}) {
  if(busy||phase==='arriving'||phase==='leaving')return;
  busy=true; $('#error').textContent='';if(action==='save')$('#saveStatus').textContent='Saving…'; controls();
  const previousRound=state?.deal?.round||0;
  const previousGold=state?.gold;
  const collection=action==='claim_commission'?captureInventoryFlight(extra.mission_id):null;
  const pouchOrigin=['collect_payment','collect_combat_rewards'].includes(action)?$(action==='collect_payment'?'#coinPouch':'#combatChest').getBoundingClientRect():null;
  const spoils=action==='collect_combat_rewards'?(state.combat.rewards.equipment||[]).map(g=>({...g,x:pouchOrigin.left+pouchOrigin.width/2,y:pouchOrigin.top+pouchOrigin.height/2})):null;
  if(sound)prepareAudio();
  try {
    let data=await request({action,...extra});
    if(action==='quote' && data.state.last_roll && data.state.deal.round>previousRound) {
      await animateD20(data.state.last_roll);
    }
    if(['steal_gear','beg_mercy'].includes(action)&&data.state.last_roll)await animateD20(data.state.last_roll);
    if(action==='beg_mercy'&&data.state.combat?.status==='ready'){state=data.state;try{data=await request({action:'fight'});}catch(e){render();throw e;}}
    if(action==='prepare_payment')playMoneyClip(paymentPouchAudio);
    else if(['collect_payment','collect_combat_rewards'].includes(action))playMoneyClip(coinRattleAudio);
    else if(Number.isFinite(previousGold)&&data.state.gold!==previousGold)coinSound();
    if(['collect_payment','collect_combat_rewards'].includes(action))displayedGold=previousGold;
    state=data.state;
    if(action==='arrive'){render();startArrival();}
    else if(action==='leave'){startDeparture();}
    else if((['skip_day','rest'].includes(action)||(action==='flee_combat'&&!data.state.customer))){phase='idle';actor.hidden=true;actor.className='actor';render();}
    else render();
    if(['collect_payment','collect_combat_rewards'].includes(action))await Promise.all([animatePayment(previousGold,state.gold,pouchOrigin),spoils?animateInventoryCollection(spoils):Promise.resolve()]);
    if(collection)await animateInventoryCollection(collection);
    if($('#relicActionsDialog').open&&['sell_relic','unlock_deep_route'].includes(action))$('#relicActionStatus').textContent=state.message;
    if($('#commissionDialog').open&&['dispatch_commission','claim_commission','sell_relic','unlock_deep_route'].includes(action))$('#commissionStatus').textContent=state.message;
    if(action==='buy_belonging'&&$('#equipmentDialog').open)$('#equipmentStatus').textContent=state.message;
    if(action==='repay_early')$('#repayStatus').textContent=state.message;$('#saveStatus').textContent=action==='save'?'Saved':'';if($('#warehouseDialog').open&&['place_stock','restock','return_stock'].includes(action))$('#warehouseStatus').textContent=state.message;
  } catch(e) { if(action==='repay_early')$('#repayStatus').textContent=e.message;if(action==='save')$('#saveStatus').textContent='Save failed';$('#error').textContent=e.message;if($('#equipmentDialog').open)$('#equipmentStatus').textContent=e.message;if($('#skillsDialog').open)$('#skillStatus').textContent=e.message;if($('#relicActionsDialog').open)$('#relicActionStatus').textContent=e.message;if($('#commissionDialog').open)$('#commissionStatus').textContent=e.message;if($('#warehouseDialog').open)$('#warehouseStatus').textContent=e.message;if(state?.caravan?.open)$('#marketMessage').textContent=e.message; }
  finally {displayedGold=null;if(state)$('#goldAmount').textContent=state.gold;busy=false;controls();if(typeof renderConfrontation==='function'&&state)renderConfrontation();if(typeof renderFinance==='function'&&state)renderFinance();if(['place_stock','restock'].includes(action))openRequestedTrade();}
}
async function animatePayment(from,to,origin){
 const target=$('#gold'),rect=target.getBoundingClientRect();
 const reduced=prefersReducedMotion();
 const coins=[];
 const duration=reduced?450:1200,delay=reduced?0:420;
 try{
  if(!reduced){
   for(let i=0;i<12;i++){
    const coin=element('span',undefined,'flying-coin');coin.setAttribute('aria-hidden','true');
    const x=origin.left+origin.width*.5+(i%3-1)*12,y=origin.top+origin.height*.4;
    coin.style.left=x+'px';coin.style.top=y+'px';document.body.append(coin);coins.push(coin);
    const dx=rect.left+rect.width*.55-x,dy=rect.top+rect.height*.5-y;
    coin.animate([{transform:'translate(-50%,-50%) scale(1)',opacity:0},{offset:.12,opacity:1},{offset:.45,transform:`translate(${dx*.35}px,${dy*.6-65}px) rotateY(180deg)`,opacity:1},{transform:`translate(${dx}px,${dy}px) scale(.4) rotateY(540deg)`,opacity:0}],{duration:650,delay:i*45,easing:'cubic-bezier(.35,0,.65,1)',fill:'both'});
   }
  }
  target.classList.add('receiving-gold');
  await new Promise(resolve=>{
   let start=null;
   function tick(now){
    start??=now;const progress=Math.min(1,Math.max(0,(now-start-delay)/(duration-delay)));
    displayedGold=Math.round(from+(to-from)*progress);$('#goldAmount').textContent=displayedGold;
    if(progress<1)requestAnimationFrame(tick);else resolve();
   }
   requestAnimationFrame(tick);
  });
 }finally{coins.forEach(coin=>coin.remove());target.classList.remove('receiving-gold');displayedGold=null;$('#goldAmount').textContent=to;}
}
function prefersReducedMotion(){return document.documentElement.dataset.motion==='reduced'||window.matchMedia('(prefers-reduced-motion: reduce)').matches;}
function soundDestination(){
 if(!audioBus){audioBus=audio.createGain();audioBus.connect(audio.destination);}
 audioBus.gain.value=typeof gameOptions==='object'?gameOptions.effectsVolume/100:.75;
 return audioBus;
}
function waitForAnimation(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
async function animateD20(result) {
  const dialog=$('#rollDialog'),die=$('#d20'),face=$('#dieFace');
  const reduced=prefersReducedMotion();
  $('#rollMath').textContent='D20 + '+result.attribute+' '+result.bonus+' · Difficulty '+result.difficulty;
  $('#rollOutcome').textContent='';
  dialog.showModal();
  if(typeof playDiceSound==='function')playDiceSound();
  let interval=null;
  try {
    if(!reduced){
      die.classList.add('rolling');let frame=0;
      interval=setInterval(()=>{face.textContent=String((frame++*7)%20+1);},65);
      await waitForAnimation(1250);
    }
    clearInterval(interval);interval=null;die.classList.remove('rolling');
    face.textContent=String(result.raw);
    die.classList.toggle('success',result.success);die.classList.toggle('failure',!result.success);
    $('#rollMath').textContent=result.raw+' + '+result.attribute+' '+result.bonus+' = '+result.total+' · Difficulty '+result.difficulty;
    $('#rollOutcome').textContent=result.success?'SUCCESS':'FAILED';
    await waitForAnimation(reduced?500:850);
  } finally {
    clearInterval(interval);if(typeof stopDiceSound==='function')stopDiceSound();die.classList.remove('rolling','success','failure');dialog.close();
  }
}
$('#rollDialog').addEventListener('cancel',e=>e.preventDefault());

function element(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function itemIcon(item,cls='item-icon'){
 const icon=element('img',undefined,cls);icon.src=item.gear?.signature_src||item.src||'assets/items/'+(item.base_id||item.id)+'.png';icon.alt='';icon.width=48;icon.height=48;icon.setAttribute('aria-hidden','true');return icon;
}
// All numeric choices share dragging and exact one-unit arrow controls.
function addNumberStepper(input,label,host=null){
 if(!host){host=element('div',undefined,'numeric-control');input.replaceWith(host);host.append(input);}
 host.classList.add('numeric-control');
 const readout=element('output',input.value,'numeric-value');readout.setAttribute('for',input.id);
 const arrows=element('div',undefined,'numeric-arrows');
 for(const [delta,glyph] of [[1,'▲'],[-1,'▼']]){
  const button=element('button',glyph);button.type='button';button.dataset.delta=String(delta);
  button.setAttribute('aria-label',(delta>0?'Increase ':'Decrease ')+label+' by 1');
  button.title=delta>0?'+1':'−1';
  button.onclick=()=>{
   if(input.disabled)return;
   const lower=Number(input.min),upper=Number(input.max),next=Number(input.value)+delta;
   if(next>upper&&input.dataset.expand==='true'&&upper<99999)input.max=String(Math.min(99999,Math.max(next,Math.ceil(upper*1.25))));
   input.value=String(Math.max(lower,Math.min(Number(input.max),next)));
   input.dispatchEvent(new Event('input',{bubbles:true}));
  };arrows.append(button);
 }
 host.append(readout,arrows);host.dataset.numberInput=input.id;
 input.addEventListener('input',refreshNumberControls);
}
function refreshNumberControls(){
 document.querySelectorAll('[data-number-input]').forEach(host=>{
  const input=document.getElementById(host.dataset.numberInput);if(!input)return;
  host.querySelector('output').value=input.value;
  host.querySelectorAll('[data-delta]').forEach(button=>{
   const boundary=Number(button.dataset.delta)<0?Number(input.value)<=Number(input.min):Number(input.value)>=Number(input.max)&&!(input.dataset.expand==='true'&&Number(input.max)<99999);
   button.disabled=input.disabled||boundary;
  });
 });
}
function controls(){$('#commissionsOpen').disabled=busy||!state||phase==='arriving'||phase==='leaving';$('#visitCaravan').hidden=!state||state.calendar.weekday!=='Monday'||state.caravan.open;$('#visitCaravan').disabled=busy||!!state?.customer||!!state?.daily.closed||phase==='arriving'||phase==='leaving';$('#saveGame').disabled=busy||!state||phase==='arriving'||phase==='leaving';$('#skillsOpen').disabled=busy||phase==='arriving'||phase==='leaving';$('#menuOpen').disabled=busy||phase==='arriving'||phase==='leaving';syncJournal();const c=state?.customer,payment=state?.deal?.status==='payment';$('#coinPouch').disabled=busy;$('#enter').disabled=busy||phase!=='idle'||!!c||!!state?.daily?.closed||!!state?.caravan?.open;$('#nextDay').disabled=busy;$('#skipDay').disabled=busy||phase==='arriving'||phase==='leaving'||!!state?.daily?.closed||payment;$('#warehouseOpen').disabled=busy||phase==='arriving'||phase==='leaving';$('#leave').disabled=busy||phase!=='present'||!c||payment;$('#skip').disabled=phase!=='arriving';document.querySelectorAll('.shop button,.shop input,#deal button,#deal input,.clues button,#warehouseDialog button,#warehouseDialog input,#warehouseDialog select,#marketScene button,#marketScene input,#commissionDialog button,#relicActionsDialog button,#skillsDialog button').forEach(e=>{e.disabled=busy||phase==='arriving'||phase==='leaving'||e.dataset.unavailable==='true';});if(c)document.querySelectorAll('.price-form input,.price-form button').forEach(e=>e.disabled=true);refreshNumberControls();}
function playMoneyClip(clip){
 if(!sound)return;
 [paymentPouchAudio,coinRattleAudio].forEach(other=>{other.pause();other.currentTime=0;});
 clip.play().catch(()=>{});
}
// Unlock audio during the button press, before waiting for the transaction.
function prepareAudio(){
 if(!sound)return null;
 try{audio??=new(window.AudioContext||window.webkitAudioContext)();audio.resume().catch(()=>{});return audio;}catch(e){return null;}
}
function coinSound(){
 const context=prepareAudio();if(!context)return;
 // A short cascade of metallic coin impacts, with inharmonic overtones.
 const start=context.currentTime+.015;
 [0,.075,.155,.25].forEach((delay,index)=>{
  const frequency=[2350,2860,2140,3190][index];
  [1,1.47,2.09].forEach((ratio,partial)=>{
   const tone=context.createOscillator(),gain=context.createGain(),at=start+delay;
   tone.type='sine';tone.frequency.setValueAtTime(frequency*ratio,at);
   tone.frequency.exponentialRampToValueAtTime(frequency*ratio*.97,at+.13);
   gain.gain.setValueAtTime(.0001,at);
   gain.gain.exponentialRampToValueAtTime(.045/(partial+1),at+.003);
   gain.gain.exponentialRampToValueAtTime(.0001,at+.19);
   tone.connect(gain);gain.connect(soundDestination());
   tone.onended=()=>{tone.disconnect();gain.disconnect();};
   tone.start(at);tone.stop(at+.21);
  });
 });
}
function bell(){if(!sound)return;try{audio??=new(window.AudioContext||window.webkitAudioContext)();audio.resume().catch(()=>{});[880,1320,1760].forEach((f,i)=>{const o=audio.createOscillator(),g=audio.createGain();o.frequency.value=f;g.gain.setValueAtTime(.035/(i+1),audio.currentTime);g.gain.exponentialRampToValueAtTime(.0001,audio.currentTime+.6);o.connect(g);g.connect(soundDestination());o.start();o.stop(audio.currentTime+.65);});}catch(e){}}
function startArrival(){phase='arriving';$('#notes').hidden=true;$('#visitorTag').hidden=true;$('#deal').hidden=true;$('#speech').textContent='The door creaks open…';$('#speaker').textContent='AT THE DOOR';actor.hidden=true;actor.className='actor';const ready=()=>{if(phase!=='arriving')return;actor.hidden=false;actor.className='actor arriving';controls();};actor.onload=ready;actor.onerror=()=>{finishArrival();$('#error').textContent='Portrait could not load. Check local assets.';};actor.src='assets/characters/'+state.customer.portrait;}
async function openRequestedTrade(){
 const c=state?.customer;if(!c||state.deal||state.combat||c.trade_blocked||phase!=='present')return;
 const item=state.stock.find(x=>x.id===c.wants);if(item&&state.shelves.includes(item.id)&&item.quantity>0&&!c.refused?.includes(item.id))await act('begin',{item_id:item.id});
}
function finishArrival(){if(phase!=='arriving')return;phase='present';actor.onload=null;actor.hidden=false;actor.className='actor present';render();controls();openRequestedTrade();}
function startDeparture(){phase='leaving';$('#deal').hidden=true;$('#notes').hidden=true;$('#visitorTag').hidden=true;$('#speech').textContent=state.message;actor.className='actor leaving';controls();}
function finishDeparture(){if(phase!=='leaving')return;phase='idle';actor.hidden=true;actor.className='actor';render();controls();}
actor.addEventListener('animationend',e=>{if(e.animationName==='approach')finishArrival();if(e.animationName==='depart')finishDeparture();});
function syncJournal(){
 const customerId=state?.customer?.id||null;
 if(customerId!==journalCustomerId){journalOpen=false;journalCustomerId=customerId;}
 const available=!!customerId&&phase==='present';
 $('#journalToggle').disabled=!available;
 $('#journalPanel').hidden=!available||!journalOpen;
 $('#journalToggle').setAttribute('aria-expanded',String(available&&journalOpen));
 $('#journalToggle').setAttribute('aria-label',journalOpen?'Close customer journal':'Open customer journal');
}
$('#journalToggle').onclick=()=>{journalOpen=!journalOpen;syncJournal();};
$('#journalClose').onclick=()=>{journalOpen=false;syncJournal();$('#journalToggle').focus();};
$('#journalPanel').addEventListener('keydown',e=>{if(e.key==='Escape'){journalOpen=false;syncJournal();$('#journalToggle').focus();}});
function journal(){const c=state.customer,host=$('#journal');if(!c)return;$('#journalName').textContent=c.name.toUpperCase()+' · JOURNAL';const list=element('dl');const wants=state.stock.find(x=>x.id===c.wants);const rows=[['Basic information',c.name+' · '+c.race+' · '+c.profession],['Worn / carried',c.equipment+'. Armour: '+c.armour+'. Accessories: '+c.accessories],['Wants to buy',wants?.name||'Nothing suitable on the shelves'],['Purchased',c.purchases.map(p=>`${p.item} · ${p.price} gold (visit ${p.visit})`)],['My actions',c.actions]];for(const [label,value]of rows){list.append(element('dt',label));const dd=element('dd');if(Array.isArray(value)&&value.length){const ul=element('ul');value.forEach(t=>ul.append(element('li',t)));dd.append(ul);}else dd.textContent=Array.isArray(value)?'None recorded.':value;list.append(dd);}host.replaceChildren(list);}
function shelves(){
 const host=$('#stock');host.replaceChildren();
 state.shelves.forEach((id,slot)=>{
  const box=element('div',undefined,'stock-item');box.append(element('small','SHELF '+(slot+1)));
  const item=state.stock.find(x=>x.id===id);
  if(item&&item.quantity>0){
   box.append(itemIcon(item),element('strong',item.name),element('span',item.mode==='fixed'?'Marked price':'Bargain','mode'));const info=element('div',undefined,'inventory-metrics');info.append(iconStat('coin',item.price,'Sale price'),iconStat('warehouse',item.quantity,'Stock on shelf'));box.append(info);
   const choose=element('button',state.customer?.wants===item.id?'Show requested item':'Recommend item');
   choose.dataset.unavailable=String(!state.customer||item.quantity===0||['negotiating','agreed','payment'].includes(state.deal?.status));choose.disabled=choose.dataset.unavailable==='true';choose.onclick=()=>act('begin',{item_id:item.id});choose.hidden=!state.customer;box.append(choose);
  }else box.append(element('strong','Empty'));
  box.dataset.quality=item?.quality||'common';const manage=element('button','Manage shelf');manage.onclick=()=>openWarehouse(slot);box.append(manage);host.append(box);
 });
}

function showMargin(selector,price,cost,projected=true){
 const target=$(selector),valid=Number.isInteger(price)&&price>0,margin=Math.round((price-cost)*100)/100;
 target.textContent=!valid?'—':(projected?'Expected ':'')+(margin>0?'Profit: +'+margin:margin<0?'Loss: −'+Math.abs(margin):'Break-even: 0')+' gold';
 target.className='margin '+(!valid?'':margin>0?'profit':margin<0?'loss':'break-even');
}
function negotiation(){
 const d=state.deal,c=state.customer,host=$('#deal');const payment=!!c&&d?.status==='payment';$('#coinPouch').hidden=!payment||phase!=='present';$('#pouchAmount').textContent=payment?'Collect '+d.agreed+' gold':'';host.hidden=!c||payment||phase==='arriving'||phase==='leaving';if(!c||payment)return;
 const item=state.stock.find(x=>x.id===(d?.item_id||c.wants));
 $('#tradeMargin').hidden=true;
 if(!item){host.classList.remove('expanded');$('#dealTitle').textContent='No suitable item';$('#itemCost').textContent='';$('#offer').textContent='Nothing on the shelves matches this customer’s needs.';$('#quoteForm').hidden=true;$('#accept').hidden=true;$('#cancel').hidden=true;$('#dice').textContent='';return;}
 const fixed=item.mode==='fixed',active=d&&['negotiating','agreed'].includes(d.status);
 host.classList.toggle('expanded',!!d&&!fixed&&active);
 $('#dealTitle').replaceChildren(itemIcon(item),document.createTextNode(item.name));
 $('#itemCost').textContent='Cost: '+item.cost+' gold · '+(fixed?'Marked price: '+item.price+' gold':'Bargain');
 $('#offer').textContent=!d?'Not on the shelf.':d.status==='sold'?'Sold for '+d.agreed+' gold':d.status==='declined'?'No sale.':fixed?(d.sale_allowed===false?'The customer will not pay this price.':'Sell for '+d.agreed+' gold?'):d.status==='agreed'?'Agreed: '+d.agreed+' gold':'Customer offers '+d.offer+' gold';
 $('#quoteForm').hidden=!d||d.status!=='negotiating'||fixed;
 if(d&&['agreed','sold'].includes(d.status)){$('#tradeMargin').hidden=false;showMargin('#tradeMargin',d.agreed,item.cost,d.status!=='sold');}
 $('#accept').hidden=!active;$('#cancel').hidden=!active;
 const amount=d?.status==='agreed'?d.agreed:d?.offer;iconAction($('#accept'),'coin',(fixed?'Sell':d?.status==='agreed'?'Confirm sale':'Accept offer')+' · '+amount+' gold',amount,true);
 $('#accept').dataset.unavailable=String(d?.sale_allowed===false);
 iconAction($('#cancel'),'cross',fixed?"Don't sell":'End negotiation');$('#cancel').classList.add('decline-action');
 if(d?.status==='negotiating'&&!fixed){$('#quote').value=d.last_quote||Math.max(d.offer+1,item.price);setupPriceBar(item,d);updatePreview();}
 const r=state.last_roll;$('#dice').replaceChildren();if(r&&!fixed){$('#dice').append(uiIcon('d20'),document.createTextNode(`${r.raw} + ${r.bonus} = ${r.total} / ${r.difficulty}`),uiIcon(r.success?'check':'cross'));$('#dice').setAttribute('aria-label',`D20 ${r.raw} + ${r.attribute} ${r.bonus} = ${r.total}; difficulty ${r.difficulty}; ${r.success?'success':'failed'}`);$('#dice').title=$('#dice').getAttribute('aria-label');}
}

function setupPriceBar(item,deal) {
  const slider=$('#priceSlider');
  slider.min='1';
  slider.max=String(deal.quote_cap??item.price_caps.bargain);slider.dataset.expand='false';$('#quote').value=String(Math.min(Number($('#quote').value),Number(slider.max)));
  slider.value=$('#quote').value;
  $('#customerPrice').textContent=deal.offer+' gold';
  drawPriceBar();
}
function drawPriceBar() {
  const slider=$('#priceSlider'),price=Math.min(Number($('#quote').value),Number(slider.max));$('#quote').value=String(price);
  if(!state?.deal)return;
  const item=state.stock.find(x=>x.id===state.deal.item_id);
  showMargin('#customerMargin',state.deal.offer,item.cost);
  showMargin('#merchantMargin',price,item.cost);
  if(!Number.isInteger(price)||price<1)return;

  slider.value=String(price);
  const min=Number(slider.min),max=Number(slider.max);
  const position=v=>Math.max(0,Math.min(1000,(v-min)/(max-min)*1000));
  const customer=position(state.deal.offer),merchant=position(price);
  $('#customerMarker').setAttribute('transform','translate('+customer+' 0)');
  $('#priceGap').setAttribute('d','M'+customer+' 40H'+merchant);
  $('#merchantPrice').textContent=price+' gold';
  $('#priceMin').textContent=min+' gold';$('#priceMax').textContent=max+' gold';
  slider.setAttribute('aria-valuetext',price+' gold; customer offers '+state.deal.offer+' gold');refreshNumberControls();
}

function render(){if(typeof renderSkills==='function')renderSkills();if(typeof renderCommissions==='function')renderCommissions();renderCalendar();renderMarket();if($('#warehouseDialog').open)renderWarehouse();const c=state.customer;$('#wantedTag').hidden=!c?.wanted;$('#attackWanted').hidden=!c?.wanted||!!c?.defeated;$('#goldAmount').textContent=(displayedGold??state.gold);$('#skill').textContent='Eloquence: +'+state.player.eloquence;$('#speech').textContent=state.message;$('#speaker').textContent=c?(c.known.includes(state.message)?"A MERCHANT'S EYE":c.name.toUpperCase()):'THE SHOP IS QUIET';$('#notes').hidden=!c;$('#visitorTag').hidden=!c;if(c){$('#visitorName').textContent=c.name+' · '+c.profession+(c.visits>1?' · Returning customer':'');$('#mood').textContent='Mood: '+c.mood;$('#mood').dataset.mood=c.mood.toLowerCase();$('#description').textContent=c.final_boss?'The man who ruined my family has come to finish his work.':`A ${c.race.toLowerCase()} ${c.profession.toLowerCase()} carrying ${c.equipment} stands before me.`;$('#detail').textContent=c.known.at(-1)||'';if(phase!=='arriving'&&phase!=='leaving'){phase='present';actor.onload=null;actor.src='assets/characters/'+c.portrait;actor.alt=c.race+' customer carrying '+c.equipment;actor.hidden=false;actor.className='actor present';}journal();}shelves();negotiation();controls();renderDaySummary();if(typeof renderEquipment==='function')renderEquipment();if(typeof renderFinance==='function')renderFinance();}
function renderMarket(){
 const open=state.caravan.open;$('#marketScene').hidden=!open;$('#shopScene').hidden=open;$('.controls').hidden=open;
 $('#marketDate').textContent=formatDate(state.calendar);$('#wares').hidden=!waresOpen;
 if(!open){waresOpen=false;return;}
 actor.hidden=true;phase='idle';
 const host=$('#merchantStock');host.replaceChildren();
 state.caravan.stock.forEach(listing=>{
  const item=state.stock.find(x=>x.id===listing.item_id),card=element('form',undefined,'merchant-item');card.dataset.quality='common';
  card.append(itemIcon(item),element('strong',item.name),element('span','Marked price · '+listing.price+' gold'),element('small','Available: '+listing.quantity));
  const q=element('input');q.type='range';q.id='buyQuantity-'+item.id;q.min='1';q.max=String(Math.max(1,listing.quantity));q.value='1';q.step='1';q.required=true;q.setAttribute('aria-label',item.name+' purchase quantity');
  const buy=element('button','Buy');buy.type='submit';buy.dataset.unavailable=String(listing.quantity===0);card.append(q,buy);addNumberStepper(q,item.name+' purchase quantity');
  card.onsubmit=e=>{e.preventDefault();act('merchant_buy',{item_id:item.id,quantity:Number(q.value)});};host.append(card);
 });
 $('#marketMessage').textContent='';renderPurchaseFeed();
}
function renderPurchaseFeed(){
 const feed=$('#purchaseFeed'),list=$('#purchaseRecords'),records=state.caravan.purchases||[];
 feed.hidden=records.length===0;
 const existing=list.children.length,previousLast=list.lastElementChild?.dataset.receiptId;
 const reset=list.dataset.day!==String(state.caravan.day)||existing>records.length||(existing>0&&records[existing-1]?.id!==previousLast);
 const oldPositions=new Map(Array.from(list.children).slice(-8).map(row=>[row.dataset.receiptId,row.getBoundingClientRect().top]));
 if(reset)list.replaceChildren();list.dataset.day=String(state.caravan.day);
 const start=list.children.length;if(start===records.length)return;
 records.slice(start).forEach(receipt=>{
  const item=state.stock.find(x=>x.id===receipt.item_id),row=element('li',undefined,'purchase-receipt');row.dataset.receiptId=receipt.id;
  row.setAttribute('aria-label','Bought '+receipt.quantity+' '+item.name+' for '+receipt.total+' gold');
  const description=element('div',undefined,'purchase-description');description.append(element('strong',item.name),element('small','×'+receipt.quantity));
  row.append(itemIcon(item),description,element('span','−'+receipt.total,'purchase-total'),uiIcon('coin'));list.append(row);
 });
 list.scrollTop=list.scrollHeight;
 if(!reset&&previousLast&&!prefersReducedMotion()){
  Array.from(list.children).forEach(row=>{const oldTop=oldPositions.get(row.dataset.receiptId);if(oldTop!==undefined){const shift=oldTop-row.getBoundingClientRect().top;if(shift)row.animate([{transform:'translateY('+shift+'px)'},{transform:'translateY(0)'}],{duration:220,easing:'ease-out'});}});
  list.lastElementChild.animate([{opacity:0,transform:'translateY(12px)'},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'ease-out'});
 }
}
let warehouseSlot=0,warehouseItem=null,warehouseMode=null;
function renderWarehouse(){
 const slots=$('#warehouseSlots');slots.replaceChildren();
 state.shelves.forEach((id,i)=>{
  const item=state.stock.find(x=>x.id===id),button=element('button',undefined,'shelf-choice');button.type='button';
  button.setAttribute('aria-pressed',String(i===warehouseSlot));button.setAttribute('aria-label','Shelf '+(i+1)+(item?' · '+item.name:' · Empty'));
  button.append(element('small','Shelf '+(i+1)));
  if(item)button.append(itemIcon(item),element('strong',item.name),element('span',item.quantity+' on shelf'));
  else button.append(element('strong','Empty'));
  button.onclick=()=>{warehouseSlot=i;renderWarehouse();controls();};slots.append(button);
 });
 const host=$('#warehouseList');host.replaceChildren();
 state.stock.filter(item=>!item.base_id||item.quantity>0||state.warehouse[item.id]>0).forEach(item=>{
  const row=element('button',undefined,'warehouse-item');row.type='button';row.dataset.quality=item.quality||'common';
  row.setAttribute('aria-label',item.name);row.setAttribute('aria-pressed',String(item.id===warehouseItem));
  row.append(itemIcon(item),element('strong',item.name));const metrics=element('div',undefined,'inventory-metrics');metrics.append(iconStat('warehouse',state.warehouse[item.id],'Stored in warehouse'),iconStat('coin',item.cost,'Your purchase cost'));row.append(metrics);
  row.onclick=()=>{
   warehouseItem=item.id;
   const existing=state.shelves.indexOf(item.id);if(existing>=0)warehouseSlot=existing;
   restoreShelfSettings(item);
   renderWarehouse();controls();$('#shelfForm').scrollIntoView({block:'nearest',behavior:prefersReducedMotion()?'instant':'smooth'});
  };host.append(row);
 });
 const item=state.stock.find(x=>x.id===warehouseItem),form=$('#shelfForm');form.hidden=!item;
 $('#clearShelf').disabled=busy||!state.shelves[warehouseSlot];$('#clearShelf').dataset.unavailable=String(!state.shelves[warehouseSlot]);
 $('#selectedWear').replaceChildren();
 if(!item)return;
 if(item.category==='consumable'){const drink=element('button','Drink · +40 HP');drink.disabled=state.equipment.stats.hp<=0||state.equipment.stats.hp>=state.equipment.stats.max_hp||!(state.warehouse[item.id]>0);drink.dataset.unavailable=String(drink.disabled);drink.onclick=()=>act('drink_potion');$('#selectedWear').append(drink);}
 if(item.wear&&typeof equipmentCard==='function'){$('#selectedWear').append(equipmentCard({...item.wear,stock_id:item.id},'stock'));}
 const selected=$('#selectedWare');selected.replaceChildren(itemIcon(item),element('strong',item.name),element('span','Cost: '+item.cost+' gold · Stored: '+state.warehouse[item.id]+' · Shelf '+(warehouseSlot+1)));
 if(item.cost===0)selected.append(element('span','Value: '+item.pricing_reference+' gold'));
 $('#warehouseQuantity').max=String(item.base_id?1:state.units_per_shelf);
 $('#modeBargain').setAttribute('aria-pressed',String(warehouseMode==='bargain'));
 $('#modeFixed').setAttribute('aria-pressed',String(warehouseMode==='fixed'));
 $('#shelfPricing').hidden=!warehouseMode;
 $('#restockShelf').hidden=state.shelves[warehouseSlot]!==item.id;
 updateShelfMargin();
}
function updateShelfMargin(){const item=state?.stock.find(x=>x.id===warehouseItem);if(item){const input=$('#warehousePrice');input.dataset.expand='false';input.max=String(item.price_caps[warehouseMode||item.mode]);input.value=String(Math.min(Number(input.value),Number(input.max)));if(warehouseMode)showMargin('#shelfMargin',Number(input.value),item.cost);}refreshNumberControls();}
function restoreShelfSettings(item){
 const saved=state.shelf_settings?.[item.id];warehouseMode=saved?.mode||null;
 $('#warehouseQuantity').value=String(saved?.quantity||1);
 const price=saved?.price||item.price;$('#warehousePrice').max=String(item.price_caps[warehouseMode||item.mode]);$('#warehousePrice').value=Math.min(price,Number($('#warehousePrice').max));
}
function openWarehouse(slot){
 warehouseSlot=Number.isInteger(slot)?slot:0;warehouseItem=Number.isInteger(slot)?state.shelves[slot]:null;warehouseMode=null;
 $('#warehouseStatus').textContent='';$('#warehouseQuantity').value='1';
 if(warehouseItem)restoreShelfSettings(state.stock.find(x=>x.id===warehouseItem));
 renderWarehouse();$('#warehouseDialog').showModal();if(typeof renderEquipment==='function')renderEquipment();controls();
}
$('#warehouseOpen').onclick=()=>openWarehouse();$('#warehouseClose').onclick=()=>$('#warehouseDialog').close();
function selectSaleMode(mode){warehouseMode=mode;renderWarehouse();controls();$('#shelfPricing').scrollIntoView({block:'nearest',behavior:prefersReducedMotion()?'instant':'smooth'});}
$('#modeBargain').onclick=()=>selectSaleMode('bargain');$('#modeFixed').onclick=()=>selectSaleMode('fixed');
$('#warehousePrice').oninput=updateShelfMargin;
$('#shelfForm').onsubmit=e=>{e.preventDefault();if(!warehouseItem||!warehouseMode)return;act('place_stock',{slot:warehouseSlot,item_id:warehouseItem,quantity:Number($('#warehouseQuantity').value),mode:warehouseMode,price:Number($('#warehousePrice').value)});};
$('#restockShelf').onclick=()=>act('restock',{slot:warehouseSlot,quantity:Number($('#warehouseQuantity').value)});
$('#clearShelf').onclick=()=>act('return_stock',{slot:warehouseSlot});
$('#wagon').onclick=()=>{waresOpen=true;renderMarket();if(typeof renderEquipment==='function')renderEquipment();controls();};$('#finishMarket').onclick=()=>act('finish_market');

function formatDate(date){return 'Year '+date.year+' · Week '+date.week+' · '+date.weekday;}
function renderCalendar(){
  $('#date').textContent=formatDate(state.calendar);
  $('#customersToday').textContent=state.customer?.final_boss?'Final duel':'Customers: '+state.daily.served+' / 10'+(state.customer?' · serving #'+state.daily.admitted:'');
  $('#revenueToday').textContent="Today's revenue: "+state.daily.revenue+' gold';
  const loan=state.loan;
  $('#loanLabel').textContent=loan.paid_off?'Loan repaid':'Loan: '+loan.balance.toLocaleString()+' gold';
  const host=$('#loanDetails');host.replaceChildren();
  host.append(element('p','Weekly rent: '+state.rent.weekly+' gold'),element('p','Next rent: '+state.calendar.days_until_rent+' days'));
  if(state.rent.arrears)host.append(element('p','Rent overdue: '+state.rent.arrears+' gold','arrears'));
  if(loan.paid_off){host.append(element('p','Debt-free.'));return;}
  host.append(element('p','Monthly repayment: '+Math.min(loan.balance,loan.principal_per_month+loan.principal_arrears).toLocaleString()+' gold'),element('p','Next repayment: '+state.calendar.days_until_payment+' days'));
  if(loan.principal_arrears)host.append(element('p','Debt overdue: '+loan.principal_arrears.toLocaleString()+' gold','arrears'));

}
function renderDaySummary(){
  const dialog=$('#dayDialog'),summary=state.day_summary;
  if(state.combat?.final_boss&&state.combat.status==='active'){if(dialog.open)dialog.close();return;}
  if(!state.daily.closed||!summary){if(dialog.open)dialog.close();return;}
  $('#dayDate').textContent=formatDate(summary.date);
  $('#dayRevenue').textContent=summary.revenue+' gold';
  $('#dayTotals').textContent=summary.customers+' customers · '+summary.sales+' item(s) sold';
  $('#dayCash').textContent='Cash remaining: '+summary.closing_gold+' gold';
  const host=$('#monthPayment');host.replaceChildren();host.hidden=!summary.loan_payment&&!summary.rent_payment;
  if(summary.rent_payment){const r=summary.rent_payment;host.append(element('h3','WEEKLY RENT'),element('p','Paid: '+r.paid+' gold'));if(r.shortfall)host.append(element('p','Overdue: '+r.shortfall+' gold','arrears'));}
  if(summary.loan_payment){
    const p=summary.loan_payment;host.append(element('h3','MONTH-END PAYMENT'),element('p','Repaid: '+p.paid.toLocaleString()+' gold'),element('p','Debt remaining: '+p.balance.toLocaleString()+' gold'));
    if(p.shortfall)host.append(element('p','Unpaid amount carried forward: '+p.shortfall+' gold','arrears'));
    if(p.paid_off)host.append(element('strong','LOAN REPAID · You are debt-free.'));
  }
  if(!dialog.open)dialog.showModal();
}
$('#nextDay').onclick=()=>act('next_day');
$('#skipDay').onclick=()=>act('skip_day');
$('#dayDialog').addEventListener('cancel',e=>e.preventDefault());

function updatePreview(){clearTimeout(previewTimer);const version=++previewVersion;$('#preview').textContent='…';previewTimer=setTimeout(async()=>{const price=Number($('#quote').value);if(!Number.isInteger(price)||price<1){$('#preview').textContent='Enter a positive whole-number price.';return;}if(state.deal?.status!=='negotiating')return;if(price<=state.deal.offer){$('#preview').textContent='Agreed';$('#preview').dataset.risk='low';iconAction($('#roll'),'check','Offer price · No roll needed');return;}iconAction($('#roll'),'d20','Roll D20');try{const r=await request({action:'preview',price});if(version===previewVersion){const stats=element('span',undefined,'preview-stats');stats.append(iconStat('shield',r.success_percent+'%','Success chance'),iconStat('clock',r.remaining_patience,'Remaining patience'));if(r.insight_bonus)stats.append(iconStat('star','+'+r.insight_bonus,'Observation bonus'));const consequence=element('span','If rejected: '+(r.walkaway_on_failure?'customer walks away':r.failure_mood),'preview-consequence');$('#preview').replaceChildren(stats,consequence);$('#preview').dataset.risk=r.walkaway_on_failure?'high':r.success_percent<50?'medium':'low';}}catch(e){if(version===previewVersion)$('#preview').textContent=e.message;}},180);}
$('#enter').onclick=()=>act('arrive');$('#skip').onclick=finishArrival;$('#leave').onclick=()=>act('leave');$('#accept').onclick=()=>act('prepare_payment');$('#coinPouch').onclick=()=>act('collect_payment');$('#cancel').onclick=()=>act('cancel');$('#quoteForm').onsubmit=e=>{e.preventDefault();act('quote',{price:Number($('#quote').value)});};$('#quote').oninput=()=>{drawPriceBar();updatePreview();};$('#priceSlider').oninput=e=>{if(quoteDragging)playQuoteTick();$('#quote').value=e.target.value;drawPriceBar();updatePreview();};document.querySelectorAll('[data-clue]').forEach(b=>b.onclick=()=>act('inspect',{clue:b.dataset.clue}));$('#sound').onclick=()=>setGameOption('sound',!sound);
addNumberStepper($('#warehouseQuantity'),'quantity');
addNumberStepper($('#warehousePrice'),'shelf price');
$('#priceSlider').dataset.expand='false';addNumberStepper($('#priceSlider'),'selling price',$('#quoteStepper'));
for(const [id,icon] of [['menuOpen','scroll'],['saveGame','scroll'],['visitCaravan','warehouse'],['warehouseOpen','warehouse'],['skipDay','clock'],['enter','hand'],['leave','arrow']]){const button=$('#'+id),label=button.textContent;button.replaceChildren(uiIcon(icon),document.createTextNode(label));button.classList.add('label-icon-button');}
iconAction($('#roll'),'d20','Roll D20');
$('#saveGame').onclick=()=>act('save');
$('#visitCaravan').onclick=()=>act('visit_caravan');
async function boot(){try{const response=await fetch('/api/state');if(!response.ok)throw new Error('The local Python server is unavailable.');const data=await response.json();token=data.token;state=data.state;$('#saveStatus').textContent='';render();window.dispatchEvent(new Event('merchant-ready'));}catch(e){$('#error').textContent=e.message+' Start the game with python main.py.';$('#enter').disabled=true;}}
boot();

// Capture clicks before handlers disable or replace dynamically rendered buttons.
document.addEventListener('click',event=>{
 const button=event.target.closest('button');
 if(!button||button.disabled||!sound)return;
 const clip=button.id==='enter'?customerArrivalAudio:buttonAudio;
 clip.currentTime=0;clip.play().catch(()=>{});
},true);

// Short ratchet ticks follow dragging without retriggering the button recording.
let quoteDragging=false,lastQuoteTick=-Infinity,quoteNoise=null;
$('#priceSlider').addEventListener('pointerdown',()=>{quoteDragging=true;lastQuoteTick=-Infinity;});
for(const type of ['pointerup','pointercancel'])document.addEventListener(type,()=>{quoteDragging=false;});
window.addEventListener('blur',()=>{quoteDragging=false;});
function playQuoteTick(){
 if(!sound||performance.now()-lastQuoteTick<55)return;
 const context=prepareAudio();if(!context)return;lastQuoteTick=performance.now();
 if(!quoteNoise){quoteNoise=context.createBuffer(1,Math.ceil(context.sampleRate*.018),context.sampleRate);const samples=quoteNoise.getChannelData(0);for(let i=0;i<samples.length;i++)samples[i]=(Math.random()*2-1)*(1-i/samples.length);}
 const source=context.createBufferSource(),filter=context.createBiquadFilter(),gain=context.createGain();source.buffer=quoteNoise;filter.type='bandpass';filter.frequency.value=1600;filter.Q.value=.8;
 gain.gain.setValueAtTime(.13,context.currentTime);gain.gain.exponentialRampToValueAtTime(.001,context.currentTime+.018);
 source.connect(filter);filter.connect(gain);gain.connect(soundDestination());source.start();source.onended=()=>{source.disconnect();filter.disconnect();gain.disconnect();};
}
