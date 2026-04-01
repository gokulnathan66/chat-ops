from langgraph.graph import StateGraph, START, END

from states.config import GraphState
from nodes.intent import intent_node
from nodes.general  import general_node
from nodes.tools import tools_node
builder = StateGraph(GraphState)

builder.add_node("intent", intent_node)
builder.add_node("general", general_node)
builder.add_node("tools", tools_node)


builder.add_edge(START, "intent")
builder.add_edge("intent", "general")
builder.add_edge("finish", END)

graph = builder.compile()

result = graph.invoke({"name": "Gokul", "message": ""})
