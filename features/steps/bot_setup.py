import os

from behave import given

from plusplusbot.dummies.bot import Bot


@given('Robbins is online')
def robbins(context):
    context.robbins_bot = Bot(os.environ.get("ROBBINS_BOT_TOKEN", None))


@given('Dave is online')
def dave(context):
    context.dave_bot = Bot(os.environ.get("DAVE_BOT_TOKEN", None))
