import test from 'node:test';
import assert from 'node:assert/strict';
import {adaptA2aResult} from '../hosts/domain-policy/a2a-result.mjs';
import {jsonIssues,observeResult} from '../scripts/result-observation.mjs';

test('only own undefined optional parentID is omitted, preserving all other values',()=>{
  const trace={trace:'kept'},output={data:1};
  const raw={content:'Created local/ses_child. Message it with a2a_send.',output,
    metadata:{trace,a2a:{ok:true,to:'local/ses_child',nested:false,parentID:undefined,extra:trace}}};
  const result=adaptA2aResult(raw);
  assert.deepEqual(result,{content:raw.content,output,metadata:{trace,a2a:{ok:true,to:'local/ses_child',nested:false,extra:trace}}});
  assert.equal(result.output,output);assert.equal(result.metadata.trace,trace);assert.equal(result.metadata.a2a.extra,trace);
  assert.equal(Object.hasOwn(result.metadata.a2a,'parentID'),false);
  assert.equal(Object.hasOwn(raw.metadata.a2a,'parentID'),true);assert.equal(raw.metadata.a2a.parentID,undefined);
  assert.deepEqual(jsonIssues(raw.metadata),['$.a2a.parentID: undefined']);assert.deepEqual(jsonIssues(result.metadata),[]);
});
test('nested string parent and already valid nonnested result are unchanged by identity',()=>{
  for(const a2a of [{ok:true,to:'local/ses_child',nested:true,parentID:'ses_parent'},
    {ok:true,to:'local/ses_child',nested:false},{ok:false,parentID:null},{parentID:0}]) {
    const raw={content:'unchanged',metadata:{a2a}};
    assert.equal(adaptA2aResult(raw),raw);assert.equal(raw.metadata.a2a,a2a);
  }
});
test('unrelated invalid metadata is retained rather than silently erased or normalized',()=>{
  const fn=()=>{},raw={content:'original',metadata:{other:undefined,a2a:{parentID:undefined,nested:false,invalid:undefined,nonfinite:NaN,fn}}};
  const result=adaptA2aResult(raw);
  assert.ok(Object.hasOwn(result.metadata,'other'));assert.ok(Object.hasOwn(result.metadata.a2a,'invalid'));
  assert.equal(result.metadata.a2a.fn,fn);assert.ok(Number.isNaN(result.metadata.a2a.nonfinite));
  assert.deepEqual(jsonIssues(result.metadata),['$.other: undefined','$.a2a.invalid: undefined','$.a2a.nonfinite: nonfinite number','$.a2a.fn: function']);
});
test('unrelated descriptors and symbol values survive the narrow path copies',()=>{
  const symbol=Symbol('other'),a2a={parentID:undefined,ok:true};
  Object.defineProperty(a2a,'hidden',{value:'preserved',enumerable:false});a2a[symbol]='preserved';
  const raw={content:'original',metadata:{a2a}};Object.defineProperty(raw,'retained',{value:123,enumerable:false});
  const result=adaptA2aResult(raw);
  assert.deepEqual(Object.getOwnPropertyDescriptor(result,'retained'),Object.getOwnPropertyDescriptor(raw,'retained'));
  assert.deepEqual(Object.getOwnPropertyDescriptor(result.metadata.a2a,'hidden'),Object.getOwnPropertyDescriptor(a2a,'hidden'));
  assert.equal(result.metadata.a2a[symbol],'preserved');
});
test('diagnostics record own presence/type and invalidity before JSON can omit undefined',()=>{
  const raw={content:'real content',metadata:{a2a:{ok:true,to:'local/ses_child',nested:false,parentID:undefined}}};
  const context={sessionID:'ses_chief',messageID:'msg_fixture',id:'call_fixture',agent:'example-chief'};
  const before=observeResult({stage:'before',result:raw,context,tool:'domain_a2a_create'});
  const after=observeResult({stage:'after',result:adaptA2aResult(raw),context,tool:'domain_a2a_create'});
  assert.equal(before.ownParentID,true);assert.equal(before.parentIDType,'undefined');assert.equal(before.resultIssues.length,1);
  assert.equal(after.ownParentID,false);assert.deepEqual(after.resultIssues,[]);
  assert.equal(after.content,before.content);assert.equal(after.destination,before.destination);assert.equal(after.callID,before.callID);
});
