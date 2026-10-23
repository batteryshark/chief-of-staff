import { readFile } from 'node:fs/promises';
import { Bus } from './bus.mjs';
import { ingestNodAnswer } from './nod.mjs';
const [flag, file, trusted] = process.argv.slice(2);
if (flag !== '--options' || !file?.startsWith('/') || trusted !== '--trusted-kit-input') throw Error('Expected --options /absolute/known/options.json --trusted-kit-input; stdin is a saved authenticated kit answer');
const options = JSON.parse(await readFile(file, 'utf8'));
let text = '';
for await (const chunk of process.stdin) { text += chunk; if (text.length > 18000) throw Error('Answer input too large'); }
console.log(JSON.stringify(await ingestNodAnswer(new Bus(options.memoryRoot), JSON.parse(text))));
