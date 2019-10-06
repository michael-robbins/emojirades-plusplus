from behave import when, then


@when('Robbins says "{phrase}"')
def robbins_says(context, phrase):
    context.robbins_bot.send_message(phrase, '#random')


@then('Dave says "{phrase}"')
def dave_says(context, phrase):
    context.dave_bot.send_message(phrase, '#random')
