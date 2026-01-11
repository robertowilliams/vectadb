# Setting Up Synthetic API for VectaDB Schema Agent

## Quick Setup (3 Steps)

### Step 1: Get Your API Key

1. Go to: https://glhf.chat
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `glhf_...`)

### Step 2: Set Your API Key

Choose one of these methods:

**Method A: Use the demo script (easiest)**
```bash
./demo_schema_agent.sh glhf_your_api_key_here
```

**Method B: Export as environment variable**
```bash
export SYNTHETIC_API_KEY=glhf_your_api_key_here
./demo_schema_agent.sh
```

**Method C: Add to .env.models file**
```bash
echo "SYNTHETIC_API_KEY=glhf_your_api_key_here" >> .env.models
python3 vectadb_schema_agent.py --model glm-4.7 --api-base "https://api.glhf.chat/v1" --schema-file bedrock_schema.json --format json
```

### Step 3: Run the Test

```bash
./demo_schema_agent.sh
```

The script will:
- ✅ Check VectaDB is running
- ✅ Test Synthetic API connection
- ✅ Fix the bedrock_schema.json
- ✅ Upload schema to VectaDB
- ✅ Verify success

---

## What Models Are Available?

On Synthetic API (glhf.chat), these models from our list are available:

1. **GLM-4.7** (Budget-friendly) - `hf:zai-org/GLM-4.7`
   - Context: 202K tokens
   - Cost: $0.55 input / $2.19 output per 1M tokens
   - Best for: Testing, iteration, cost optimization

2. **GLM-4.6** (Ultra-cheap) - `hf:zai-org/GLM-4.6`
   - Context: 202K tokens
   - Cost: $0.11 input / $0.33 output per 1M tokens
   - Best for: High-volume testing

3. **Kimi K2 Thinking** - `hf:Kimi/Kimi-k2-thinking`
   - Context: 262K tokens
   - Cost: $0.44 input / $1.32 output per 1M tokens
   - Best for: Complex reasoning tasks

---

## Testing Without API Key (Free Tier)

Synthetic offers a free tier with limited requests. Just sign up and you'll get:
- Free API key
- Limited requests per month
- Perfect for testing the schema agent

---

## Full Test Command

Once you have your API key:

```bash
# Test with GLM-4.7 (recommended)
python3 vectadb_schema_agent.py \
  --model glm-4.7 \
  --api-base "https://api.glhf.chat/v1" \
  --api-key "glhf_your_key_here" \
  --schema-file bedrock_schema.json \
  --format json
```

Or use the demo script:
```bash
./demo_schema_agent.sh glhf_your_key_here
```

---

## Verifying Success

After running the agent, check if the schema was uploaded:

```bash
curl http://localhost:8080/health | python3 -m json.tool
```

Should show:
```json
{
  "status": "healthy",
  "ontology_loaded": true,
  "ontology_namespace": "bedrock.healthcare",
  "ontology_version": "1.0.0"
}
```

---

## Next Steps After Schema Upload

Once the schema is uploaded:

1. **Ingest Bedrock data:**
   ```bash
   python3 ingest_bedrock_graph.py
   ```

2. **Start the UI (if not running):**
   ```bash
   cd vectadb-ui
   npm run dev
   ```

3. **View the graph:**
   ```bash
   open http://localhost:5173/graph
   ```

---

## Troubleshooting

### "Invalid API key" error
- Make sure your key starts with `glhf_`
- Check you copied the entire key
- Try generating a new key at https://glhf.chat

### "Rate limit exceeded" error
- Free tier has limited requests
- Wait a few minutes and try again
- Consider upgrading your plan

### "Model not found" error
- Make sure you're using `hf:` prefix: `hf:zai-org/GLM-4.7`
- Check the model is available on Synthetic

### Schema still fails after agent runs
- Check the agent output for specific errors
- Try a stronger model: `--model glm-4.7` instead of `glm-4.6`
- Review the fixed schema manually

---

## Cost Estimate

For fixing the bedrock_schema.json:
- Input: ~2,000 tokens (schema + error + instructions)
- Output: ~1,500 tokens (fixed schema)
- **Total cost: ~$0.004 (less than half a cent)**

---

## Alternative: Test Locally First

If you don't want to use an API key yet, you can:

1. Manually fix the schema (see INTEGRATION_COMPLETE.md)
2. Use a local LLM with Ollama (slower but free)
3. Review the agent's logic in `vectadb_schema_agent.py`

But using Synthetic API is **highly recommended** for:
- Fast response times (2-5 seconds)
- High success rate
- Minimal cost
- No local GPU needed

---

## Ready to Test!

Get your key from https://glhf.chat and run:

```bash
./demo_schema_agent.sh glhf_your_key_here
```

Good luck! 🚀
