from aiogram.fsm.state import State, StatesGroup

class AdminState(StatesGroup):
    admin_menu = State()
    waiting_for_message = State()
    confirming_send = State()
    selecting_users = State()
    viewing_stats = State()
    managing_users = State()
    settings_menu = State()
    choosing_type = State()
    choosing_method = State()
    waiting_for_volume = State()
    waiting_for_amount = State()
    collecting_data = State()
    waiting_for_file = State()
    editing_data = State()
    waiting_for_edit = State() 
    waiting_for_amount_expl = State()
    waiting_for_amount_drainage = State()
    waiting_for_tariff = State()
    waiting_for_tariff_edit = State()
    waiting_for_documents = State()
    confirming_documents = State()

    company_list = State()  # Основное состояние - список компаний
    company_action = State()  # Действие с компанией
    edit_param = State()  # Редактирование параметра
    add_company = State()
    waiting_for_unexpected = State()

    choosing_service = State()  # Выбор услуги (отопление/общие)
    selecting_tenant = State()  # Выбор арендатора
    waiting_for_heat_volume = State()  # Ввод показаний отопления
    waiting_for_heat_amount = State()  # Ввод суммы отопления
    confirming_readings = State()  # Подтверждение показаний
    meter_filler_choice = State()  # Выбор кто заполняет (Я/Арендатор)
    meter_type_selection = State()  # Выбор типа счетчика
    entering_cold_water = State()  # Ввод холодной воды
    entering_hot_water = State()   # Ввод горячей воды
    entering_electricity = State()  # Ввод электроэнергии
    waiting_for_unexpected = State()
    waiting_for_documents_unexpected = State()
    confirming_documents_unexpected = State()