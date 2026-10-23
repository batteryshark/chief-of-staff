// managed by chief-of-staff/install.sh; one watched entry, no package/config entry.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { setupHeartbeat, heartbeatCapabilities } from './plugin.mjs';
import { chiefSelection } from './chief.mjs';
import { Bus } from './bus.mjs';
import { pairedMetadata } from './paired-app.mjs';
import { resolvedObjective } from './objective.mjs';
import { attentionDelivery } from './attention.mjs';
import { atLeast } from './version.mjs';

// The installer replaces only these explicit paths in the Location-local wrapper.
const optionsFile = '__OPTIONS_FILE__';
const allowedLocation = '__LOCATION__';
const statusFile = '__STATUS_FILE__';
export default {
  id: 'chief-heartbeat-pilot',
  async setup(ctx) {
    if (ctx.location.directory !== allowedLocation) return;
    const options = JSON.parse(await readFile(optionsFile, 'utf8'));
    if (!atLeast(ctx.app.version, options.minimumNativeVersion ?? options.nativeVersion)) return;
    const status = { at: Date.now(), pid: process.pid, version: ctx.app.version, location: ctx.location.directory,
      enabled: options.enabled, originSessions: options.originSessions, goalSessions: options.goalSessions,
       principalSending: false, optionsFile, capabilities: heartbeatCapabilities,
       nodAnswerRoute: options.nodCommand?.includes('heartbeat-bus') ? 'heartbeat-bus' : 'unscoped',
       objectiveDataDirectoryOverride: process.env.OPENCHAMBER_DATA_DIR ?? null,
       reconciliationRequired: options.reconciliationRequired === true, rosterFile: options.rosterFile };
    const save = async () => writeFile(statusFile, JSON.stringify(status, null, 2) + '\n');
    // A fresh recipient Location has no prior reset-install directory. Fail before
    // registering timers/tools if that administrative path cannot be created.
    await mkdir(path.dirname(statusFile), { recursive: true, mode: 0o700 });
    let stop;
    try {
      if (options.enabled) {
        status.goalScopes = [];
        for (const sessionID of options.goalSessions ?? []) {
          try {
          const metadata = await pairedMetadata(options.docketSource)(sessionID, options.originDirectory);
          const goal = metadata?.openchamber?.goal, binding = options.goalBindings[sessionID];
          if (!goal || goal.id !== binding.id || goal.objective !== binding.objective || Boolean(goal.objectiveFile) !== binding.objectiveFile) throw Error('Installed pilot goal identity differs');
          const effective = await resolvedObjective(goal, sessionID, binding);
          status.goalScopes.push({ sessionID, goalID: goal.id, source: effective.source, sha256: effective.sha256 });
          } catch (error) {
            // Keep the stored goal membership/binding; never turn a stale goal into
            // no-goal delivery or prevent independent read/status tools from loading.
            status.goalScopes.push({sessionID, goalID: options.goalBindings[sessionID]?.id,
              available: false, error: String(error.message)});
          }
        }
      }
      stop = await setupHeartbeat({ ...ctx, options }, { principalDelivery: attentionDelivery(options), onError: error => {
        status.lastError = String(error.message); void save();
      } });
      if (options.enabled) {
        status.chief = await chiefSelection(options, ctx).current();
        const tools = await ctx.tool.list();
        status.registeredTools = tools.filter(t => /^(chief_|heartbeat_)/.test(t.id))
          .map(t => ({ id: t.id, description: t.description }));
        status.postSupportsExactLimits = Boolean(tools.find(t => t.id === 'chief_post')?.input?.properties?.limits);
        status.context = { hookRegistered: true, chiefOnly: status.chief,
          inbox: JSON.parse(await new Bus(options.memoryRoot).inbox()), recent: JSON.parse(await new Bus(options.memoryRoot).recent()) };
      }
      status.ready = true;
      await save();
      return async () => { await stop(); status.ready = false; status.disposed = true; await save(); };
    } catch (error) { if (stop) await stop(); status.ready = false; status.error = String(error.message); await save(); throw error; }
  },
};
