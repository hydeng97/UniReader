import uvicorn
from main import app, SERVER_HOST, SERVER_PORT

if __name__ == "__main__":
    print(f"Starting server at http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"Open http://localhost:{SERVER_PORT} in your browser")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
