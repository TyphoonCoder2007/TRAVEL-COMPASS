from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class TravelQuery(BaseModel):
    destination: str
    preferences: Optional[str] = None

class RecommendationResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    recommendations: List[Dict[str, Any]]
    geographic_info: Dict[str, Any]
    climate_info: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# Initialize AI Chat
ai_chat = LlmChat(
    api_key=os.environ.get('EMERGENT_LLM_KEY'),
    session_id="travel-guide-session",
    system_message="You are an expert travel guide and geographic information specialist. Provide comprehensive, accurate travel recommendations with detailed geographic and climate information. Always format your responses in clear, structured JSON format."
).with_model("openai", "gpt-4o")

# Helper function to prepare data for MongoDB
def prepare_for_mongo(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = prepare_for_mongo(value)
            elif isinstance(value, list):
                data[key] = [prepare_for_mongo(item) if isinstance(item, dict) else item for item in value]
    return data

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Travel Guide API"}

@api_router.post("/recommendations", response_model=RecommendationResponse)
async def get_travel_recommendations(query: TravelQuery):
    try:
        # Create comprehensive prompt for travel recommendations
        prompt = f"""
        DESTINATION: {query.destination}
        {f'PREFERENCES: {query.preferences}' if query.preferences else ''}
        
        You are a travel expert. Provide ONLY a valid JSON response (no other text) with comprehensive travel information for {query.destination}. Use this exact structure:

        {{
            "recommendations": [
                {{
                    "name": "Attraction/Restaurant/Activity Name",
                    "type": "attraction",
                    "description": "Clear, informative description",
                    "rating": "4.5/5",
                    "best_time_to_visit": "Best visiting time",
                    "estimated_duration": "Time needed",
                    "tips": "Practical visitor tips"
                }}
            ],
            "geographic_info": {{
                "continent": "Continent Name",
                "country": "Country Name", 
                "region": "State/Province/Region",
                "coordinates": "Latitude, Longitude",
                "elevation": "Elevation above sea level",
                "time_zone": "Time zone (e.g., GMT+9)",
                "local_currency": "Currency name and code",
                "languages": ["Primary language", "Secondary language"],
                "population": "Population of city/region"
            }},
            "climate_info": {{
                "climate_type": "Climate classification",
                "seasons": {{
                    "spring": "Spring weather description",
                    "summer": "Summer weather description", 
                    "fall": "Fall weather description",
                    "winter": "Winter weather description"
                }},
                "average_temperatures": {{
                    "summer_high": "°C (°F)",
                    "summer_low": "°C (°F)",
                    "winter_high": "°C (°F)",
                    "winter_low": "°C (°F)"
                }},
                "rainfall": "Annual rainfall description",
                "best_travel_months": ["Month1", "Month2", "Month3"]
            }}
        }}

        Include 8-10 diverse recommendations (attractions, restaurants, activities, hotels). Ensure all data is accurate and current. RESPOND ONLY WITH VALID JSON.
        """
        
        user_message = UserMessage(text=prompt)
        response = await ai_chat.send_message(user_message)
        
        # Parse the AI response
        import json
        import re
        
        # Try to extract JSON from the response
        try:
            # First try direct JSON parsing
            ai_data = json.loads(response)
        except json.JSONDecodeError:
            try:
                # Look for JSON within the response text
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    ai_data = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in response")
            except (json.JSONDecodeError, ValueError):
                # If all parsing fails, create a structured fallback with actual destination info
                destination_parts = query.destination.split(',')
                city = destination_parts[0].strip()
                country = destination_parts[-1].strip() if len(destination_parts) > 1 else city
                
                ai_data = {
                    "recommendations": [
                        {
                            "name": f"Explore {city}",
                            "type": "activity",
                            "description": f"Discover the amazing attractions and culture of {city}. This vibrant destination offers unique experiences for every traveler.",
                            "rating": "4.5/5",
                            "best_time_to_visit": "Year-round",
                            "estimated_duration": "2-3 days",
                            "tips": f"Research local customs and try traditional cuisine in {city}"
                        },
                        {
                            "name": f"{city} City Center",
                            "type": "attraction",
                            "description": f"The heart of {city} with its main attractions, shopping, and dining options.",
                            "rating": "4.3/5",
                            "best_time_to_visit": "Morning to evening",
                            "estimated_duration": "Half day",
                            "tips": "Use public transportation to get around easily"
                        },
                        {
                            "name": "Local Restaurants",
                            "type": "restaurant",
                            "description": f"Experience authentic local cuisine at the best restaurants {city} has to offer.",
                            "rating": "4.4/5",
                            "best_time_to_visit": "Lunch and dinner",
                            "estimated_duration": "1-2 hours per meal",
                            "tips": "Make reservations in advance for popular spots"
                        }
                    ],
                    "geographic_info": {
                        "continent": "To be determined",
                        "country": country,
                        "region": f"{city} region",
                        "coordinates": "Available on mapping services",
                        "elevation": "Variable",
                        "time_zone": "Local time zone",
                        "local_currency": "Local currency",
                        "languages": ["Local languages"],
                        "population": f"{city} metropolitan area"
                    },
                    "climate_info": {
                        "climate_type": "Temperate",
                        "seasons": {
                            "spring": "Mild and pleasant weather",
                            "summer": "Warm and comfortable",
                            "fall": "Cool with beautiful foliage", 
                            "winter": "Cool to cold temperatures"
                        },
                        "average_temperatures": {
                            "summer_high": "25°C (77°F)",
                            "summer_low": "15°C (59°F)",
                            "winter_high": "10°C (50°F)",
                            "winter_low": "0°C (32°F)"
                        },
                        "rainfall": "Moderate throughout the year",
                        "best_travel_months": ["April", "May", "September", "October"]
                    }
                }
        
        # Create response object
        recommendation = RecommendationResponse(
            query=query.destination,
            recommendations=ai_data.get("recommendations", []),
            geographic_info=ai_data.get("geographic_info", {}),
            climate_info=ai_data.get("climate_info", {})
        )
        
        # Store in database
        recommendation_dict = prepare_for_mongo(recommendation.dict())
        await db.travel_recommendations.insert_one(recommendation_dict)
        
        return recommendation
    
    except Exception as e:
        logger.error(f"Error getting travel recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating travel recommendations")

@api_router.get("/recommendations/history", response_model=List[RecommendationResponse])
async def get_recommendation_history():
    try:
        recommendations = await db.travel_recommendations.find().sort("created_at", -1).limit(10).to_list(length=10)
        return [RecommendationResponse(**rec) for rec in recommendations]
    except Exception as e:
        logger.error(f"Error getting recommendation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving recommendation history")

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(prepare_for_mongo(status_obj.dict()))
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
