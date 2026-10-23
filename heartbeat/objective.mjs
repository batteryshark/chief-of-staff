// Read-only mirror of installed session-goal/objectives.js: file first, then inline.
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';

export async function resolvedObjective(goal, sessionID, binding = {}, env = process.env) {
  let text, source = 'inline';
  if (goal.objectiveFile) {
    const root = path.resolve(env.OPENCHAMBER_DATA_DIR || path.join(os.homedir(), '.config/openchamber'));
    const file = path.join(root, 'goals', sessionID + '.md');
    if (!binding.objectiveFilePath || path.resolve(binding.objectiveFilePath) !== file) throw Error('Reviewed objective file/data directory binding differs');
    try { text = (await readFile(file, 'utf8')).trim(); source = file; }
    catch (e) { if (e.code !== 'ENOENT') throw e; }
  }
  if (!text) { text = String(goal.objective ?? '').trim(); source = 'inline'; }
  if (!text || text.length > 128000) throw Error('Resolved goal objective missing or too large');
  const sha256 = createHash('sha256').update(text).digest('hex');
  if (binding.effectiveObjectiveSha256 && sha256 !== binding.effectiveObjectiveSha256) throw Error('Resolved goal objective differs from reviewed scope');
  return { text, source, sha256 };
}
