from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from telegram import Message, MessageEntity, ParseMode, Update, User
from telegram.ext import (
    BasePersistence,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    Updater,
)
from telegram.ext.filters import Filters
from telegram.ext.filters import MessageEntity as MessageEntityType
from telegram.utils.helpers import mention_markdown


def get_entities(
    message: Message, entity_types: List[MessageEntityType]
) -> Dict[MessageEntity, str]:
    entities = {}

    if message.entities is not None:
        entities.update(message.parse_entities(entity_types))

    if message.caption_entities is not None:
        entities.update(message.parse_caption_entities(entity_types))

    return entities


def get_hashtags(message: Message) -> List[str]:
    entity_types = [MessageEntityType.HASHTAG]
    tags = get_entities(message, entity_types).values()
    return list(tags)


def get_mentions(message: Message) -> List[Union[User, str]]:
    entity_types = [MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION]

    mentions = get_entities(message, entity_types)

    return [
        mention.user if mention.user is not None else username.lstrip("@")
        for mention, username in mentions.items()
    ]


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
            if not subscribers:
                del context.chat_data[tag]

    verb = "adicionadas" if status else "removidas"
    text = f"inscrições {verb} para {user_name}: {' '.join(tags)}"
    update.message.reply_text(text)


def handle_sub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=True)


def handle_unsub(update: Update, context: CallbackContext) -> None:
    return update_subscription(update, context, status=False)


def get_user_subscriptions(
    user: Union[User, str], context: CallbackContext
) -> List[str]:
    assert context.chat_data is not None

    if isinstance(user, User):
        return [
            tag
            for tag, subscribers in context.chat_data.items()
            if user.id in subscribers
        ]

    else:
        return [
            tag
            for tag, subscribers in context.chat_data.items()
            if user in subscribers.values()
        ]


def get_tag_subscribers(tag: str, context: CallbackContext) -> List[Tuple[int, str]]:
    assert context.chat_data is not None
    return list(context.chat_data.get(tag, {}).items())


def list_subscriptions(user: Union[User, str], context: CallbackContext) -> str:
    assert context.chat_data is not None

    subscriptions = get_user_subscriptions(user, context)

    if isinstance(user, User):
        user_name = user.username or user.first_name
    else:
        user_name = user

    return f"inscrições de {user_name}: {' '.join(subscriptions)}"


def list_subscribers(tag: str, context: CallbackContext) -> str:
    assert context.chat_data is not None

    subscribers = get_tag_subscribers(tag, context)
    mentions = (name for id, name in subscribers)

    return f"inscritos em {tag}: {' '.join(mentions)}"


def handle_list(update: Update, context: CallbackContext) -> None:
    assert update.effective_user is not None
    text = list_subscriptions(update.effective_user, context)

    assert update.message is not None
    update.message.reply_text(text)


def handle_list_all(update: Update, context: CallbackContext) -> None:
    assert context.chat_data is not None

    text = f"tags do grupo: {' '.join(context.chat_data.keys())}"

    assert update.message is not None
    update.message.reply_text(text)


def handle_info(update: Update, context: CallbackContext) -> None:
    args = context.args or []
    assert update.message is not None

    assert len(args) > 0, "quer info de quê, meu anjo?"
    assert len(args) < 2, "uma coisa de cada vez, faz favor"

    mentions = get_mentions(update.message)
    hashtags = get_hashtags(update.message)

    if mentions:
        user = mentions[0]
        text = list_subscriptions(user, context)

    elif hashtags:
        tag = hashtags[0]
        text = list_subscribers(tag, context)

    else:
        user = args[0]
        text = list_subscriptions(user, context)

    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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
    dispatcher.add_handler(CommandHandler("listall", handle_list_all))
    dispatcher.add_handler(CommandHandler("info", handle_info))
    dispatcher.add_handler(
        MessageHandler(
            Filters.entity(MessageEntityType.HASHTAG)
            | Filters.caption_entity(MessageEntityType.HASHTAG),
            handle_hashtag,
        )
    )
    dispatcher.add_error_handler(handle_error)

    updater.start_polling()


if __name__ == "__main__":
    main()
