import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from src.persistence.db import DB_PATH


def get_checkpointer() -> SqliteSaver:
    # Pass a raw connection directly — do NOT use from_conn_string() 
    # (it returns a context manager, not a saver instance)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)