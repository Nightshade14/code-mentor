from fastapi import FastAPI
from pydantic import BaseModel, Field
from helper import extract_repo_knowledge
from google import genai
from google.genai import types
from typing import List
from dotenv import load_dotenv
load_dotenv()
import json
import graphviz

class Relationship(BaseModel):
    source: str = Field(description="The source entity (Class, Function, or Service). Use CamelCase.")
    target: str = Field(description="The target entity being called (Database, API, or Class). Use CamelCase.")
    label: str = Field(description="The relationship type (calls, reads_from, writes_to, depends_on). Max 3 words.")

class KnowledgeGraph(BaseModel):
    relationships: List[Relationship] = Field(description="A list of all directed edges extracted from the code.")

def find_relationships(knowledge: dict):
    """
    Create a knowledge graph by identifying nodes and edges from the knowledge dictionary.
    """

    system_prompt = """
    You are an Expert Software Architect and Knowledge Graph Engineer. Your task is to extract a semantic "Dependency Graph" from the JSON code representation provided by the user.

    **YOUR GOAL:**
    Convert the hierarchical JSON data provided by the user into a dictionary of relationships.

    **ENTITY EXTRACTION RULES:**
    1. **Source Entities:** Active agents (Classes like `PaymentService`, Functions like `process_order`).
    2. **Target Entities:** Systems being called.
    * *Internal:* Other classes/functions in the data.
    * *External:* Libraries/APIs (e.g., `stripe`, `boto3`, `requests`).
    * *Normalization:* Convert `stripe.Charge.create` -> `StripeAPI`. Convert `boto3.client` -> `AWS_S3`. Convert `db.query` -> `Database`.

    **RELATIONSHIP INFERENCE RULES (Edge Labels):**
    - **Standard Call:** A calls B -> label: `calls`.
    - **Data Flow:** Reading data -> label: `reads_from`.
    - **Data Mutation:** Writing data -> label: `writes_to`.
    - **Dependency:** Imports/Instantiations -> label: `depends_on`.

    **FILTERING (CRITICAL):**
    - **IGNORE** technical noise: `print`, `logging`, `len`, `str`, `int`, `list`.
    - **IGNORE** internal language features unless they represent major logic.

    **CRITICAL COMPATIBILITY RULES:**
    1. **Clean Names:** Use CamelCase (e.g., "PaymentService"). No spaces or special chars.
    2. **Short Labels:** Max 3 words.
    3. **Direction:** Always Source -> Target.
    """

    prompt = f"""
    **INPUT DATA (JSON):**
    {knowledge}
    """

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-09-2025",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=KnowledgeGraph
            )
        )
    except Exception as e:
        print(f"LLM API call Error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }  

    with open('relationships.json', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    try:
        # data_dict = json.loads(response.text)
        # result = KnowledgeGraph.model_validate(data_dict)
        return response.text

    except Exception as e:
        print(f"Error: {e}")
        



def render_architecture_graph(llm_output, output_filename="architecture_diagram"):
    """
    Renders a Graphviz diagram from the LLM's JSON output.
    
    Args:
        llm_output (dict): The JSON object containing "relationships"

        output_filename (str): Base name for the output file (no extension)
    """
    
    dot = graphviz.Digraph(comment='Architecture Auto-Draftsman')
    
    dot.attr(rankdir='LR')           # Left-to-Right layout (Input -> Logic -> Data)
    dot.attr(splines='ortho')        # Orthogonal lines (Right angles, circuit-board look)
    dot.attr('node', 
            shape='box', 
            style='filled', 
            fillcolor='#E8F5E9',
            fontname='Helvetica',
            penwidth='1.5')
    dot.attr('edge', 
            fontname='Helvetica', 
            fontsize='10',
            color='#455A64',
            arrowsize='0.8')

    def get_shape_and_color(node_name):
        name_lower = node_name.lower()
        
        # Rule 1: Databases -> Cylinders (Yellow/Gold)
        if any(x in name_lower for x in ['db', 'database', 'sql', 'store', 'redis']):
            return 'cylinder', '#FFF9C4'
        
        # Rule 2: External APIs -> Component/Tab (Light Blue)
        if any(x in name_lower for x in ['api', 'stripe', 'aws', 's3', 'external']):
            return 'component', '#E1F5FE'
            
        # Rule 3: Frontend/Users -> Oval (Light Grey)
        if any(x in name_lower for x in ['user', 'client', 'frontend', 'app']):
            return 'oval', '#F5F5F5'
            
        # Default: Services -> Box (Light Green)
        return 'box', '#E8F5E9'

    if isinstance(llm_output, str):
        try:
            llm_output = json.loads(llm_output)
        except json.JSONDecodeError:
            print("Error: llm_output is not a valid JSON string.")
            return None

    edges = llm_output.get("relationships", {})

    added_nodes = set()

    for edge_dict in edges:
        # Style Source Node
        if edge_dict["source"] not in added_nodes:
            shape, color = get_shape_and_color(edge_dict["source"])
            dot.node(edge_dict["source"], shape=shape, fillcolor=color)
            added_nodes.add(edge_dict["source"])
        
        # Style Target Node
        if edge_dict["target"] not in added_nodes:
            shape, color = get_shape_and_color(edge_dict["target"])
            dot.node(edge_dict["target"], shape=shape, fillcolor=color)
            added_nodes.add(edge_dict["target"])
        
        # Add Edge
        dot.edge(edge_dict["source"], edge_dict["target"], label=edge_dict["label"])

    try:
        output_path = dot.render(output_filename, format='png', view=False)
        success_msg = "Success! Diagram generated"
        print(success_msg)
        return success_msg
    except Exception as e:
        error_msg = f"Error rendering graph: {e}"
        print(error_msg)


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
        relationships = find_relationships(knowledge)
        final_result = KnowledgeGraph(relationships=relationships)

        return {
            "status": "success",
            "knowledge": final_result
        }

    except Exception as e:
        print(f"Error extracting knowledge: {e}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
