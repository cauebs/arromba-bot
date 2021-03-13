from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from typing import Any

from telegram import ParseMode, Update, User, Message
from telegram.ext import (
    BasePersistence,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    Updater,
)
from telegram.ext.filters import Filters, MessageEntity
from telegram.utils.helpers import mention_markdown


def get_hashtags(message: Message) -> list[str]:
    entity_types = [MessageEntity.HASHTAG]
    tags: list[str] = []

    if message.entities is not None:
        tags.extend(message.parse_entities(entity_types).values())

    if message.caption_entities is not None:
        tags.extend(message.parse_caption_entities(entity_types).values())

    return tags


def update_subscription(update: Update, context: CallbackContext, status: bool) -> None:
    assert update.message is not None
    tags = get_hashtags(update.message)

    assert len(tags) > 0, "me diz pelo menos uma tag, né"
    assert all(
        tag.startswith("#") for tag in tags
    ), "foi mal, mas tag tem que começar com #"

    user = update.effective_user
    assert user is not None
    user_name = user.username or user.first_name

    assert context.chat_data is not None

    for tag in tags:
        subscribers = context.chat_data.setdefault(tag, {})

        if status:
            subscribers[user.id] = user_name
        else:
            del subscribers[user.id]

    verb = "adicionadas" if status else "removidas"
    text = f"inscrições {verb} para {user_name}: {' '.join(tags)}"
    update.message.reply_text(text)


def handle_sub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=True)


def handle_unsub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=False)


def handle_list(update: Update, context: CallbackContext) -> None:
    assert context.chat_data is not None
    assert update.effective_user is not None

    subscriptions = (
        tag
        for tag, subscribers in context.chat_data.items()
        if update.effective_user.id in subscribers
    )

    user_name = update.effective_user.username or update.effective_user.first_name
    text = f"inscrições de {user_name}: {' '.join(subscriptions)}"

    assert update.message is not None
    update.message.reply_text(text)


def handle_hashtag(update: Update, context: CallbackContext) -> None:
    assert update.message is not None
    tags = get_hashtags(update.message)

    assert context.chat_data is not None
    tagged = (context.chat_data.get(tag, {}) for tag in tags)

    mentions = (
        mention_markdown(id, name)
        for subscribers in tagged
        for id, name in subscribers.items()
    )

    text = " ".join(mentions)
    if text:
        update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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
    dispatcher.add_handler(CommandHandler("list", handle_list))
    dispatcher.add_handler(
        MessageHandler(
            Filters.entity(MessageEntity.HASHTAG)
            | Filters.caption_entity(MessageEntity.HASHTAG),
            handle_hashtag,
        )
    )
    dispatcher.add_error_handler(handle_error)

    updater.start_polling()


if __name__ == "__main__":
    main()
