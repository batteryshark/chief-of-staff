#!/usr/bin/env node
// Offline helper only. No peer contact; receive writes only an explicitly owned fixture/home.
import fs from 'node:fs';
import {resolveOwner,prepareHandoff,receiveHandoff} from '../services/directory/local.mjs';
try {
  const [action,directory,owner,home] = process.argv.slice(2);
  let result;
  if (action === 'resolve') result = resolveOwner(directory,owner);
  else {
    const envelope = JSON.parse(fs.readFileSync(0,'utf8'));
    if (action === 'prepare') result = prepareHandoff(directory,envelope);
    else if (action === 'receive') result = receiveHandoff(directory,owner,home,envelope);
    else throw Error('usage: resolve DIRECTORY OWNER | prepare DIRECTORY < envelope | receive DIRECTORY OWNER OWN_HOME < envelope');
  }
  console.log(JSON.stringify(result));
} catch(e) { console.error(e.message); process.exitCode=1; }
