from typing import Annotated,TypedDict 
from langgraph.graph.message import add_messages

class ReasearchState(TypedDict):
    
    #------------Input ------ 
    query: str
    depth :str 
    
    # ------Agent working memory ----- 
    messages = Annotated[list,add_messages] # reducer:appends,never overwrites 
    sub_question : list[str] #planner fills this 
    research_findings : list[str] #reasearcher accumulates this
    gaps_identified :list[str] #critics fill this
    reaserch_iteration :int #superviser incremets this
    
    #output 
    final_reports :str 
    sources : list[str]
    
    #routing 
    next_agent :str #superviser sets this each turn 