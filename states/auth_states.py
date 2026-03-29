from aiogram.fsm.state import State,StatesGroup

class Auth_States(StatesGroup):
    menu_state = State()
    notifications_state = State()