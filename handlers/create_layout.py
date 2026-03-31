import zipfile
import re as _re
from decimal import Decimal
from datetime import datetime, date
import calendar
import tempfile
import os


def _xml_escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _col_letter_to_num(letter: str) -> int:
    result = 0
    for ch in letter.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result


def _col_num_to_letter(num: int) -> str:
    result = ''
    while num > 0:
        num, rem = divmod(num - 1, 26)
        result = chr(rem + ord('A')) + result
    return result


def _get_col_styles(sheet: str) -> dict:
    col_styles = {}
    for m in _re.finditer(r'<col\s[^>]*?min="(\d+)"[^>]*?max="(\d+)"[^>]*/>', sheet):
        tag = m.group(0)
        sm = _re.search(r'style="(\d+)"', tag)
        if sm:
            style_id = sm.group(1)
            end_col = min(int(m.group(2)), 200)
            for c in range(int(m.group(1)), end_col + 1):
                col_styles[c] = style_id
    return col_styles


def _fill_template(template_path: str, output_path: str,
                   cell_values: dict, new_rows: dict | None = None,
                   extra_merges: list | None = None) -> None:
    """
    Заполняет xlsx-шаблон значениями.
    Текст записывается через sharedStrings (t="s") — как в самом шаблоне.
    styles.xml, изображения, настройки печати — побайтово без изменений.
    """
    with zipfile.ZipFile(template_path, 'r') as z:
        file_map = {name: z.read(name) for name in z.namelist()}

    sheet = file_map['xl/worksheets/sheet1.xml'].decode('utf-8')

    ss_raw = file_map.get('xl/sharedStrings.xml', b'').decode('utf-8')
    existing_si = _re.findall(r'<si>.*?</si>', ss_raw, _re.DOTALL)
    ss_count = len(existing_si)
    new_si_entries: list[str] = []

    def _add_string(text) -> int:
        nonlocal ss_count
        if isinstance(text, str) and text.startswith('<rich>'):
            raw_xml = text[6:]  # strip '<rich>'
            if raw_xml.endswith('</rich>'):
                raw_xml = raw_xml[:-7]  # strip '</rich>'
            new_si_entries.append(f'<si>{raw_xml}</si>')
        else:
            escaped = _xml_escape(str(text))
            new_si_entries.append(f'<si><t>{escaped}</t></si>')
        idx = ss_count
        ss_count += 1
        return idx

    def _make_cell_xml(ref: str, val, s_attr: str = '') -> str:
        if isinstance(val, (int, float, Decimal)):
            num = int(val) if isinstance(val, Decimal) and val == int(val) else val
            return f'<c r="{ref}"{s_attr}><v>{num}</v></c>'
        idx = _add_string(val)
        return f'<c r="{ref}"{s_attr} t="s"><v>{idx}</v></c>'

    def _set_existing_cell(sheet: str, ref: str, val) -> str:
        if isinstance(val, (int, float, Decimal)):
            num = int(val) if isinstance(val, Decimal) and val == int(val) else val
            inner = f'<v>{num}</v>'
            t_attr = ''
        else:
            idx = _add_string(val)
            inner = f'<v>{idx}</v>'
            t_attr = ' t="s"'

        pat_self = _re.compile(rf'<c r="{_re.escape(ref)}"([^>]*)/>')
        m = pat_self.search(sheet)
        if m:
            attrs = _re.sub(r'\s+t="[^"]*"', '', m.group(1))
            cell = f'<c r="{ref}"{attrs}{t_attr}>{inner}</c>'
            return sheet[:m.start()] + cell + sheet[m.end():]

        pat_full = _re.compile(rf'<c r="{_re.escape(ref)}"([^>]*)>.*?</c>')
        m = pat_full.search(sheet)
        if m:
            attrs = _re.sub(r'\s+t="[^"]*"', '', m.group(1))
            cell = f'<c r="{ref}"{attrs}{t_attr}>{inner}</c>'
            return sheet[:m.start()] + cell + sheet[m.end():]

        return sheet

    col_styles = _get_col_styles(sheet)

    for ref, val in cell_values.items():
        sheet = _set_existing_cell(sheet, ref, val)

    if new_rows:
        for rn in sorted(new_rows.keys()):
            row_pat = _re.compile(rf'<row r="{rn}"[^>]*>(.*?)</row>', _re.DOTALL)
            rm = row_pat.search(sheet)
            if rm:
                for col_letter, val in sorted(new_rows[rn].items()):
                    cell_ref = f'{col_letter}{rn}'
                    if f'r="{cell_ref}"' in rm.group(0):
                        sheet = _set_existing_cell(sheet, cell_ref, val)
                    else:
                        col_num = _col_letter_to_num(col_letter)
                        style_id = col_styles.get(col_num)
                        s_attr = f' s="{style_id}"' if style_id else ''
                        insert_pos = rm.end() - len('</row>')
                        cell_xml = _make_cell_xml(cell_ref, val, s_attr)
                        sheet = sheet[:insert_pos] + cell_xml + sheet[insert_pos:]
                        rm = row_pat.search(sheet)
            else:
                cells_xml = ''
                for col_letter, val in sorted(new_rows[rn].items()):
                    cell_ref = f'{col_letter}{rn}'
                    col_num = _col_letter_to_num(col_letter)
                    style_id = col_styles.get(col_num)
                    s_attr = f' s="{style_id}"' if style_id else ''
                    cells_xml += _make_cell_xml(cell_ref, val, s_attr)
                new_row = f'<row r="{rn}">{cells_xml}</row>'
                sheet = sheet.replace('</sheetData>', f'{new_row}</sheetData>')

    if extra_merges:
        mc_m = _re.search(r'<mergeCells count="(\d+)">', sheet)
        if mc_m:
            existing = set(_re.findall(r'<mergeCell ref="([^"]+)"', sheet))
            inserts = ''
            added = 0
            for ref in extra_merges:
                if ref not in existing:
                    inserts += f'<mergeCell ref="{ref}"/>'
                    added += 1
            if added:
                old_count = int(mc_m.group(1))
                sheet = sheet.replace(
                    '</mergeCells>',
                    f'{inserts}</mergeCells>'
                )
                sheet = sheet.replace(
                    f'<mergeCells count="{old_count}">',
                    f'<mergeCells count="{old_count + added}">'
                )

    all_refs = _re.findall(r'<c r="([A-Z]+)(\d+)"', sheet)
    for mm in _re.finditer(r'<mergeCell ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', sheet):
        all_refs.append((mm.group(1), mm.group(2)))
        all_refs.append((mm.group(3), mm.group(4)))
    if all_refs:
        min_row = min(int(r) for _, r in all_refs)
        max_row = max(int(r) for _, r in all_refs)
        min_col = min(_col_letter_to_num(c) for c, _ in all_refs)
        max_col = max(_col_letter_to_num(c) for c, _ in all_refs)
        new_dim = f'{_col_num_to_letter(min_col)}{min_row}:{_col_num_to_letter(max_col)}{max_row}'
        sheet = _re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="{new_dim}"/>', sheet)

    file_map['xl/worksheets/sheet1.xml'] = sheet.encode('utf-8')

    if new_si_entries and ss_raw:
        ss_raw = ss_raw.replace('</sst>', ''.join(new_si_entries) + '</sst>')
        sst_m = _re.search(r'<sst\s[^>]*>', ss_raw)
        if sst_m:
            tag = sst_m.group(0)
            tag = _re.sub(r'count="\d+"', f'count="{ss_count}"', tag)
            tag = _re.sub(r'uniqueCount="\d+"', f'uniqueCount="{ss_count}"', tag)
            ss_raw = ss_raw[:sst_m.start()] + tag + ss_raw[sst_m.end():]
        file_map['xl/sharedStrings.xml'] = ss_raw.encode('utf-8')
    elif new_si_entries:
        ss_new = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{ss_count}" uniqueCount="{ss_count}">'
            f'{"".join(new_si_entries)}</sst>'
        )
        file_map['xl/sharedStrings.xml'] = ss_new.encode('utf-8')

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out:
        for name, data in file_map.items():
            out.writestr(name, data)



director = 'Директор'
start_text_in_a5_ab5 = 'Арендодатель: '
start_text_in_a7_ab7 = 'Арендатор: '
start_text_in_a16_ab16 = 'Всего оказано услуг 1, на сумму '
text_for_user_accept_data_A19_AB19= 'Вышеперечисленные услуги выполнены полностью и в срок. Арендатор претензий по объему, качеству и срокам оказания услуг не имеет.'

def get_text_work_in_act(number_agreement, current_date):
    split_agreement = str(number_agreement).split(' ')
    agr_num = split_agreement[0] if len(split_agreement) > 0 else ""
    agr_date = f" от {split_agreement[1]}" if len(split_agreement) > 1 else ""
    
    start_date = datetime(current_date.year, current_date.month, 1)
    last_day_in_this_month = calendar.monthrange(current_date.year, current_date.month)[1]
    last_date = date(current_date.year, current_date.month, last_day_in_this_month)
    text = f'Услуги аренды по договору аренды нежилого помещения №{agr_num}{agr_date}. За период с {start_date.strftime("%d.%m.%Y")} по {last_date.strftime("%d.%m.%Y")}.'
    return text

def sum_propisyu_full(summa):
    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    units_female = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", 
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "десять", "двадцать", "тридцать", "сорок", "пятьдесят", 
            "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
    hundreds = ["", "сто", "двести", "триста", "четыреста", "пятьсот", 
                "шестьсот", "семьсот", "восемьсот", "девятьсот"]
    
    thousands = ["тысяча", "тысячи", "тысяч"]
    millions = ["миллион", "миллиона", "миллионов"]
    billions = ["миллиард", "миллиарда", "миллиардов"]
    
    if isinstance(summa, str):
        summa = summa.replace(',', '.')
        summa = float(summa)
    
    rubli = int(summa)
    kopeyki = int(round((summa - rubli) * 100))
    
    def number_to_words(num, gender_female=False):
        if num == 0:
            return "ноль"
        
        result = []
        
        # Миллиарды
        bln = num // 1_000_000_000
        if bln > 0:
            bln_text = convert_triple(bln, False)
            result.append(bln_text + " " + get_plural_form(bln, billions))
            num %= 1_000_000_000
        
        # Миллионы
        mil = num // 1_000_000
        if mil > 0:
            mil_text = convert_triple(mil, False)
            result.append(mil_text + " " + get_plural_form(mil, millions))
            num %= 1_000_000
        
        # Тысячи
        thousand = num // 1_000
        if thousand > 0:
            thousand_text = convert_triple(thousand, True)
            result.append(thousand_text + " " + get_plural_form(thousand, thousands))
            num %= 1_000
        
        # Остаток
        if num > 0:
            result.append(convert_triple(num, gender_female))
        
        return " ".join(result)
    
    def convert_triple(num, is_thousand=False):
        """Конвертирует трёхзначное число"""
        if num == 0:
            return ""
        
        res = []
        
        # Сотни
        h = num // 100
        if h > 0:
            res.append(hundreds[h])
            num %= 100
        
        # Десятки и единицы
        if num >= 20:
            d = num // 10
            res.append(tens[d])
            num %= 10
            if num > 0:
                if is_thousand:
                    res.append(units_female[num])
                else:
                    res.append(units[num])
        elif num >= 10:
            res.append(teens[num - 10])
        elif num > 0:
            if is_thousand:
                res.append(units_female[num])
            else:
                res.append(units[num])
        
        return " ".join(res)
    
    def get_plural_form(num, forms):
        """Возвращает правильную форму слова"""
        num = num % 100
        if 11 <= num <= 19:
            return forms[2]
        
        last_digit = num % 10
        if last_digit == 1:
            return forms[0]
        if 2 <= last_digit <= 4:
            return forms[1]
        return forms[2]
    
    def get_rubles_word(num):
        """Склонение слова 'рубль'"""
        num = num % 100
        if 11 <= num <= 19:
            return "рублей"
        
        last_digit = num % 10
        if last_digit == 1:
            return "рубль"
        if 2 <= last_digit <= 4:
            return "рубля"
        return "рублей"
    
    def get_kopeyki_word(num):
        """Склонение слова 'копейка'"""
        num = num % 100
        if 11 <= num <= 19:
            return "копеек"
        
        last_digit = num % 10
        if last_digit == 1:
            return "копейка"
        if 2 <= last_digit <= 4:
            return "копейки"
        return "копеек"
    
    # Получаем рубли прописью
    rubli_text = number_to_words(rubli, False)
    if rubli == 0:
        rubli_text = "ноль"
    else:
        rubli_text = rubli_text.capitalize()
    
    # Формируем результат
    rubli_word = get_rubles_word(rubli)
    kopeyki_word = get_kopeyki_word(kopeyki)
    
    return f"{rubli_text} {rubli_word} {kopeyki:02d} {kopeyki_word}"

def get_short_fio(fio):
    print(fio)
    fio_split = fio.split(' ')
    print(fio_split)
    short_name = f'{fio_split[1][0]}.'.upper()
    short_patronymic = f'{fio_split[2][0]}.'.upper()
    short_fio = f'{fio_split[0]} {short_name}{short_patronymic}'
    return short_fio

async def create_layoat_for_user(name_company, name_company_tenant, current_date, final_price, square, agreement, full_name_tenant, act_number, tenant_director_title='Директор'):
    price_rub_cop = str(final_price).split('.')
    rub_part = price_rub_cop[0]
    cop_part = price_rub_cop[1] if len(price_rub_cop) > 1 else '00'
    short_full_name_tenant = get_short_fio(full_name_tenant)

    if isinstance(current_date, str):
        for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                current_date = datetime.strptime(current_date, fmt)
                break
            except ValueError:
                continue

    act_text = f'Акт за аренду №{act_number} от {current_date.strftime("%d.%m.%Y")}'
    text_work_in_act = get_text_work_in_act(agreement, current_date)

    cell_values = {
        'A3':  act_text,
        'A5':  f'{start_text_in_a5_ab5}{name_company}',
        'A7':  f'{start_text_in_a7_ab7}{name_company_tenant}',
        'C11': text_work_in_act,
        'T11': square,
        'W11': 'кв.м',
        'Y11': final_price,
        'Y13': final_price,
        'A16': f'{start_text_in_a16_ab16}{rub_part} руб. {cop_part} коп.',
        'A17': sum_propisyu_full(final_price),
        'A22': f'{director} {name_company}',
        'T22': f'{tenant_director_title} {name_company_tenant}',
        'A24': 'Попова Я.В. __________',
        'T24': f'{short_full_name_tenant} ________________',
    }

    name_file = f'Акт на оплату арендного платежа для {name_company_tenant}'
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{name_file}_{next(tempfile._get_candidate_names())}.xlsx")

    _fill_template('docs/create_layout_us.xlsx', temp_file_path, cell_values)
    return temp_file_path

async def create_invoice_for_payment_for_user(act_number, name_company, name_company_tenant,
                                               agreement, price, square,
                                               full_name_tenant, tenant_director_title='Директор',
                                               target_date=None):
    if target_date is None:
        target_date = datetime.now().replace(day=1)

    first_day = target_date.replace(day=1).strftime("%d.%m.%Y")
    fifth_day = target_date.replace(day=5).strftime("%d.%m.%Y")
    text_work_in_act = get_text_work_in_act(agreement, target_date)

    price_val = float(price)
    price_formatted = f"{price_val:.2f}"

    buyer_escaped = _xml_escape(name_company_tenant)
    buyer_rich = (
        '<rich>'
        '<r><rPr><sz val="12"/><rFont val="Times New Roman"/><family val="1"/></rPr>'
        '<t xml:space="preserve">Покупатель: </t></r>'
        '<r><rPr><b/><sz val="12"/><rFont val="Times New Roman"/><family val="1"/></rPr>'
        f'<t>{buyer_escaped}</t></r>'
    )

    cell_values = {
        'A5':  f'Счет на оплату №{act_number} от {first_day}',
        'A7':  buyer_rich,
        'C9':  text_work_in_act,
        'I9':  price_val,
        'K9':  price_val,
        'A10': f'Оплатить до:                                                                   {fifth_day}',
        'L11': price_val,
        'A12': f'Всего наименований 1, на сумму {price_formatted} руб.',
        'B13': f'({sum_propisyu_full(price)})',
    }

    cleaned = name_company_tenant.replace('"', '')
    name_file = f'Счет на оплату арендного платежа для {cleaned}'
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{name_file}_{next(tempfile._get_candidate_names())}.xlsx")

    _fill_template('docs/Счет на оплату Аренда.xlsx', temp_file_path, cell_values)
    return temp_file_path


async def create_invoice_for_ku_for_user(act_number, name_company, name_company_tenant,
                                         agreement, price, square, start_period, end_period,
                                         full_name_tenant, tenant_director_title='Директор',
                                         target_date=None):
    if target_date is None:
        target_date = datetime.now().replace(day=1)

    first_day = target_date.replace(day=1).strftime("%d.%m.%Y")
    fifth_day = target_date.replace(day=5).strftime("%d.%m.%Y")

    agreement_list = agreement.split(' ')
    agr_num = agreement_list[0] if len(agreement_list) > 0 else ""
    agr_date = f" от {agreement_list[1]}г." if len(agreement_list) > 1 else ""

    text_work = (
        f'Возмещение затрат на электроснабжение, отопление, коммунальные услуги '
        f'по договору аренды нежилого помещения №{agr_num}{agr_date} '
        f'за период с {start_period}г. по {end_period}г.'
    )

    price_val = float(price)
    price_formatted = f"{price_val:.2f}"

    buyer_escaped = _xml_escape(name_company_tenant)
    buyer_rich = (
        '<rich>'
        '<r><rPr><sz val="12"/><rFont val="Times New Roman"/><family val="1"/></rPr>'
        '<t xml:space="preserve">Покупатель: </t></r>'
        '<r><rPr><b/><sz val="12"/><rFont val="Times New Roman"/><family val="1"/></rPr>'
        f'<t>{buyer_escaped}</t></r>'
    )

    cell_values = {
        'A5':  f'Счет на оплату №{act_number} от {first_day}',
        'A7':  buyer_rich,
        'C9':  text_work,
        'I9':  price_val,
        'K9':  price_val,
        'A10': f'Оплатить до:                                                                   {fifth_day}',
        'L11': price_val,
        'A12': f'Всего наименований 1, на сумму {price_formatted} руб.',
        'B13': f'({sum_propisyu_full(price)})',
    }

    cleaned = name_company_tenant.replace('"', '')
    name_file = f'Счет на оплату КУ для {cleaned}'
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{name_file}_{next(tempfile._get_candidate_names())}.xlsx")

    _fill_template('docs/Счет на оплату КУ.xlsx', temp_file_path, cell_values)
    return temp_file_path


async def create_act_payment_ku_for_user(act_number, name_company, name_company_tenant,
                                         agreement, price, square, start_period, end_period,
                                         full_name_tenant, tenant_director_title='Директор',
                                         target_date=None):
    months_ru = {
        1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
        5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
        9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
    }
    if target_date is None:
        target_date = datetime.now()

    month_name = months_ru[target_date.month]

    agreement_list = agreement.split(' ')
    agr_num = agreement_list[0] if len(agreement_list) > 0 else ""
    agr_date = f" от {agreement_list[1]}" if len(agreement_list) > 1 else ""

    text_work = (
        f'Возмещение затрат на электроснабжение, отопление, коммунальные услуги '
        f'по договору аренды нежилого помещения №{agr_num}{agr_date}. '
        f'За период с {start_period} по {end_period}.'
    )

    price_str = str(price)
    price_parts = price_str.split('.')
    rub_part = price_parts[0]
    cop_part = price_parts[1] if len(price_parts) > 1 else '00'

    short_fio = get_short_fio(full_name_tenant)

    cell_values = {
        'A3':  f'Акт №{act_number} КУ {month_name} {target_date.year}',
        'A5':  f'{start_text_in_a5_ab5}{name_company}',
        'A7':  f'{start_text_in_a7_ab7}{name_company_tenant}',
        'C11': text_work,
        'T11': square,
        'W11': 'кв.м',
        'Y11': price,
        'Y13': price,
        'A16': f'{start_text_in_a16_ab16}{rub_part} руб. {cop_part} коп.',
        'A17': sum_propisyu_full(price),
        'A22': f'{director} {name_company}',
        'T22': f'{tenant_director_title} {name_company_tenant}',
        'A24': 'Попова Я.В. __________',
        'T24': f'{short_fio} ________________',
    }

    cleaned = name_company_tenant.replace('"', '')
    name_file = f'Акт КУ для {cleaned}'
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"{name_file}_{next(tempfile._get_candidate_names())}.xlsx")

    _fill_template('docs/invoice_for_payment.xlsx', temp_file_path, cell_values)
    return temp_file_path

