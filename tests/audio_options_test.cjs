const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
(async()=>{
 const nodes=new Map();function node(id){if(!nodes.has(id))nodes.set(id,{value:0,volume:0,currentTime:0,paused:true,playCalls:0,play(){this.paused=false;this.playCalls++;return Promise.resolve();},pause(){this.paused=true;},setAttribute(k,v){this[k]=v;}});return nodes.get(id);}
 let frames=new Map(),frameId=0;const saved={sound:false,volume:42,reduceMotion:false};
 const context=vm.createContext({$:node,Promise,Math,JSON,Number,performance:{now:()=>0},state:null,sound:true,audio:null,audioBus:{gain:{value:0}},prepareAudio:()=>{},paymentPouchAudio:node('pouch'),coinRattleAudio:node('coins'),customerArrivalAudio:node('arrival'),buttonAudio:node('button'),document:{hidden:false,documentElement:{dataset:{}},addEventListener(){}},localStorage:{getItem:()=>JSON.stringify(saved),setItem:(key,value)=>Object.assign(saved,JSON.parse(value))},requestAnimationFrame:fn=>{frames.set(++frameId,fn);return frameId;},cancelAnimationFrame:id=>frames.delete(id),refreshNumberControls(){},addNumberStepper(){}});
 const run=code=>vm.runInContext(code,context);const finishFade=(time=1000)=>{const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(time));};
 run(fs.readFileSync(require('path').join(__dirname,'..','audio-manager.js'),'utf8'));
 run(fs.readFileSync(require('path').join(__dirname,'..','opening.js'),'utf8').split('const PROLOGUE=')[0]);
 assert.equal(run('gameOptions.effectsVolume'),42);assert.equal(run('gameOptions.musicVolume'),35);assert.equal(run('gameOptions.music'),true);
 run('unlockMusic()');await Promise.resolve();finishFade(-10);assert.ok(node('#ambientMusic').volume>=0&&node('#battleMusic').volume>=0,'First animation timestamp may predate performance.now');finishFade();assert.equal(node('#ambientMusic').paused,false);assert.equal(node('#battleMusic').paused,true);
 run("state={combat:{status:'threatened'}};syncMusic()");assert.equal(run('musicTarget===ambientMusic'),true);
 run("state={combat:{status:'active'}};syncMusic()");finishFade();assert.equal(node('#ambientMusic').paused,true);assert.equal(node('#battleMusic').paused,false);assert.equal(node('#battleMusic').volume,.35);
 run("setGameOption('effectsVolume',20)");assert.equal(node('button').volume,.2);assert.equal(node('#battleMusic').volume,.35,'SFX volume must not change music');
 run("setGameOption('sound',true);playDiceSound()");assert.equal(node('#diceRollAudio').volume,.2);assert.equal(node('#diceRollAudio').paused,false);
 run("setGameOption('sound',false)");assert.equal(node('#diceRollAudio').paused,true);assert.equal(node('#battleMusic').paused,false,'SFX mute must not mute music');
 run("setGameOption('music',false)");assert.equal(node('#battleMusic').paused,true);assert.equal(node('#ambientMusic').paused,true);
 run("setGameOption('music',true);state.combat.status='victory';syncMusic()");finishFade();assert.equal(node('#ambientMusic').paused,false);assert.equal(node('#battleMusic').paused,true);
 run("document.hidden=true;syncMusic()");assert.equal(node('#ambientMusic').paused,true);
 assert.equal(saved.effectsVolume,20);assert.equal(saved.music,true);console.log('Audio migration, independent volumes, dice playback and music transitions passed');
})().catch(error=>{console.error(error);process.exitCode=1});
