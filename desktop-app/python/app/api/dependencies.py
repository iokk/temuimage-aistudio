from fastapi import Request

from app.db.connection import create_connection


def get_db_connection(request: Request):
    runtime = request.app.state.runtime
    connection = create_connection(runtime.db_path)
    try:
        yield connection
    finally:
        connection.close()
