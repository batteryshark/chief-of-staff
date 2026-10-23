import test from 'node:test';
import assert from 'node:assert/strict';
import {atLeast} from '../heartbeat/version.mjs';

test('release floor admits 2.1.x and 2.5.1, rejects older/malformed hosts',()=>{
  for(const version of ['2.0.32','2.0.33','2.1.0','2.1.9','2.5.1'])assert.equal(atLeast(version),true,version);
  for(const version of ['2.0.31','1.9.99','2.1','2.1.0-beta','v2.1.0',null,'garbage'])assert.equal(atLeast(version),false,String(version));
});
// This tests version admission, NOT a real 2.1.x native host API or plugin-load matrix.
