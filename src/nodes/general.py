from src.states.config import GraphState
from src.services.bedrock import BedrockService


bedrock_service = BedrockService()


def general_node(state: GraphState):
    user_query = state.get("user_query", "").strip()

    response_text = bedrock_service.converse_text(
        system_prompt=(
            "You are a helpful AI assistant. "
            "Answer clearly and concisely. "
            "If the user asks about indexed documents, do not invent results."
        ),
        user_message=user_query,
        temperature=0.3,
        max_tokens=1024,
    )

    return {
        "message": response_text
    }