/**
 * Baseline demo: run an open-weight model on Modal, routed through the
 * Pydantic AI Gateway, traced in Logfire.
 *
 * Swap MODEL below (the Hugging Face repo ID) to whatever you deployed with
 * `modal endpoint create --name gateway --model <MODEL>`.
 */

import * as logfire from "@pydantic/logfire-node";
import { createOpenAI } from "@ai-sdk/openai";
import { generateText } from "ai";

const MODEL = "google/gemma-3-1b-it";
const ROUTE = "agentlenses-provider";

logfire.configure({
  serviceName: "agent-lenses-gateway-demo-ts",
});

const baseUrl = process.env.PYDANTIC_AI_GATEWAY_BASE_URL;
const apiKey = process.env.PYDANTIC_AI_GATEWAY_API_KEY;

if (!baseUrl || !apiKey) {
  throw new Error(
    "Set PYDANTIC_AI_GATEWAY_BASE_URL and PYDANTIC_AI_GATEWAY_API_KEY (e.g. via --env-file)"
  );
}

const gateway = createOpenAI({
  baseURL: `${baseUrl}/${ROUTE}`,
  apiKey,
});

async function main() {
  const { text } = await generateText({
    model: gateway.chat(MODEL),
    prompt:
      "Write a professional email declining a meeting invitation for a sprint planning " +
      "with the design team. Sign off with my direct line, 07700 900123.",
    // AI SDK emits its own OpenTelemetry spans for this call when enabled -
    // no separate OpenAI instrumentation package needed.
    experimental_telemetry: { isEnabled: true },
  });

  logfire.info("agent output: {output}", { output: text });
  console.log(text);

  await logfire.shutdown();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
