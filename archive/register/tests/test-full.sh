curl -s "$AGENT_REGISTRY_URL/healthz" && \
echo "Health OK"

AGENT_ID=$(curl -s -X POST "$AGENT_REGISTRY_URL/agents" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RPC_API_KEY" \
  -d '{"method":"create_id","params":{"metadata":{"role":"curl-agent","goal":"test"}},"id":"1"}' | jq -r '.result.id')

echo "Agent: $AGENT_ID"

TASK_ID=$(curl -s -X POST "$AGENT_REGISTRY_URL/tasks" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RPC_API_KEY" \
  -d "{\"method\":\"create_id\",\"params\":{\"agent_id\":\"$AGENT_ID\",\"metadata\":{\"description\":\"curl test\"}},\"id\":\"1\"}" | jq -r '.result.id')

echo "Task: $TASK_ID"

curl -s -X POST "$AGENT_REGISTRY_URL/logs" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RPC_API_KEY" \
  -d "{\"agent_id\":\"$AGENT_ID\",\"task_id\":\"$TASK_ID\",\"level\":\"INFO\",\"message\":\"curl test info\"}"

curl -s "$AGENT_REGISTRY_URL/metrics" | grep $AGENT_ID
