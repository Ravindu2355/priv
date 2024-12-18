import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

async def ask(client: Client, user_id: int, question: str, timeout: int = 30):
    """
    Simulate ask() functionality using a while loop to check for the response.
    """
    response_event = False
    user_response = None
    handler_ref = None

    # Send the question to the user
    await client.send_message(user_id, question)

    # Define a custom message handler to capture the user's response
    def on_message(client, message: Message):
        nonlocal user_response, response_event
        if message.chat.id == user_id:
            user_response = message.text
            response_event = True  # Signal that the response is received

    # Register the handler
    handler_ref = client.add_handler(filters.chat(user_id) & filters.text, on_message)

    start_time = asyncio.get_event_loop().time()

    # Wait for the response with a while loop to handle the timeout
    while not response_event:
        elapsed_time = asyncio.get_event_loop().time() - start_time
        if elapsed_time > timeout:
            await client.send_message(user_id, "⏳ You took too long to respond!")
            user_response = None
            break
        await asyncio.sleep(1)  # Sleep for a short period to avoid blocking the event loop

    # Clean up the handler
    if handler_ref:
        client.remove_handler(handler_ref)

    return user_response