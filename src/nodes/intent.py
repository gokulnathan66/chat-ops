
from states.config import GraphState

# from config.settings import settings

# print(settings.app_name)
# print(settings.db_url)



def intent_node(state: GraphState):
    return {
        "message": f"Hello, {state['name']}!"
    }


