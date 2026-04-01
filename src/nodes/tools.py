
from states.config import GraphState



def tools_node(state: GraphState):
    return {
        "message": f"Hello, {state['name']}!"
    }


