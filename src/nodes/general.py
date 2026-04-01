
from states.config import GraphState



def general_node(state: GraphState):
    return {
        "message": f"Hello, {state['name']}!"
    }


