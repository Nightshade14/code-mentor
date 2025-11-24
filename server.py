import json
import os
from typing import List

import graphviz
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from git import Repo
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from helper import extract_repo_knowledge

load_dotenv()


RELATIONSHIPS = None

class Relationship(BaseModel):
    source: str = Field(
        ...,
        description="The source entity (Class, Function, or Service). Use CamelCase.",
    )
    target: str = Field(
        ...,
        description="The target entity being called (Database, API, or Class). Use CamelCase.",
    )
    label: str = Field(
        ...,
        description="The relationship type (calls, reads_from, writes_to, depends_on). Max 3 words.",
    )


class KnowledgeGraph(BaseModel):
    relationships: List[Relationship] = Field(
        ..., description="A flat list of all directed edges extracted from the code."
    )


# --- 2. Core Logic ---
def find_relationships(knowledge: list) -> KnowledgeGraph:
    """
    Extracts dependencies using Gemini with Strict Structured Output.
    """

    system_prompt = """
    You are an Expert Software Architect. Your goal is to output a FLAT list of dependencies based on the provided code structure.

    RULES:
    1. Output strict and correct JSON matching the KnowledgeGraph response schema.
    2. Flatten all nested calls into direct Source -> Target relationships.
    3. Normalize names: 'stripe.Charge.create' becomes 'StripeAPI'.
    4. Ignore trivial logs/prints.
    """

    all_relationships = []
    batch_size = 8

    # Chunk the knowledge list into batches
    batches = [
        knowledge[i : i + batch_size] for i in range(0, len(knowledge), batch_size)
    ]

    print(f"Processing {len(knowledge)} files in {len(batches)} batches...")

    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        for i, batch in enumerate(batches):
            print(f"Calling LLM API for batch {i + 1}/{len(batches)}...")

            try:
                response = client.models.generate_content(
                    model="gemini-3-pro-preview",
                    # model="gemini-2.5-flash-lite-preview-09-2025",
                    contents=f"Analyze this code structure and generate the dependency graph:\n\n{json.dumps(batch)}",
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=KnowledgeGraph,
                        thinkingConfig={
                            "includeThoughts": False,
                            "thinkingLevel": "LOW",
                        },
                    ),
                )

                if response.parsed:
                    all_relationships.extend(response.parsed.relationships)
                else:
                    # Fallback if parsing fails but text exists
                    batch_graph = KnowledgeGraph.model_validate_json(response.text)
                    all_relationships.extend(batch_graph.relationships)

            except Exception as e:
                print(f"Error processing batch {i + 1}: {e}")
                # Continue to next batch instead of failing completely
                continue

        res = KnowledgeGraph(relationships=all_relationships)
        return res

    except Exception as e:
        print(f"LLM Extraction Error: {e}")
        # Return empty graph on failure to prevent API crash
        return []


def render_architecture_graph(
    graph_data: KnowledgeGraph, output_filename="static/gem_3_arch"
):
    """
    Renders a Graphviz diagram. Accepts the Pydantic object directly.
    """

    print("Rendering architecture graph...")

    dot = graphviz.Digraph(comment="Architecture Auto-Draftsman")

    # Styling
    dot.attr(rankdir="LR", splines="ortho")
    dot.attr("node", shape="box", style="filled", fontname="Helvetica")
    dot.attr("edge", fontname="Helvetica", fontsize="10", color="#455A64")

    def get_style(node_name):
        n = node_name.lower()
        if any(x in n for x in ["db", "database", "sql", "redis"]):
            return "cylinder", "#FFF9C4"  # Yellow
        if any(x in n for x in ["api", "stripe", "aws", "s3"]):
            return "component", "#E1F5FE"  # Blue
        if any(x in n for x in ["user", "client", "front"]):
            return "oval", "#F5F5F5"  # Grey
        return "box", "#E8F5E9"  # Green default

    # Extract relationships list from Pydantic model
    edges = graph_data.relationships
    added_nodes = set()

    for edge in edges:
        # Add Source
        if edge.source not in added_nodes:
            s, c = get_style(edge.source)
            dot.node(edge.source, shape=s, fillcolor=c)
            added_nodes.add(edge.source)

        # Add Target
        if edge.target not in added_nodes:
            s, c = get_style(edge.target)
            dot.node(edge.target, shape=s, fillcolor=c)
            added_nodes.add(edge.target)

        # Add Edge
        dot.edge(edge.source, edge.target, label=edge.label)

    try:
        output_path = dot.render(output_filename, format="png", view=False)
        return output_path
    except Exception as e:
        print(f"Graphviz Error: {e}")
        return None


# --- 3. API Setup ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


class KnowledgeRequest(BaseModel):
    repo_path: str


@app.post("/extract_knowledge")
async def extract_knowledge(request: KnowledgeRequest):
    try:
        # 0. Download git repo
        git_url = request.repo_path
        repo_dir = request.repo_path.split("/")[-1][:-4]

        try:
            if not os.path.exists(repo_dir):
                os.makedirs(repo_dir, exist_ok=True)
                Repo.clone_from(git_url, repo_dir)
                print(f"Repository successfully cloned to {repo_dir}")
        except Exception as e:
            print(f"Error cloning repository: {e}")

        # 1. Get Raw Knowledge (AST/File dict)
        raw_knowledge = extract_repo_knowledge(repo_dir)

        # 2. Get Flat Relationships (Pydantic Object)
        graph_data: KnowledgeGraph = find_relationships(raw_knowledge)
        RELATIONSHIPS = graph_data.relationships

        # 3. Generate Diagram
        diagram_path = render_architecture_graph(graph_data)

        # 4. Return JSON
        return {
            "status": "success",
            "diagram_path": diagram_path,
        }

    except Exception as e:
        # Log the full error for your hackathon debugging
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enhance_diagram")
async def enhance_diagram():
    from PIL import Image

    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        prompt = f"""
        Generate a professional, high-fidelity technical knowledge graph diagram.

        **VISUAL STYLE GUIDE:**
        - The diagram must look like a clean engineering blueprint or technical schematic.
        - Background: Clean, neutral.
        - Lines: Solid, precise connector lines with clear arrowheads indicating direction.
        - **CRITICAL: ALL TEXT LABELS ON NODES AND CONNECTOR ARROWS MUST BE PERFECTLY LEGIBLE, SHARP, AND CRISP.** Do not generate blurry or gibberish text.

        **LAYOUT & CONTENT INSTRUCTIONS:**
        Organize the elements spatially to minimize overlapping lines. The flow should generally move from inputs (left/top) to data storage (right/bottom).

        DETAILED CONTENT DESCRIPTION:
        {RELATIONSHIPS}
        """

        # Use absolute path or relative to CWD, assuming CWD is repo root
        input_image_path = "static/gem_3_arch.png"
        if not os.path.exists(input_image_path):
            raise HTTPException(status_code=404, detail="Original diagram not found")

        image = Image.open(input_image_path)

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt],
        )

        output_path = "static/gem_3_arch_enhanced.png"

        for part in response.parts:
            if part.text is not None:
                print(part.text)
            elif part.inline_data is not None:
                image = part.as_image()
                image.save(output_path)

        return {
            "status": "success",
            "diagram_path": output_path
        }

    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
