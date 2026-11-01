// Voluntary repayments and the final campaign ending.
addNumberStepper($('#repayAmount'),'repayment amount');
function updateRepayment(){
 const amount=Number($('#repayAmount').value);
 $('#repayRemaining').textContent='Debt remaining: '+Math.max(0,state.loan.balance+state.loan.interest_arrears-amount).toLocaleString()+' gold';
 refreshNumberControls();
}
function renderFinance(){
 if(!state)return;
 const finale=state.final_boss;
 $('#finalDuel').hidden=!finale||finale.status!=='waiting';
 if(finale?.status==='waiting'&&!finale.introduced&&state.equipment.stats.hp>0&&!busy&&!$('#titleScreen').open)showBossEncounter();
 if((finale?.status!=='waiting'||state.equipment.stats.hp<=0)&&$('#bossDialog').open)$('#bossDialog').close();
 const available=Math.min(state.gold,state.loan.balance+state.loan.interest_arrears);
 if($('#repayDialog').open){
  $('#repayBalance').textContent='Debt: '+state.loan.balance.toLocaleString()+' gold · Gold: '+state.gold.toLocaleString();
  $('#repayAmount').max=String(Math.max(1,available));$('#repayAmount').value=String(Math.max(1,Math.min(Number($('#repayAmount').value),available)));
  updateRepayment();
 }
 if(state.ending&&!busy&&!$('#titleScreen').open){
  const ending=state.ending;
  $('#victoryStats').replaceChildren(element('strong',ending.repaid.toLocaleString()+' gold repaid'),element('span','Day '+ending.day+' · '+ending.visits+' customers'),element('span',ending.gold.toLocaleString()+' gold remaining'));
  document.querySelectorAll('dialog[open]').forEach(d=>{if(d.id!=='victoryDialog')d.close();});
  if(!$('#victoryDialog').open)$('#victoryDialog').showModal();
 }else if(!state.ending&&$('#victoryDialog').open)$('#victoryDialog').close();
}
const financeBaseControls=controls;
controls=function(){
 financeBaseControls();
 $('#finalDuel').disabled=busy||!!state?.customer||state?.final_boss?.status!=='waiting'||state?.equipment.stats.hp<=0||phase==='arriving'||phase==='leaving';
 const locked=busy||!state||state.equipment.stats.hp<=0||['active','threatened','ready'].includes(state.combat?.status)||!!state.ending;
 $('#repayOpen').disabled=locked||!!state?.customer||state?.gold<1||state?.loan.paid_off||phase==='arriving'||phase==='leaving';
 $('#repaySubmit').disabled=locked||Math.min(state?.gold||0,(state?.loan.balance||0)+(state?.loan.interest_arrears||0))<1;
 $('#repayAmount').disabled=$('#repaySubmit').disabled;$('#repayClose').disabled=busy;
 if(state?.ending)for(const id of ['equipmentOpen','skillsOpen','commissionsOpen','warehouseOpen','visitCaravan','enter','skipDay','leave','nextDay'])$('#'+id).disabled=true;
 refreshNumberControls();
};
$('#repayOpen').prepend(uiIcon('coin'));
$('#repayOpen').onclick=()=>{$('#repayStatus').textContent='';$('#repayDialog').showModal();renderFinance();controls();};
$('#repayClose').onclick=()=>$('#repayDialog').close();
$('#repayAmount').oninput=updateRepayment;
$('#repayForm').onsubmit=e=>{e.preventDefault();act('repay_early',{amount:Number($('#repayAmount').value)});};
$('#victoryDialog').addEventListener('cancel',e=>e.preventDefault());
$('#victoryMenu').onclick=()=>showTitleScreen();

function showBossEncounter(){
 $('#bossStats').replaceChildren(element('strong',state.final_boss.max_hp+' HP'),iconStat('gear',state.final_boss.attack,'Attack'),iconStat('shield',state.final_boss.defense,'Defense'),iconStat('clock',state.final_boss.interval+'s','Attack interval'));
 document.querySelectorAll('dialog[open]').forEach(d=>{if(d.id!=='bossDialog')d.close();});
 if(!$('#bossDialog').open)$('#bossDialog').showModal();
}
$('#finalDuel').onclick=()=>{$('#bossStatus').textContent='';showBossEncounter();};
$('#bossFight').onclick=()=>{$('#bossDialog').close();act('begin_final_battle');};
$('#bossPrepare').onclick=()=>{$('#bossDialog').close();act('acknowledge_boss');};
$('#bossDialog').addEventListener('cancel',e=>e.preventDefault());
