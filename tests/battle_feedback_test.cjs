const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const context=vm.createContext({});vm.runInContext(fs.readFileSync(require('path').join(__dirname,'..','battle-effects.js'),'utf8'),context);
vm.runInContext("var seen=[]; syncInjury=()=>{};showStrike=e=>seen.push(e.id);",context);
const step=(id,seq,events)=>vm.runInContext('syncBattleFeedback('+JSON.stringify({equipment:{stats:{}},combat:id?{id,event_seq:seq,events:events.map(n=>({id:n}))}:null})+')',context);
step('saved',3,[1,2,3]);step('saved',3,[1,2,3]);assert.equal(vm.runInContext('seen.length',context),0,'Reload must not replay saved strikes');
step('saved',5,[1,2,3,4,5]);step('saved',5,[1,2,3,4,5]);assert.equal(vm.runInContext('seen.join()',context),'4,5','Polling consumes each strike exactly once');
step(null,0,[]);step('new',0,[]);step('new',1,[1]);assert.equal(vm.runInContext('seen.join()',context),'4,5,1','A new fight starts a fresh event sequence');
console.log('Battle event replay checks passed');
