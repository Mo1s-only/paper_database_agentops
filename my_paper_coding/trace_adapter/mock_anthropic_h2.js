#!/usr/bin/env node
// Local-only Anthropic HTTPS mock with HTTP/2 ALPN. No provider connections.
const fs = require('fs');
const http2 = require('http2');

const args = process.argv.slice(2);
function option(name) {
  const index = args.indexOf(name);
  if (index < 0 || index + 1 >= args.length) throw new Error(`Missing ${name}`);
  return args[index + 1];
}
const port = Number(option('--port'));
const logPath = option('--log');
const server = http2.createSecureServer({
  key: fs.readFileSync(option('--tls-key')),
  cert: fs.readFileSync(option('--tls-cert')),
  allowHTTP1: true,
  ALPNProtocols: ['h2', 'http/1.1'],
});

function firstPrompt(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(firstPrompt).join(' ');
  if (!value || typeof value !== 'object') return '';
  for (const key of ['messages', 'input', 'content', 'text', 'prompt']) {
    if (key in value) return firstPrompt(value[key]);
  }
  return Object.values(value).map(firstPrompt).join(' ');
}

server.on('request', (req, res) => {
  const path = new URL(req.url, 'https://127.0.0.1').pathname;
  if (path === '/health') {
    res.writeHead(200, {'content-type': 'application/json'});
    res.end(JSON.stringify({ok: true}));
    return;
  }
  const chunks = [];
  req.on('data', chunk => chunks.push(chunk));
  req.on('end', () => {
    let payload = {};
    try { payload = JSON.parse(Buffer.concat(chunks).toString()); } catch (_) {}
    fs.appendFileSync(logPath, JSON.stringify({
      path, protocol: req.httpVersion, stream: Boolean(payload.stream),
      body_bytes: Buffer.concat(chunks).length,
      prompt: firstPrompt(payload),
    }) + '\n');
    const model = payload.model || 'claude-agentsight-mock';
    if (payload.stream) {
      const message = {id: 'msg_agentsight_stream', type: 'message', role: 'assistant',
        model, content: [], stop_reason: null, stop_sequence: null,
        usage: {input_tokens: 11, output_tokens: 0}};
      const events = [
        ['message_start', {type: 'message_start', message}],
        ['content_block_start', {type: 'content_block_start', index: 0,
          content_block: {type: 'text', text: ''}}],
        ['content_block_delta', {type: 'content_block_delta', index: 0,
          delta: {type: 'text_delta', text: 'agentsight mock response'}}],
        ['content_block_stop', {type: 'content_block_stop', index: 0}],
        ['message_delta', {type: 'message_delta', delta: {stop_reason: 'end_turn', stop_sequence: null},
          usage: {output_tokens: 4}}],
        ['message_stop', {type: 'message_stop'}],
      ];
      res.writeHead(200, {'content-type': 'text/event-stream', 'cache-control': 'no-cache'});
      for (const [name, data] of events) res.write(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`);
      res.end();
    } else {
      res.writeHead(200, {'content-type': 'application/json'});
      res.end(JSON.stringify({id: 'msg_agentsight', type: 'message', role: 'assistant', model,
        content: [{type: 'text', text: 'agentsight mock response'}],
        stop_reason: 'end_turn', stop_sequence: null,
        usage: {input_tokens: 11, output_tokens: 4}}));
    }
  });
});

server.listen(port, '127.0.0.1', () => process.stdout.write(`https://127.0.0.1:${port}\n`));
