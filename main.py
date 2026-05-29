import os
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from notion_client import Client 
import sys

load_dotenv()

# error handling
try:
    llm_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
except KeyError as e:
    print(f"Missing environment variable: {e}")
    exit(1)

class Tasks(BaseModel):
    title:str=Field(description="The title of the task")
    status:str=Field(description="The status of the task")
    deadline:str | None = Field(description="Any implied deadline or timeline, if mentioned. E.g., 'Friday', 'Q3', 'Tonight'.")
    priority:str = Field(default="Medium", description="The priority of the task: 'High', 'Medium', 'Low'.")
    project_title: str | None = Field(description="The title of the parent project this task belongs to, if any.")

class Projects(BaseModel):
    name:str=Field(description="the name of the project")
    objective:str | None=Field(description="The high level objective of the project")

# now connecting both databases
class BraindumpExtraction(BaseModel):
    projects : list[Projects] = Field(description="A list of distinct projects extracted from the braindump.")
    tasks : list[Tasks] = Field(description="A list of actionable tasks extracted from the braindump.")

# LLM extraction:
def extract_braindump(text : str) -> BraindumpExtraction:
    print("Processing Braindump through Gemini........")
    prompt = f"""You are an expert executive assistant. Analyze the following braindump and extract the underlying structured data.
    Identify any overarching Projects being mentioned, and any specific actionable Tasks.
    Link tasks to projects using the project_title field where applicable.
    
    Braindump:
    "{text}"
    """

    # boilerplate for gemini
    response = llm_client.models.generate_content(
        model = "gemini-2.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type" : "application/json",  
            "response_schema" : BraindumpExtraction,
        }

    )
    return response.parsed

# my_braindump = """ I need to finalize the product proposal for Codénix by tonight. Also have to review 
# the new Agentic AI coursework modules this weekend. Remind me to look up the chords for 
# that Zubeen Garg song and update the Bio-Mechanical Guitar AI repo on GitHub with the 
# latest tablature scripts.
# """
# structured_data = extract_braindump(my_braindump)
# print(structured_data)


# injecting to notion
def push_to_notion_database(task: Tasks):
    print(f"🚀 Pushing task to Notion: '{task.title}' [{task.project_title or 'No Project'}]")
    
    # Building properties payload matching your database schema
    payload = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": task.title
                    }
                }
            ]
        },
        "Priority": {
            "select": {
                "name": task.priority
            }
        },
        "Project": {
            "rich_text": [
                {
                    "text": {
                        "content": task.project_title or ""
                    }
                }
            ]
        },
        "Status": {
            "status": {
                "name": "Not started"
            }
        }
    }
    
    try:
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=payload
        )
        print(f"✅ Successfully created page for: {task.title}")
    except Exception as e:
        error_msg = str(e)
        if "property that exists" in error_msg:
            print(f"⚠️ Missing columns in Notion database, falling back to 'Name' only...")
            fallback_payload = {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": task.title
                            }
                        }
                    ]
                }
            }
            try:
                notion.pages.create(
                    parent={"database_id": DATABASE_ID},
                    properties=fallback_payload
                )
                print(f"✅ Successfully created page (Name only) for: {task.title}")
            except Exception as fallback_err:
                print(f"❌ Notion API Fallback Error for '{task.title}': {fallback_err}")
        else:
            print(f"❌ Notion API Error for '{task.title}': {e}")

if __name__ == "__main__":
    print("--- Notion Braindump Agent Pipeline Initialized ---")
    
    # Prompt the user for input directly in the terminal
    print("\nEnter your text dump below (Press Enter, then Ctrl+D or Ctrl+Z to finish):")
    user_dump = sys.stdin.read().strip()
    
    if not user_dump:
        print("❌ Error: No text input detected.")
        sys.exit(1)
        
    # Execute Pipeline Steps
    extracted_payload = extract_braindump(user_dump)
    
    total_tasks = len(extracted_payload.tasks)
    print(f"\n✨ Extraction Complete! Found {total_tasks} distinct tasks.\n")
    
    for idx, task in enumerate(extracted_payload.tasks, 1):
        print(f"[{idx}/{total_tasks}] Processing...")
        push_to_notion_database(task)
        
    print("\n🎉 All tasks have been successfully processed and pushed to Notion!")