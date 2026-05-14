from langfuse import observe
from langgraph.graph import END, START, StateGraph

from src.nodes.approval_gate import approval_gate_node
from src.nodes.general import general_node
from src.nodes.hitl_escalate import hitl_escalate_node
from src.nodes.intent import intent_node
from src.nodes.tools import tools_node
from src.states.config import GraphState


@observe()
def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("intent", intent_node, ends=["general", "tools", "escalate", "approval_required"])
    builder.add_node("general", general_node)
    builder.add_node("tools", tools_node)
    builder.add_node("escalate", hitl_escalate_node)
    builder.add_node("approval_required", approval_gate_node)

    builder.add_edge(START, "intent")
    builder.add_edge("general", END)
    builder.add_edge("tools", END)
    builder.add_edge("escalate", END)
    builder.add_edge("approval_required", END)

    return builder.compile()


graph = build_graph()