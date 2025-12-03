import asyncio
import os
import sys
import logging
from unittest.mock import MagicMock, AsyncMock
from dotenv import load_dotenv

# Set up logging to see debug output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import Database
from src.llm import LLMClient
from src.cogs.chat import Chat

# Load env
load_dotenv()

async def main():
    print("Initializing Test Environment...")
    
    # Setup DB
    db_path = "data/test_brrr.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = Database(db_path)
    await db.init()
    
    # Setup LLM
    api_key = os.getenv('REQUESTY_API_KEY')
    if not api_key:
        print("Error: REQUESTY_API_KEY not found")
        return
        
    llm = LLMClient(api_key, model="openai/gpt-4o-mini")
    
    # Mock Bot
    bot = MagicMock()
    bot.db = db
    bot.llm = llm
    bot.user.avatar.url = "http://placeholder.com/avatar.png"
    
    # Initialize Chat Cog
    chat_cog = Chat(bot)
    
    print("\n=== Local Chat Test (Type 'quit' to exit) ===")
    print("You can test tools like: 'Create a task for project 1 called Test Task'")
    
    # Create a dummy project for testing tools
    await db.create_project(guild_id=123, title="Test Project", description="A test project")
    print("Created 'Test Project' (ID: 1) for testing.")
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['quit', 'exit']:
            break
            
        # Mock Message
        message = AsyncMock()
        message.content = user_input
        message.author.id = 999
        message.author.display_name = "TestUser"
        message.author.bot = False
        message.guild.id = 123
        message.channel.id = 456
        message.mentions = []
        
        # Mock channel.typing context manager
        typing_cm = MagicMock()
        typing_cm.__aenter__ = AsyncMock(return_value=None)
        typing_cm.__aexit__ = AsyncMock(return_value=None)
        message.channel.typing = MagicMock(return_value=typing_cm)
        
        # Mock reply/send
        async def mock_reply(content, mention_author=False):
            print(f"Bot: {content}")
        
        async def mock_send(content):
            print(f"Bot (cont): {content}")
            
        message.reply = mock_reply
        message.channel.send = mock_send
        
        # Run handler
        await chat_cog.handle_mention(message)

    # Cleanup
    await llm.close()
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(main())
