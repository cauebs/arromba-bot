from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from typing import Any

from telegram import ParseMode, Update, User
from telegram.ext import (
    BasePersistence,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    Updater,
)
from telegram.ext.filters import Filters
from telegram.utils.helpers import mention_markdown


def update_subscription(update: Update, context: CallbackContext, status: bool) -> None:
    tags = context.args
    assert tags is not None
    assert len(tags) > 0, "me diz pelo menos uma tag, né"
    assert all(
        tag.startswith("#") for tag in tags
    ), "foi mal, mas tag tem que começar com #"

    user = update.effective_user
    assert user is not None

    assert context.chat_data is not None

    for tag in tags:
        subscribers = context.chat_data.setdefault(tag, {})

        if status:
            subscribers[user.id] = user.username or user.first_name
        else:
            del subscribers[user.id]

    assert update.message is not None
    prefix = "+" if status else "-"
    text = " ".join(prefix + tag for tag in tags)
    update.message.reply_text(text)


def handle_sub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=True)


def handle_unsub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=False)


def handle_text(update: Update, context: CallbackContext) -> None:
    message = update.message
    assert message is not None

    if message.entities is not None:
        hashtags = message.parse_entities(["hashtag"]).values()
    elif message.caption_entities is not None:
        hashtags = message.parse_caption_entities(["hashtag"]).values()

    assert context.chat_data is not None
    tagged = (context.chat_data.get(tag, {}) for tag in hashtags)

    mentions = (
        mention_markdown(id, name)
        for subscribers in tagged
        for id, name in subscribers.items()
    )

    text = " ".join(mentions)
    if text:
        message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def handle_error(update, context: CallbackContext) -> None:
    assert update.message is not None
    update.message.reply_text(str(context.error))


def get_persistence() -> BasePersistence:
    data_dir = Path.home() / f".local/share/{__package__}"
    data_dir.mkdir(parents=True, exist_ok=True)

    filename = data_dir / __package__
    return PicklePersistence(str(filename))


def main() -> None:
    token = environ["TOKEN"]
    updater = Updater(token, persistence=get_persistence())
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("sub", handle_sub))
    dispatcher.add_handler(CommandHandler("unsub", handle_unsub))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_text))
    dispatcher.add_error_handler(handle_error)

    updater.start_polling()


if __name__ == "__main__":
    main()
