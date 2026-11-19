#!/usr/bin/env node
// Verify the APK's exact stdin-owner + cookie-pairing + REA MCP contract on Linux.
// This is credential-free. It never contacts a model provider or executes an analysis target.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {mkdtemp,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:net';
import {randomBytes} from 'node:crypto';
const runtime=resolve(process.argv[2]??'android/runtime');
const temporary=await mkdtemp(join(tmpdir(),'terminator-apk-auth-'));
const passed=[];let child,log='';
async function port(){const s=createServer();s.listen(0,'127.0.0.1');await once(s,'listening');const n=s.address().port;await new Promise(r=>s.close(r));return n;}
try{
 const home=join(temporary,'home');await mkdir(home);const main=await port(),hook=await port(),origin=`http://127.0.0.1:${main}`;
 const owner=randomBytes(32).toString('base64url');
 child=spawn(process.execPath,[join(runtime,'node_modules/openmausbot/dist-server/index.js')],{detached:true,env:{PATH:process.env.PATH,HOME:home,LANG:'C.UTF-8',OMB_DATA_DIR:join(temporary,'workspace'),OMB_STATIC_DIR:join(runtime,'node_modules/openmausbot/dist'),OMB_PORT:String(main),OMB_WEBHOOK_PORT:String(hook),OMB_LOOPBACK_TRUST:'service',OMB_CLI_OWNER_STDIN:'1'},stdio:['pipe','pipe','pipe']});
 child.stdin.end(owner+'\n');
 await new Promise((ok,fail)=>{
  const timer=setTimeout(()=>fail(Error('Readiness timed out')),90000);
  child.once('error',e=>{clearTimeout(timer);fail(e);});child.once('exit',code=>{clearTimeout(timer);fail(Error(`Exited before readiness: ${code}`));});
  const collect=b=>{log=(log+b.toString()).slice(-16000);if(log.includes('openmausbot server on http://')){clearTimeout(timer);ok();}};child.stdout.on('data',collect);child.stderr.on('data',collect);
 });
 const api=(method,path,body,headers={})=>fetch(origin+path,{method,redirect:'error',signal:AbortSignal.timeout(60000),headers:{'content-type':'application/json',...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
 assert.equal((await api('GET','/api/config')).status,403);
 assert.equal((await api('POST','/api/auth/pairing',{}, {'x-openmausbot-cli-owner':'x'.repeat(43)})).status,403);
 passed.push('Anonymous and forged-owner requests rejected');
 const minted=await api('POST','/api/auth/pairing',{label:'APK host fixture',ttlMs:60000},{'x-openmausbot-cli-owner':owner});assert.equal(minted.status,200);const invitation=await minted.json();
 const paired=await api('POST','/api/auth/pair',{code:invitation.code,cookie:true,label:'APK WebView fixture'},{origin});assert.equal(paired.status,200);
 const cookie=paired.headers.get('set-cookie');assert.ok(cookie);assert.match(cookie,/HttpOnly/i);assert.equal((await paired.json()).token,undefined);
 const auth={origin,cookie:cookie.split(';',1)[0]};assert.equal((await api('GET','/api/config',undefined,auth)).status,200);
 passed.push('Private-stdin owner bootstrap and HttpOnly cookie session work');
 assert.equal((await api('POST','/api/auth/pair',{code:invitation.code,cookie:true,label:'Replay'},{origin})).status,401);
 passed.push('Pairing code is single-use');
 const name='terminator-rea',entry=join(runtime,'node_modules/rea-agents/scripts/rea.mjs');
 const config={name,command:process.execPath,args:[entry,'mcp'],enabled:false};
 const added=await api('POST','/api/mcp/servers',config,auth);assert.equal(added.status,201);
 const listed=await (await api('GET','/api/mcp/servers',undefined,auth)).json();assert.equal(listed.servers.find(x=>x.name===name).enabled,false);
 const tested=await api('POST',`/api/mcp/servers/${name}/test`,{},auth);assert.equal(tested.status,200);const probe=await tested.json();assert.equal(probe.ok,true,JSON.stringify(probe));
 passed.push('Original OpenMausBot to REA MCP initialize/tools-list probe passed');
 const {name:_,...updated}=config;updated.enabled=true;
 assert.equal((await api('PUT',`/api/mcp/servers/${name}`,updated,auth)).status,200);
 assert.equal((await api('POST','/api/mcp/servers',{...config,name:'foreign'}, {...auth,origin:'https://example.invalid'})).status,403);
 passed.push('Explicit native connect flow works; foreign-origin mutation denied');
 assert.equal((await api('POST','/api/auth/logout',{},auth)).status,200);
 assert.ok([401,403].includes((await api('GET','/api/config',undefined,auth)).status));
 passed.push('Logged-out cookie cannot read private configuration');
 assert.ok(!log.includes(owner));
 console.log(JSON.stringify({passed,executionHost:{platform:process.platform,architecture:process.arch},androidDeviceTested:false,paidProviderRequestsTested:false,fullParity:'NOT_CERTIFIED'},null,2));
}catch(error){console.error(error);console.error('Bounded fixture log (no provider keys):\n'+log);process.exitCode=1;
}finally{
 if(child&&child.exitCode===null){const exit=once(child,'exit');try{process.kill(-child.pid,'SIGTERM');}catch{}const force=setTimeout(()=>{try{process.kill(-child.pid,'SIGKILL');}catch{}},5000);await exit;clearTimeout(force);}
 await rm(temporary,{recursive:true,force:true});
}
