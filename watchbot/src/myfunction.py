import logging

import telegram
from telegram import Message, Update
from telegram.ext import CallbackContext
from typing import Optional
from storage import SQLite3_Storage
from model import CompactMessage

logger = logging.getLogger(__name__)
storage = SQLite3_Storage(f"/file/memory.db", overwrite=True)


def extract_text_message(message: Message, edited: bool = False) -> CompactMessage:
    msg = CompactMessage(
            identifier=f"{message.chat.id}/{message.message_id}",
            text=message.text,
            chattype=message.chat.type,
            chatid=message.chat.id,
            chatname=message.chat.title,
            userid=message.from_user.id,
            username=message.from_user.username,
            message_id=message.message_id,
            lastUpdated=str(message.date),
            edited=edited
        )
    return msg


async def middleware_function(update: Update, context: CallbackContext) -> None:
    logger.info(f"\nMiddleware Function => Update: {update}")
    message: Optional[telegram.Message] = getattr(update, "message", None)
    edited_message: Optional[telegram.EditedMessage] = getattr(update, "edited_message", None)
    if message:
        conversation = extract_text_message(message, False)
        storage.set(conversation.identifier, conversation.to_dict())
    elif edited_message:
        conversation = extract_text_message(edited_message, True)
        storage.set(conversation.identifier, conversation.to_dict())
    else:
        logger.error(f"\nException => Update: {update}")
        
        
async def error_handler(update: object, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    logger.error(msg="Update: ", exc_info=str(update))


async def retrieve_handler(update: Update, context: CallbackContext) -> None:
    chatid = update.message.chat.id
    keys = storage.keys()
    keys = list(filter(lambda x: x.startswith(f"{chatid}/"), keys))
    result_string = "===== BEG ===="
    for key in keys:
        try:
            result = storage.get(key)
            # Challenge the existence of a message
            _ = await context.bot.forward_message(chat_id=75316412, message_id=result['message_id'], from_chat_id=result['chatid'], disable_notification=True)
            result_string += f"\n@{result['lastUpdated']} => {result['text']}"
        except telegram.error.BadRequest as bad_request:
            # Message has been deleted
            logger.error(f"Failed to forward message({key}): {bad_request}")
    result_string += "\n===== END ===="
    await update.message.reply_text(result_string)


async def help_handler(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("https://github.com/JonahTzuChi/watchbot")
