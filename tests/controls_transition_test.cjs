// Exercise the actual layered control functions across combat and recovery states.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const nodes=new Map();function node(key){if(!nodes.has(key))nodes.set(key,{disabled:false,hidden:false,dataset:{},querySelectorAll:()=>[]});return nodes.get(key);}
const context=vm.createContext({$:node,syncJournal(){},refreshNumberControls(){},document:{querySelectorAll:()=>[]},busy:false,phase:'idle',state:{customer:null,deal:null,combat:null,ending:null,daily:{closed:false},caravan:{open:false},calendar:{weekday:'Thursday'},equipment:{stats:{hp:100}},loan:{balance:20000,interest_arrears:0},gold:721}});
function block(file,start,end){const source=fs.readFileSync(file,'utf8');return source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));}
vm.runInContext(block(require('path').join(__dirname,'..','game.js'),'function controls(){','function playMoneyClip('),context);
vm.runInContext(block(require('path').join(__dirname,'..','equipment.js'),'const equipmentBaseControls=controls;','setInterval('),context);
vm.runInContext(block(require('path').join(__dirname,'..','finance.js'),'const financeBaseControls=controls;',"$('#repayOpen').prepend"),context);
const run=code=>vm.runInContext(code,context);
run('controls()');assert.equal(node('#commissionsOpen').disabled,false);
for(const status of ['threatened','ready','active']){run(`state.combat={status:'${status}'};controls()`);assert.equal(node('#commissionsOpen').disabled,true);}
for(const status of ['victory','escaped','spared']){run(`state.combat={status:'${status}'};controls()`);assert.equal(node('#commissionsOpen').disabled,false);}
run("state.combat={status:'defeat'};state.equipment.stats.hp=0;controls()");assert.equal(node('#commissionsOpen').disabled,true);
run("state.combat=null;state.equipment.stats.hp=100;phase='idle';controls()");assert.equal(node('#commissionsOpen').disabled,false,'Rest must unlock commissions');
for(const phase of ['arriving','leaving']){run(`phase='${phase}';controls()`);assert.equal(node('#commissionsOpen').disabled,true);}
run("phase='idle';busy=true;controls()");assert.equal(node('#commissionsOpen').disabled,true);
run('busy=false;controls()');assert.equal(node('#commissionsOpen').disabled,false,'Request completion must unlock commissions');
run('state.ending={day:1};controls()');assert.equal(node('#commissionsOpen').disabled,true);
run('state.ending=null;controls()');assert.equal(node('#commissionsOpen').disabled,false,'A new campaign must unlock commissions');
console.log('Commission controls recover after combat, rest, busy states and campaign reset');
