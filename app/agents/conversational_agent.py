from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from app.tools.garmin_tools import get_activities, get_sleep_data, get_stress_data, get_user_info
from app.tools.workout_tools import create_fit_file
from app.tools.date_tools import get_current_date
from app.tools.profiling_tools import analyze_and_summarize_user_activities
from app.tools.user_tools import delete_user_data
from app.tools.recovery_tools import assess_recovery_status
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Pydantic models for tool arguments
class GetActivitiesArgs(BaseModel):
    start_date: str = Field(description="The start date in ISO format (YYYY-MM-DD).")
    end_date: str = Field(description="The end date in ISO format (YYYY-MM-DD).")

class GetSleepDataArgs(BaseModel):
    date: str = Field(description="The date in ISO format (YYYY-MM-DD).")

class GetStressDataArgs(BaseModel):
    date: str = Field(description="The date in ISO format (YYYY-MM-DD).")

class CreateFitFileArgs(BaseModel):
    workout_steps: Optional[List[Dict]] = Field(default=None, description="A list of workout steps. If not provided, a default workout will be created.")

def create_conversational_agent(user_id: int):
    """
    Creates a conversational agent for a user.
    """

    # Helper functions to pass user_id to the tools
    def get_activities_for_user(start_date: str, end_date: str) -> list:
        return get_activities(user_id=user_id, start_date=start_date, end_date=end_date)

    def get_sleep_data_for_user(date: str) -> dict:
        return get_sleep_data(user_id=user_id, date=date)

    def get_stress_data_for_user(date: str) -> dict:
        return get_stress_data(user_id=user_id, date=date)

    def get_user_info_for_user() -> dict:
        return get_user_info(user_id=user_id)

    def analyze_activities_for_user() -> str:
        return analyze_and_summarize_user_activities(user_id=user_id)

    def delete_user_data_for_user() -> str:
        return delete_user_data(user_id=user_id)

    def assess_recovery_for_user() -> str:
        return assess_recovery_status(user_id=user_id)

    tools = [
        StructuredTool.from_function(
            name="get_current_date",
            func=get_current_date,
            description="Returns the current date in ISO format (YYYY-MM-DD).",
        ),
        StructuredTool.from_function(
            name="get_activities",
            func=get_activities_for_user,
            description="Fetch activities from Garmin Connect within a date range. Returns a compact summary of activities with dates, types, distances, durations, and key metrics like heart rate and pace.",
            args_schema=GetActivitiesArgs,
        ),
        StructuredTool.from_function(
            name="get_sleep_data",
            func=get_sleep_data_for_user,
            description="Fetch sleep data for a specific date. Returns a summary including total sleep time, deep/light/REM sleep phases, awake time, and sleep score.",
            args_schema=GetSleepDataArgs,
        ),
        StructuredTool.from_function(
            name="get_stress_data",
            func=get_stress_data_for_user,
            description="Fetch stress data for a specific date. Returns average and max stress levels, plus time spent in rest, low, medium, and high stress states.",
            args_schema=GetStressDataArgs,
        ),
        StructuredTool.from_function(
            name="get_user_info",
            func=get_user_info_for_user,
            description="Fetch user's full name from Garmin Connect.",
        ),
        StructuredTool.from_function(
            name="create_fit_file",
            func=create_fit_file,
            description="""Creates a .fit file from a list of workout steps. 
            Each step should be a dictionary with keys: wkt_step_name, duration_type, duration_value, target_type, target_value.
            Example:
            {
                "workout_steps": [
                    {
                        "wkt_step_name": "Warm-up",
                        "duration_type": "time",
                        "duration_value": 600,  # in seconds
                        "target_type": "heart_rate",
                        "target_value": 120
                    },
                    {
                        "wkt_step_name": "Ride",
                        "duration_type": "distance",
                        "duration_value": 10000,  # in meters
                        "target_type": "power",
                        "target_value": 200
                    }
                ]
            }
            """,
            args_schema=CreateFitFileArgs,
        ),
        StructuredTool.from_function(
            name="analyze_and_summarize_user_activities",
            func=analyze_activities_for_user,
            description="Analyzes the user's activities and provides a summary of their profile.",
        ),
        StructuredTool.from_function(
            name="assess_recovery_status",
            func=assess_recovery_for_user,
            description="IMPORTANT: Use this tool BEFORE creating any workout. Checks yesterday's sleep and stress data to assess if the user is well-recovered. Returns a recovery score and training recommendations. Always call this before creating a .fit file.",
        ),
        StructuredTool.from_function(
            name="delete_user_data",
            func=delete_user_data_for_user,
            description="Deletes all data associated with the user.",
        ),
    ]

    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", """You are a helpful AI sports coach. You can help users with their activities, sleep, stress, and create workout plans.

Important guidelines:
- All tools return pre-formatted, human-readable summaries (not raw JSON)
- The data you receive is already filtered and compact
- You can use this data directly in your responses
- Use the get_current_date tool when users ask for data "until today" or "this week"

⚠️ CRITICAL WORKFLOW FOR WORKOUT CREATION:
1. When a user asks for a workout or training plan, you MUST FIRST call assess_recovery_status
2. Review the recovery assessment (sleep quality, stress levels, recovery score)
3. Based on the recovery status:
   - WELL RECOVERED (5-6/6): Create intensive/challenging workout as requested
   - MODERATE RECOVERY (3-4/6): Create moderate intensity workout, warn user about recovery
   - POOR RECOVERY (0-2/6): Suggest rest day or very light activity, explain why
4. Only then create the .fit file, adjusted to their recovery status
5. Always explain to the user why you're adjusting the workout based on their recovery

- When a workout file is created, inform the user that the file is ready to download
- Be conversational, supportive, and prioritize user safety and recovery"""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm_with_tools = llm.bind_tools(tools)

    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                x["intermediate_steps"]
            ),
            "chat_history": lambda x: x["chat_history"],
        }
        | prompt
        | llm_with_tools
        | OpenAIToolsAgentOutputParser()
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)

    return agent_executor
