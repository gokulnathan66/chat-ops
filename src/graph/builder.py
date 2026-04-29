from langfuse import observe
from langgraph.graph import END, START, StateGraph

from src.nodes.general import general_node
from src.nodes.intent import intent_node
from src.nodes.tools import tools_node
from src.states.config import GraphState


@observe()
def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("intent", intent_node, ends=["general", "tools"])
    builder.add_node("general", general_node)
    builder.add_node("tools", tools_node)

    builder.add_edge(START, "intent")
    builder.add_edge("general", END)
    builder.add_edge("tools", END)

    return builder.compile()


graph = build_graph()