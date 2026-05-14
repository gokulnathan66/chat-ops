
I built a production-grade LLMOps platform — and it’s much more than just a chat app.

Most conversational AI demos stop at: “Ask a question, get an answer.”  
But in real-world systems, that’s only the beginning.

Once a conversational application is deployed, the real challenges start:

- How do you evaluate whether the system is performing well over time?
- How do you detect retrieval degradation in your RAG pipeline?
- How do you observe model behavior, trace failures, and manage prompts?
- What happens when the assistant cannot provide an adequate answer?
- How do you bring a human into the loop for sensitive tasks or escalation scenarios?

These are the problems I wanted to explore.

So I built an end-to-end LLMOps platform that covers the core building blocks needed for production AI systems: evaluation, observability, prompt management, data management, human oversight, and operational reliability.

Here’s what the system includes:

→ A LangGraph-based routing pipeline that classifies every query into 4 intents: general chat, RAG retrieval, human escalation, or approval-required actions — using structured output with Claude Haiku 4.5 on AWS Bedrock.

→ A RAG engine powered by Qdrant + AWS Titan Embeddings, with cosine similarity scoring, source citation, and automatic re-retrieval when relevance drops below threshold.

→ A dual-mode Human-in-the-Loop system:
- Mid-conversation escalation, where the AI can hand off to a human agent in real time
- Approval gates for sensitive operations that require supervisor sign-off before execution

→ An automated evaluation pipeline using AWS Lambda + EventBridge:
- RAG quality checks triggered after every document ingestion
- Post-conversation sentiment and topic analysis running every 15 minutes
- Automatic degradation detection and alerting

→ Two Next.js dashboards:
- A customer-facing chat interface
- An operator console to monitor evaluation scores, manage HITL queues, and track document ingestion jobs

→ Full Langfuse integration for prompt management, tracing, and observability — including intent classification, tool calls, agent steps, and per-turn cost tracking

→ Infrastructure deployed through Terraform across multiple AWS services, including EC2, DynamoDB, Lambda, EventBridge, Secrets Manager, S3, and more

To me, this is what real LLMOps looks like.

Not just connecting a RAG pipeline to an LLM and deploying a demo — but building the systems needed after deployment: evaluation, observability, degradation detection, prompt control, and human oversight from day one.

Tech stack: FastAPI · LangGraph · LangChain · AWS Bedrock · Claude Haiku 4.5 · Qdrant · DynamoDB · S3 · Lambda · Langfuse · Next.js 14 · Terraform

Happy to answer questions or do a deeper walkthrough of any part of the architecture.

#LLMOps #RAG #LangGraph #AWS #GenerativeAI #ProductionAI #MLOps #BuildInPublic

