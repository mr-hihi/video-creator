const DEFAULT_AGENT_PORT = 4024;
const AGENT_PORT_KEY = 'agentPort';
const MIN_AGENT_PORT = 1;
const MAX_AGENT_PORT = 65535;

function toAgentPort(value) {
  const port = parseInt(value, 10);
  if (!Number.isInteger(port) || port < MIN_AGENT_PORT || port > MAX_AGENT_PORT) {
    return DEFAULT_AGENT_PORT;
  }
  return port;
}

function buildAgentWsUrl(port) {
  return `ws://127.0.0.1:${port}`;
}
