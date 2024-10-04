import logging
import os
from time import time
import telegram
from telegram import Message, Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from typing import Optional
from storage import SQLite3_Storage
from model import CompactMessage, Media

logger = logging.getLogger(__name__)
master = os.getenv("MASTER_TLG_ID", 0)
assert master != 0


def extract_media(message: Message) -> Media:
    """Extract media information from a Message."""
    media = Media(isMedia=False, fileid=None, filename=None, mime_type=None)
    if message.document:
        media = Media(
            isMedia=True,
            fileid=message.document.file_id,
            filename=message.document.file_name,
            mime_type=message.document.mime_type,
        )
    elif message.photo:
        media = Media(
            isMedia=True,
            fileid=message.photo[-1].file_id,
            filename=message.caption,
            mime_type=None,
        )
    elif message.video:
        media = Media(
            isMedia=True,
            fileid=message.video.file_id,
            filename=message.video.file_name,
            mime_type=message.video.mime_type,
        )
    elif message.audio:
        media = Media(
            isMedia=True,
            fileid=message.audio.file_id,
            filename=message.audio.file_name,
            mime_type=message.audio.mime_type,
        )
    elif message.voice:
        media = Media(
            isMedia=True,
            fileid=message.voice.file_id,
            filename=message.voice.file_name,
            mime_type=message.voice.mime_type,
        )
    return media


def parse_message(message: Message, edited: bool = False) -> CompactMessage:
    """
    Parse a Message object from Telegram API into a CompactMessage object.

    Args:
    - message (Message): The Message object to parse.
    - edited (bool, optional): If the message is edited. Defaults to False.

    Returns:
    - CompactMessage: The parsed CompactMessage object.

    Notes:
    Fields `isForwarded`, `author` and `isBot` are only applicable when it's a forwarded message.
    """
    msg = CompactMessage(
        identifier=f"{message.chat.id}/{message.message_id}",
        text=message.text if message.text else message.caption,
        chattype=message.chat.type,
        chatid=message.chat.id,
        chatname=message.chat.title,
        userid=message.from_user.id,
        username=message.from_user.username or f"{message.from_user.first_name} {message.from_user.last_name}",
        message_id=message.message_id,
        created=str(message.date),
        lastUpdated=str(message.date),
        edited=edited,
        isForwarded=False,
        media=extract_media(message),
    )
    # Handle Forwarded Message
    forward_origin = getattr(message, "forward_origin", None)
    if forward_origin:
        msg.isForwarded = True
        if forward_origin.type is telegram.constants.MessageOriginType.HIDDEN_USER:
            msg.author = forward_origin.sender_user_name
        else:
            msg.author = forward_origin.sender_user.username or f"{forward_origin.sender_user.first_name} {forward_origin.sender_user.last_name}"
            msg.isBot = forward_origin.sender_user.is_bot

    return msg


async def middleware_function(update: Update, context: CallbackContext) -> None:
    """
    Middleware function to intercept all incoming messages and store them in an SQLite database.

    Args:
    - update (Update): The incoming update object.
    - context (CallbackContext): The context object passed to the middleware function.

    Returns:
    - None

    Notes:
    - The middleware function will store the message in an SQLite database.
    - If the message body is not found, an error message will be logged.
    """
    logger.info(f"\nMiddleware Function => Update: {update}")

    message: Optional[telegram.Message] = getattr(update, "message", None)
    edited_message: Optional[telegram.Message] = getattr(
        update, "edited_message", None
    )
    if not message and not edited_message:
        logger.error(
            f"\nException: [Message Body Not Found]=> Update: {update}")
        return None

    if edited_message:
        compact_message = parse_message(edited_message, True)
    else:
        compact_message = parse_message(message, False)
    storage = SQLite3_Storage(
        f"/file/{compact_message.chatid}.db", overwrite=False)
    storage.set(compact_message.identifier, compact_message.to_dict())


async def error_handler(update: object, context: CallbackContext):
    logger.error(msg="Exception while handling an update:",
                 exc_info=context.error)
    logger.info(f"\nError Handler => Update: {update}")


def to_display(data: dict) -> str:
    assert not data["deleted"]
    return (
            f"\n<strong>{data['username']}</strong> => [{data['text']}]@{data['lastUpdated']}"
            + (" (edited)" if data["edited"] else "")
    )


async def help_handler(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("https://github.com/JonahTzuChi/watchbot")


async def export_handler(update: Update, context: CallbackContext) -> None:
    """
    Export chat history in csv format.

    Retrieve chat history from the specified chat through `forward_message`.
    Can choose to export only recent messages or all messages.
    Due to the limitation of Telegram API, the bot will not be notified when a message is deleted.
    Therefore, this program iteratively challenges the existence of a message.

    Along this time, the program will also try to retrieve previously uncought messages either due to bot downtime or lost of .db file.

    This function retrieves the chat history from a specified chat using `forward_message` method.
    It allows the user to export either only recent messages or the entire chat history.
    Due to Telegram API limitations, the bot cannot detect when a message is deleted directly;
    thus, the program iteratively checks the existence of each message to handle deletions.

    Additionally, this function attempts to retrieve any messages that were missed,
    potentially due to bot downtime or the loss of the database file.

    Limitations:
    - When forwarding messages, the Telegram API changes `msg.chat` to represent the bot
      and `msg.from_user` to represent the bot's user, masking the original sender's identity.
    - In group chats, forwarding a message does not capture the identity of the user who forwarded it;
      instead, it displays the original sender and the bot.

    Side Effects:
    - This function forward messages to a master chat to verify their existence.
    - It stores chat messages in an SQLite database for persistent storage.

    Note:
    - This function challenges the existence of messages by attempting to forward them.
    - It may mark messages as deleted if the forwarding fails.
    """
    # Configuration
    recent: bool = False

    caller_name = (
            update.message.from_user.username
            or f"{update.message.from_user.first_name} {update.message.from_user.last_name}"
    )
    chatid = update.message.chat.id
    storage = SQLite3_Storage(f"/file/{chatid}.db", overwrite=False)

    messageid = update.message.message_id
    chattype = update.message.chat.type
    chatname = update.message.chat.title or (
        f"{update.message.chat.first_name} {update.message.chat.last_name}"
    )
    # Determine search range
    if recent:
        search_from = messageid - 20
    else:
        search_from = 0
    search_to = messageid
    for i in range(search_from, search_to):
        try:
            key = f"{chatid}/{i}"
            result = storage.get(key)
            # Challenge the existence of a message
            msg = await context.bot.forward_message(
                chat_id=master,
                message_id=i,
                from_chat_id=chatid,
                disable_notification=True,
            )
            if result is None:
                if (
                        msg.forward_origin.type
                        is telegram.constants.MessageOriginType.HIDDEN_USER
                ):
                    forward_origin: telegram.MessageOriginHiddenUser = msg.forward_origin
                    forward_sender_name = forward_origin.sender_user_name
                    is_bot = False
                else:
                    forward_origin: telegram.MessageOriginUser = msg.forward_origin
                    forward_sender_name = (
                            f"{forward_origin.sender_user.first_name} {forward_origin.sender_user.last_name}"
                            or forward_origin.sender_user.username
                    )
                    is_bot = forward_origin.sender_user.is_bot

                if (
                        update.message.chat.type is telegram.constants.ChatType.PRIVATE
                        and forward_sender_name != caller_name
                ):
                    is_forwarded = True
                else:
                    is_forwarded = False  # forward_sender_name[-3:].lower() == "bot":

                # Set username and userid as None since we cannot discern it's original sender.
                # To be honest, we do not know the original created datetime
                result = CompactMessage(
                    identifier=key,
                    text=msg.text or msg.caption,
                    chattype=chattype,
                    chatid=chatid,
                    chatname=chatname,
                    userid=None,
                    username=None,
                    message_id=i,
                    created=None,
                    lastUpdated=str(msg.forward_origin.date),
                    edited=False,
                    deleted=False,
                    isForwarded=is_forwarded,
                    author=forward_sender_name,
                    isBot=is_bot,
                    media=extract_media(msg),
                )
                storage.set(key, result.to_dict())
        except telegram.error.BadRequest as bad_request:
            if result:
                # Message has been deleted
                result["deleted"] = True
                storage.set(key, result)
                logger.error(f"Failed to copy message({key}): {bad_request}")
            else:
                logger.error(f"Failed to copy message({key}): {bad_request}")

    if update.message.chat.title:
        export_path = f"/file/{update.message.chat.title}_{int(time())}.csv"
    else:
        export_path = f"/file/{update.message.chat.id}_{int(time())}.csv"
    storage.export_csv(export_path)
    reply_msg = await update.message.reply_document(
        export_path, parse_mode=ParseMode.HTML
    )
    conversation = CompactMessage(
        identifier=f"{reply_msg.chat.id}/{reply_msg.message_id}",
        text=None,
        chattype=reply_msg.chat.type,
        chatid=reply_msg.chat.id,
        chatname=reply_msg.chat.title or f"{reply_msg.chat.first_name} {reply_msg.chat.last_name}",
        userid=reply_msg.from_user.id,
        username=reply_msg.from_user.username,
        message_id=reply_msg.message_id,
        created=str(reply_msg.date),
        lastUpdated=str(reply_msg.date),
        edited=False,
        deleted=False,
        isForwarded=False,
        author=None,
        isBot=False,
        media=extract_media(reply_msg),
    )
    storage = SQLite3_Storage(f"/file/{conversation.chatid}.db", overwrite=False)
    storage.set(conversation.identifier, conversation.to_dict())


async def message_handler(update: Update, context: CallbackContext) -> None:
    # await update.message.reply_text("=== COPY ===")
    pass
