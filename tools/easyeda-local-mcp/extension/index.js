import { project1, project1Methods } from './project1.js';
// EasyEDA Pro 3.2.149: only official environment and local WebSocket APIs.
const SOCKET_ID = 'codex-project1-fixed';
const ENDPOINT = 'ws://127.0.0.1:18149/easyeda';
let paired = false;
function send(message) { eda.sys_WebSocket.send(SOCKET_ID, JSON.stringify(message)); }
function environment() {
  const env = eda.sys_Environment;
  return {
    editorVersion: env.getEditorCurrentVersion(), isClient: env.isClient(),
    isOnline: env.isOnlineMode(), isHalfOffline: env.isHalfOfflineMode(),
    isOffline: env.isOfflineMode(),
  };
}
async function receive(event) {
  if (typeof event.data !== 'string' || event.data.length > 4096) return;
  let m;
  try { m = JSON.parse(event.data); } catch { return; }
  if (!m || typeof m !== 'object' || Array.isArray(m)) return;
  if (m.type === 'paired' && Object.keys(m).length === 1) {
    paired = true;
    eda.sys_MessageBox.showInformationMessage('Local bridge paired. Project1 fixed document controls.', 'Local environment bridge', 'OK');
    return;
  }
  if (!paired || m.type !== 'request' || typeof m.id !== 'string' || !/^[a-zA-Z0-9_-]{1,64}$/.test(m.id)) return;
  if (Object.keys(m).length !== 3 || m.method !== 'environment' && !project1Methods.includes(m.method)) {
    send({ type: 'response', id: m.id, error: 'operation_not_allowed' }); return;
  }
  try { send({ type: 'response', id: m.id, result: m.method === 'environment' ? environment() : await project1(m.method) }); }
  catch (e) { send({ type: 'response', id: m.id, error: /^[a-z_]+$/.test(e.message) ? e.message : 'api_operation_failed' }); }
}
export function connect() {
  eda.sys_Dialog.showInputDialog(
    'Enter the current local bridge pairing code.',
    '127.0.0.1:18149 only. Project1 fixed document controls.',
    'Local environment bridge', 'password', '', { minlength: 64, maxlength: 64 },
    token => {
      if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) return;
      paired = false;
      try { eda.sys_WebSocket.close(SOCKET_ID, 1000, 'Reconnect'); } catch {}
      eda.sys_WebSocket.register(SOCKET_ID, ENDPOINT, receive, () => {
        send({ type: 'authenticate', token }); token = '';
      });
    },
  );
}
export function disconnect() {
  paired = false;
  try { eda.sys_WebSocket.close(SOCKET_ID, 1000, 'User disconnected'); } catch {}
}
