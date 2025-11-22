from fastapi import FastAPI
from pydantic import BaseModel
from helper import extract_repo_knowledge

app = FastAPI()


class KnowledgeRequest(BaseModel):
    """Request model for extract_knowledge endpoint"""
    repo_path: str


@app.get("/health")
async def health_check():
    """Health check endpoint to verify the server is running"""
    return {
        "status": "healthy",
        "message": "Server is running"
    }


@app.post("/extract_knowledge")
async def extract_knowledge(request: KnowledgeRequest):
    """
    Extract knowledge from the provided repository path
    
    Args:
        request: KnowledgeRequest containing the repository path to process
        
    Returns:
        dict: Extracted knowledge data
    """

    try:
        knowledge = extract_repo_knowledge(request.repo_path)

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

    return {
        "status": "success"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
