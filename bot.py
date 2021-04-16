import logging
from datetime import datetime

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ParseMode, KeyboardButton, ReplyKeyboardMarkup
from aiogram.types.message import ContentType
from aiogram.utils.emoji import emojize
from aiogram.utils.executor import start_polling
from aiogram.utils.markdown import bold, italic, text, code
from pydantic import BaseSettings

from proj.client import Client
from proj.data import ALL_PAIRS, ALL_COINS
from proj.errors import ApiError


class Config(BaseSettings):
    api_token: str

    class Config:
        env_file = '.env'


storage = MemoryStorage()

config = Config()
API_TOKEN = config.api_token
RATES_URL = 'http://localhost:8000/api/rates/'
GRAPH_URL = 'http://localhost:8000/api/graphs/'
EXCHANGE_URL = 'http://localhost:8000/api/rates/exchange/'
WRONG_ARGS_ERROR = 'Wrong args, call /help for usage info'
API_ERROR = 'Something went wrong.'
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, )

dp = Dispatcher(bot, storage=storage)
client = Client('http://localhost:8000/')


class RegistrationForm(StatesGroup):
    api_key = State()
    secret = State()


balance_text = emojize('💼 Баланс')
history_text = emojize('🧮 История ордеров')
profit_text = emojize('💵 Профит')
help_text = emojize('🆘 Помощь')
button1 = KeyboardButton(balance_text)
button2 = KeyboardButton(history_text)
button3 = KeyboardButton(profit_text)
button_help = KeyboardButton(help_text)

markup3 = ReplyKeyboardMarkup().add(
    button1).add(button2).add(button3).add(button_help)
cancel_text = emojize('❌ Отмена')
registration_text = emojize('👋 Регистрация')
button_cancel = KeyboardButton(cancel_text)
markup_cancel = ReplyKeyboardMarkup().add(
    button_cancel)
button_registration = KeyboardButton(registration_text)
markup_registration = ReplyKeyboardMarkup().add(button_registration).add(button_cancel)


def login_required(func):
    async def check_user(message: types.Message):
        try:
            user = await client.auth_user(message.from_user.id)
            if not user:
                await message.reply(text('Зарегистрируйтесь для начала', sep='\n'), parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=markup_registration)
                return
        except ApiError as ex:
            await message.reply(text(ex.message, sep='\n'), parse_mode=ParseMode.MARKDOWN)
            return
        return await func(message)

    return check_user


# You can use state '*' if you need to handle all states
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals=cancel_text, ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply('Регистрация прервана', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    """
    Conversation's entry point
    """
    # Set state
    try:
        user = await client.auth_user(message.from_user.id)
        if user:
            await message.reply(text('Вы уже зарегистрированы', sep='\n'), parse_mode=ParseMode.MARKDOWN,
                                reply_markup=markup3)
            return
        await message.reply("Вы хотите зарегистрироваться?", reply_markup=markup_registration)
    except ApiError as ex:
        await message.reply(text(ex.message, sep='\n'), parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands='registration')
@dp.message_handler(Text(equals=registration_text, ignore_case=True))
async def registration(message: types.Message):
    user = await client.auth_user(message.from_user.id)
    if user:
        await message.reply("Вы уже зарегистрированы.", reply_markup=markup3)
        return

    await RegistrationForm.api_key.set()

    await message.reply("Введите Binance api key c Binance.", reply_markup=markup_cancel)


@dp.message_handler(state=RegistrationForm.api_key)
async def process_api_key(message: types.Message, state: FSMContext):
    """
    Process user name
    """
    async with state.proxy() as data:
        data['api_key'] = message.text

    await RegistrationForm.next()
    await message.reply("Ввведите ваш api secret c Binance.", reply_markup=markup_cancel)


@dp.message_handler(state=RegistrationForm.secret)
async def process_secret(message: types.Message, state: FSMContext):
    """
    Process user name
    """
    async with state.proxy() as data:
        data['secret'] = message.text
        try:
            user = await client.register(message.from_user.id, message.from_user.username, data['secret'],
                                         data['api_key'])
            await message.reply(text(f'"Вы успешно зарегистрированы, {user.telegram_username}', sep='\n'),
                                parse_mode=ParseMode.MARKDOWN)
        except ApiError:
            await message.reply(
                text(f'Вы ввели недействительные ключи, попробуйте снова.'),
                reply_markup=markup_registration,
                parse_mode=ParseMode.MARKDOWN
            )
        finally:
            await state.finish()


@dp.message_handler(commands=['help'])
@dp.message_handler(Text(equals=help_text, ignore_case=True))
async def help_command(message: types.Message):
    user = await client.auth_user(message.from_user.id)
    text_msg = text(
        "Возможные команды:\n",
        '/balance <валюта>',
        "- баланс в определенной валюте, по умолчанию BTC\n",
        '/orders <валюта>', "- отображение ордеров по определенной валюте, по умолчанию все\n",
        '/rate <валютная_пара>', "- отображение курса валютной пары",
        '/profit', "- отображение прибыли/убытков по портфелю в USDT"
    )
    if not user:
        await message.reply(text('Вы не зарегистрированы, зарегистрируйтесь для начала', sep='\n'),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=markup_registration)
    await message.answer(text_msg, reply_markup=markup3)


@dp.message_handler(commands=['balance'])
@dp.message_handler(lambda message: message.text and 'баланс' in message.text.lower())
@login_required
async def balance(message: types.Message):
    symbol = message.get_args()
    if symbol is not None:
        symbol = symbol.split(' ', maxsplit=1)[0]
    await types.ChatActions.typing()
    if symbol:
        symbol = symbol.upper()
        if symbol not in ALL_COINS:
            await message.reply(text('Такой монеты нет на бинансе.', sep='\n'), parse_mode=ParseMode.MARKDOWN)
            return
    data = await client.get_balance(message.from_user.id, symbol)
    if symbol:
        text_data = f'\n Сумма в {symbol}: {data["sum"]}'
    else:
        text_data = f'\n Сумма в BTC: {data["sum"]}'
    await message.reply(text(text_data, sep='\n'), parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands=['orders'])
@dp.message_handler(lambda message: message.text and 'история ордеров' in message.text.lower())
@login_required
async def orders_list(message: types.Message):
    symbol = message.get_args()
    if symbol is not None:
        symbol = symbol.split(' ', maxsplit=1)[0]
    await types.ChatActions.typing()
    if symbol:
        symbol = symbol.upper()
        if symbol not in ALL_COINS:
            await message.reply(text('Такой монеты нет на бинансе.', sep='\n'), parse_mode=ParseMode.MARKDOWN)
            return
    print(symbol)
    orders = await client.get_orders(message.from_user.id, symbol)
    text_data = '\n'.join(
        [

            f" #{i}\n {bold(o.symbol)}: количество= {o.amount}, цена = {o.price}, время={datetime.utcfromtimestamp(int(o.time) // 1000).strftime('%Y-%m-%d %H:%M:%S')} "
            for i, o in enumerate(orders, start=1) if o.amount
        ]
    )
    await message.reply(text(text_data, sep='\n'), parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands=['profit'])
@dp.message_handler(lambda message: message.text and 'профит' in message.text.lower())
@login_required
async def profit_list(message: types.Message):
    await types.ChatActions.typing()
    profit = await client.get_profit(message.from_user.id)
    profit_data = profit['profit']
    text_data = '\n'.join(
        [

            f"{bold(asset)}: {profit}$"
            for asset, profit in profit_data.items()
        ]
    )
    total_profit = float('{:010.4f}'.format(profit["total_profit"]))
    text_data += f'\nВесь профит: {total_profit}$'
    await message.reply(text(text_data, sep='\n'), parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands=['rate'])
@login_required
async def rates_for_coin(message: types.Message):
    symbol = message.get_args()
    if not symbol:
        await message.reply(text('Укажите валютную пару.', sep='\n'), parse_mode=ParseMode.MARKDOWN)
        return
    symbol = symbol.split(' ', maxsplit=1)[0]
    await types.ChatActions.typing()
    symbol = symbol.upper()
    if symbol not in ALL_PAIRS:
        await message.reply(text('Такой пары нет на бинансе.', sep='\n'), parse_mode=ParseMode.MARKDOWN)
        return
    rate = await client.get_rate(symbol)
    if rate:
        await message.reply(text(f'Курс пары {symbol} = {rate}', sep='\n'), parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply(text(f'Несуществующая пара', sep='\n'), parse_mode=ParseMode.MARKDOWN)

if __name__ == '__main__':
    start_polling(dp, skip_updates=True)
