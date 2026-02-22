from langgraph.checkpoint.sqlite import SqliteSaver
from src.persistence.db import DB_PATH 

def get_checkpointer()->SqliteSaver:
    #SqliteSaver creates its own tables in the same DB file 
    #thread_id is passed at invoke time = (= job_id UUID). 
    return SqliteSaver.from_conn_string(str(DB_PATH))