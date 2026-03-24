from aiogram.fsm.state import StatesGroup,State

class RegStates(StatesGroup):
    enterINN_state = State()
    enter_type_busines_state = State()
    enter_sfp_state = State()
    enter_second_name_state = State()
    enter_first_name_state = State()
    enter_patronymic_state = State()
    enter_company_name_state = State()
    end_reg_state = State()
    