const crypto = require('crypto');
const http = require('http');
const fs = require('fs');
const path = require('path');

const OPCODES = { TEXT: 0x01, CLOSE: 0x08, PING: 0x09, PONG: 0x0A };
const WS_MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const MAX_FRAME_PAYLOAD_BYTES = 10 * 1024 * 1024;

function computeAcceptKey(clientKey) {
  return crypto.createHash('sha1').update(clientKey + WS_MAGIC).digest('base64');
}

function encodeFrame(opcode, payload) {
  const fin = 0x80;
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.alloc(2);
    header[0] = fin | opcode;
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = fin | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = fin | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payload]);
}

function decodeFrame(buffer) {
  if (buffer.length < 2) return null;
  const secondByte = buffer[1];
  const opcode = buffer[0] & 0x0F;
  const masked = (secondByte & 0x80) !== 0;
  let payloadLen = secondByte & 0x7F;
  let offset = 2;
  if (!masked) throw new Error('Client frames must be masked');
  if (payloadLen === 126) {
    if (buffer.length < 4) return null;
    payloadLen = buffer.readUInt16BE(2);
    offset = 4;
  } else if (payloadLen === 127) {
    if (buffer.length < 10) return null;
    const extendedLen = buffer.readBigUInt64BE(2);
    if (extendedLen > BigInt(MAX_FRAME_PAYLOAD_BYTES)) {
      throw new Error('WebSocket frame payload exceeds maximum allowed size');
    }
    payloadLen = Number(extendedLen);
    offset = 10;
  }
  if (payloadLen > MAX_FRAME_PAYLOAD_BYTES) {
    throw new Error('WebSocket frame payload exceeds maximum allowed size');
  }
  const maskOffset = offset;
  const dataOffset = offset + 4;
  const totalLen = dataOffset + payloadLen;
  if (buffer.length < totalLen) return null;
  const mask = buffer.slice(maskOffset, dataOffset);
  const data = Buffer.alloc(payloadLen);
  for (let i = 0; i < payloadLen; i++) {
    data[i] = buffer[dataOffset + i] ^ mask[i % 4];
  }
  return { opcode, payload: data, bytesConsumed: totalLen };
}

const PORT_FILE = process.env.BRAINSTORM_PORT_FILE || null;
const randomPort = () => 49152 + Math.floor(Math.random() * 16383);
function preferredPort() {
  if (process.env.BRAINSTORM_PORT) return Number(process.env.BRAINSTORM_PORT);
  if (PORT_FILE) {
    try {
      const p = Number(fs.readFileSync(PORT_FILE, 'utf-8').trim());
      if (Number.isInteger(p) && p > 1023 && p < 65536) return p;
    } catch (e) {}
  }
  return randomPort();
}
let PORT = preferredPort();
const HOST = process.env.BRAINSTORM_HOST || '127.0.0.1';
const URL_HOST = process.env.BRAINSTORM_URL_HOST || (HOST === '127.0.0.1' ? 'localhost' : HOST);
const SESSION_DIR = process.env.BRAINSTORM_DIR || '/tmp/brainstorm';
const CONTENT_DIR = path.join(SESSION_DIR, 'content');
const STATE_DIR = path.join(SESSION_DIR, 'state');
const SUPERPOWERS_VERSION = '1.0.0';
const SUPERPOWERS_BRAND_IMAGE_URL = 'https://primeradiant.com/brand/superpowers-visual-brainstorming-logo.png';
const TOKEN_FILE = process.env.BRAINSTORM_TOKEN_FILE || null;
function generateToken() { return crypto.randomBytes(32).toString('hex'); }
function initialToken() {
  if (process.env.BRAINSTORM_TOKEN) return { value: process.env.BRAINSTORM_TOKEN, source: 'env' };
  if (TOKEN_FILE) {
    try {
      const t = fs.readFileSync(TOKEN_FILE, 'utf-8').trim();
      if (/^[0-9a-f]{32,}$/i.test(t)) return { value: t, source: 'file' };
    } catch (e) {}
  }
  return { value: generateToken(), source: 'generated' };
}
const tokenInfo = initialToken();
let TOKEN = tokenInfo.value;
let COOKIE_NAME = 'brainstorm-key-' + PORT;
const MIME_TYPES = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml' };
function waitingPage() { return '<html><body><h1>Brainstorm Companion</h1><p>Waiting for screens...</p></body></html>'; }
function bootstrapPage(key) { return '<html><body><script>sessionStorage.setItem("brainstorm-session-key", "' + key + '"); location.replace("/");</script></body></html>'; }
const frameTemplate = fs.readFileSync(path.join(__dirname, 'frame-template.html'), 'utf-8');
const helperScript = fs.readFileSync(path.join(__dirname, 'helper.js'), 'utf-8');
const helperInjection = '<script>' + helperScript + '</script>';
function isFullDocument(html) { return html.trimStart().toLowerCase().startsWith('<!doctype') || html.trimStart().toLowerCase().startsWith('<html'); }
function wrapInFrame(content) { return frameTemplate.replace('<!-- CONTENT -->', content); }
function getNewestScreen() {
  const files = fs.readdirSync(CONTENT_DIR).filter(f => f.endsWith('.html')).map(f => {
    const fp = path.join(CONTENT_DIR, f);
    return { path: fp, mtime: fs.statSync(fp).mtime.getTime() };
  }).sort((a, b) => b.mtime - a.mtime);
  return files.length > 0 ? files[0].path : null;
}
function companionUrl() { return 'http://' + URL_HOST + ':' + PORT + '/?key=' + TOKEN; }
function isAuthorized(req) {
  const q = req.url.indexOf('?');
  if (q >= 0) {
    const params = new URLSearchParams(req.url.slice(q + 1));
    if (params.get('key') === TOKEN) return true;
  }
  return false;
}
function handleRequest(req, res) {
  if (!isAuthorized(req)) {
    res.writeHead(403); res.end('Forbidden'); return;
  }
  const pathname = req.url.split('?')[0];
  if (pathname === '/') {
    const screenFile = getNewestScreen();
    let html = screenFile ? (raw => isFullDocument(raw) ? raw : wrapInFrame(raw))(fs.readFileSync(screenFile, 'utf-8')) : waitingPage();
    html += helperInjection;
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
  } else if (pathname.startsWith('/files/')) {
    const filePath = path.join(CONTENT_DIR, path.basename(pathname.slice(7)));
    res.writeHead(200); res.end(fs.readFileSync(filePath));
  } else {
    res.writeHead(404); res.end('Not Found');
  }
}
const clients = new Set();
function handleUpgrade(req, socket) {
  if (!isAuthorized(req)) { socket.destroy(); return; }
  const key = req.headers['sec-websocket-key'];
  socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + computeAcceptKey(key) + '\r\n\r\n');
  let buffer = Buffer.alloc(0);
  clients.add(socket);
  socket.on('data', (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    while (buffer.length > 0) {
      const result = decodeFrame(buffer);
      if (!result) break;
      buffer = buffer.slice(result.bytesConsumed);
      if (result.opcode === OPCODES.TEXT) {
        try { const event = JSON.parse(result.payload.toString()); console.log(JSON.stringify({ source: 'user-event', ...event })); } catch (e) {}
      }
    }
  });
  socket.on('close', () => clients.delete(socket));
}
function broadcast(msg) {
  const frame = encodeFrame(OPCODES.TEXT, Buffer.from(JSON.stringify(msg)));
  for (const socket of clients) { try { socket.write(frame); } catch (e) { clients.delete(socket); } }
}
function startServer() {
  if (!fs.existsSync(CONTENT_DIR)) fs.mkdirSync(CONTENT_DIR, { recursive: true });
  if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });
  const server = http.createServer(handleRequest);
  server.on('upgrade', handleUpgrade);
  fs.watch(CONTENT_DIR, (eventType, filename) => {
    if (filename && filename.endsWith('.html')) {
      broadcast({ type: 'reload' });
    }
  });
  server.listen(PORT, HOST, () => {
    console.log(JSON.stringify({ type: 'server-started', port: PORT, url: companionUrl() }));
  });
}
if (require.main === module) startServer();
module.exports = { computeAcceptKey, encodeFrame, decodeFrame };
