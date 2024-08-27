import logging
import os
from time import time
import telegram
from telegram import Message, Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from typing import Optional
from storage import SQLite3_Storage
from model import CompactMessage

logger = logging.getLogger(__name__)
master = os.getenv("MASTER_TLG_ID", 0)
assert master != 0


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
        storage = SQLite3_Storage(f"/file/{conversation.chatid}.db", overwrite=False)
        storage.set(conversation.identifier, conversation.to_dict())
    elif edited_message:
        conversation = extract_text_message(edited_message, True)
        storage = SQLite3_Storage(f"/file/{conversation.chatid}.db", overwrite=False)
        storage.set(conversation.identifier, conversation.to_dict())
    else:
        logger.error(f"\nException => Update: {update}")
        
        
async def error_handler(update: object, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    logger.error(msg="Update: ", exc_info=str(update))


def to_display(data: dict) -> str:
    assert not data['deleted']
    return f"\n<strong>{data['username']}</strong> => [{data['text']}]@{data['lastUpdated']}" + (" (edited)" if data['edited'] else "")


async def retrieve_via_forward(update: Update, context: CallbackContext) -> None:
    chatid = update.message.chat.id
    storage = SQLite3_Storage(f"/file/{chatid}.db", overwrite=False)
    keys = storage.keys()
    keys = list(filter(lambda x: x.startswith(f"{chatid}/"), keys))
    for key in keys:
        try:
            result = storage.get(key)
            # Challenge the existence of a message
            _ = await context.bot.forward_message(chat_id=master, message_id=result['message_id'], from_chat_id=result['chatid'], disable_notification=True)
        except telegram.error.BadRequest as bad_request:
            # Message has been deleted
            result['deleted'] = True
            storage.set(key, result)
            logger.error(f"Failed to forward message({key}): {bad_request}")
    
    export_path = f"/file/{chatid}_{int(time())}.csv"
    storage.export_csv(export_path)
    await update.message.reply_document(export_path, parse_mode=ParseMode.HTML)


async def retrieve_via_copy(update: Update, context: CallbackContext) -> None:
    chatid = update.message.chat.id
    storage = SQLite3_Storage(f"/file/{chatid}.db", overwrite=False)
    keys = storage.keys()
    keys = list(filter(lambda x: x.startswith(f"{chatid}/"), keys))
    for key in keys:
        try:
            result = storage.get(key)
            # Challenge the existence of a message
            _ = await context.bot.copy_message(chat_id=master, message_id=result['message_id'], from_chat_id=result['chatid'])
        except telegram.error.BadRequest as bad_request:
            # Message has been deleted
            result['deleted'] = True
            storage.set(key, result)
            logger.error(f"Failed to copy message({key}): {bad_request}")
    
    export_path = f"/file/{chatid}_{int(time())}.csv"
    storage.export_csv(export_path)
    await update.message.reply_document(export_path, parse_mode=ParseMode.HTML)


async def help_handler(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("https://github.com/JonahTzuChi/watchbot")
