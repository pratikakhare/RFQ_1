import os
import re
import tempfile
import pandas as pd
from dateutil import parser

VALID_SUBMISSION_CATEGORY = {
    'FOB', 'OFR', 'PLC', 'SVC', 'ALL',
    'FOB/OFR', 'FOB/PLC', 'FOB/SVC',
    'OFR/PLC', 'OFR/SVC', 'PLC/SVC',
    'FOB/OFR/PLC', 'FOB/OFR/SVC',
    'FOB/PLC/SVC', 'OFR/PLC/SVC',
    'OFR (IPI)'
}

VALID_SUB_CATEGORY = {
    'ROUTING',
    'OFR SURCHARGES',
    'BASE CHARGES PER WM-MIN & BL',
    '3RD PARTY CFS CHARGES',
    'BASE CHARGES PER WM-MIN',
    'TRANSIT TIME',
    'CURRENCY',
    'CARRIER SCAC CODES',
    'ENTIRE SHEET',
    'SOLAS FEE',
    'FILING FEES',
    'ORIGIN-DESTINATION VIA',
    'COMPENSATION',
    'RATE BASIS',
    'STORAGE CHARGE AFTER FREE TIME',
    'BASE CHARGES PER BL',
    'POL/POD DETAILS',
    'OTHER SURCHARGES',
    'ALTERNATIVE PORTS',
    'HAZ CHARGES',
    'EXP. CLEARANCE SURCHARGE',
    'FREQUENCY',
    'BMSB',
    'CUTOFF DAYS',
    'DESCRIPTION',
    'HAZ ROUTING',
    'IPI',
    'OWN/CO-LOAD',
    'PRE-DEFINED RATES',
    'STORAGE FREE DAYS',
    'NON-STACKABLE CHARGE',
    'PALLETIZING PER PALLET'
}

VALID_ERROR_CATEGORY = {
    'DIFFERENT RATES FOR DUPLICATE LANES',
    'DUMMY RATES',
    'FILE SENT TO DIFFERENT EMAIL ID',
    'INCOMPLETE INFO - RATE DESCRIPTION MISSING',
    'INCOMPLETE INFO. - PARTIAL RATES',
    'INCORRECT ALT. UNCODE',
    'INCORRECT CURRENCY',
    'INCORRECT DETAILS TRANSMITTED FOR UPLOAD PURPOSE',
    'INCORRECT FILE FORMAT USED/TAMPERED',
    'INCORRECT HAZ DETAILS/RATES',
    'INCORRECT RATES/QUOTE/DETAILS',
    'INCORRECT SERVICE DETAILS',
    'INCREASED RATES',
    'LOCKED RATES OVERRIDE',
    'RECEIVED SUBMISSION POST DEADLINE',
    'MISMATCH IN SERVICE LANE BETWEEN MEMBERS',
    'MISSING DETAILS',
    'NO FEEDBACK',
    'PI NOT FOLLOWED',
    'RATES QUOTED FOR WM & TON',
    'RATES QUOTED WITH DIFFERENT VALIDITY',
    'ROUTING CHANGE-MISSING CONFIRMATION ON FOB/PLC',
    'TYPO ERROR',
    'RATES/DETAILS CORRECTION POST DEADLINE',
    'NEGATIVE RATES'
}

VALID_STATUS_OUTCOME = {
    'ADJUSTED AS PER STD PROCESS',
    'EXTENDED EXISTING RATES',
    'FIXED ERROR',
    'NO UPDATE PROCESSED (DECLINED BY OWNER)',
    'QUERY SENT TO MEMBERS FOR CONFIRMATION',
    'REMOVED',
    'UPDATED AS NS',
    'UPDATED REVISED RCVD RATES/DETAILS',
    'UPDATED ROUTING WITH NO CHANGE IN FOB/PLC',
    'UPDATED USING SDD',
    'NO FEEDBACK FROM ACCOUNT OWNER-NOT UPDATED'
}

VALID_HANDLERS = {
    'AS', 'KB', 'KN', 'RP',
    'SD', 'SG', 'SK', 'SM', 'SR'
}

DATE_COLUMNS = [
    'RFQ RELEASE DATE',
    'DEADLINE',
    'RECEIVED',
    'FINAL SUBMISSION DATE'
]

MAPPING_YN = {
    'Y': 'YES',
    'YES': 'YES',
    'N': 'NO',
    'NO': 'NO'
}


# =========================================================
# MASTER CLEANING FUNCTIONS
# =========================================================

def clean_email(email):
    if pd.isna(email) or not email:
        return ''

    email_str = str(email).strip()
    email_str = re.sub(r'[\n\r\t\xa0]', '', email_str)
    email_candidates = re.split(r'[;,|]+', email_str)

    if len([e for e in email_candidates if e.strip()]) > 1:
        return ''

    email = email_candidates[0].strip().strip('.,;').replace(' ', '')
    email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    return email if re.match(email_regex, email) else ''


def parse_messy_date(x):
    if pd.isna(x) or str(x).strip() == '':
        return ''
    x = str(x)
    x = re.sub(r'IST', '', x, flags=re.IGNORECASE)
    x = re.sub(r'[()]', '', x)
    x = x.replace('//', '/')
    x = re.sub(r'\s+', ' ', x).strip()
    try:
        return parser.parse(x, fuzzy=True).strftime('%m/%d/%Y')
    except Exception:
        return ''


def clean_compliant(x):
    if pd.isna(x):
        return ''
    x = str(x).strip().upper()
    x = re.sub(r'^\d+\s*[\.\)]\s*', '', x)
    x = re.sub(r'\s+', ' ', x)
    if 'REVISED' in x:
        return 'YES - REVISED RATES'
    elif 'MAINTAIN' in x:
        return 'YES - MAINTAIN RATES'
    elif x == 'NO' or ' NO ' in f' {x} ':
        return 'NO'
    return ''


def multiline_cleaner(x, valid_set):
    if pd.isna(x):
        return ''
    x = str(x).upper().strip()
    if x == '':
        return ''
    x = re.sub(r'[\xa0]', ' ', x)
    x = re.sub(r'\s+', ' ', x).strip()
    starts_valid = any(
        x.startswith(v)
        for v in sorted(valid_set, key=len, reverse=True)
    )
    if starts_valid and not re.match(r'^\d+\.', x):
        x = '1. ' + x
    x = re.sub(r'(\d+)\.', r' \1. ', x)
    x = re.sub(r'\s+', ' ', x).strip()
    matches = list(re.finditer(r'(\d+)\.\s*(.*?)(?=\s*\d+\.|$)', x))
    values = []
    if matches:
        for m in matches:
            val = m.group(2).strip()
            if val in valid_set:
                values.append(val)
    else:
        if x in valid_set:
            values.append(x)
    if not values:
        return ''
    values = list(dict.fromkeys(values))
    cleaned = [f"{i+1}. {v}" for i, v in enumerate(values)]
    return '\n'.join(cleaned)


def normalize_month(value):
    month_map = {
        'JANUARY': 'JAN',
        'FEBRUARY': 'FEB',
        'MARCH': 'MAR',
        'APRIL': 'APR',
        'JUNE': 'JUN',
        'JULY': 'JUL',
        'AUGUST': 'AUG',
        'SEPTEMBER': 'SEP',
        'OCTOBER': 'OCT',
        'NOVEMBER': 'NOV',
        'DECEMBER': 'DEC',
        'NAN': ''
    }
    value = str(value).strip().upper()
    return month_map.get(value, value)


def clean_rfq_dataframe(df):
    df['GLOBAL/\nNAC'] = df['GLOBAL/\nNAC'].astype(str).str.strip()
    df['NAMED ACCOUNT'] = df['NAMED ACCOUNT'].astype(str).str.strip()
    cond1 = ~df['GLOBAL/\nNAC'].isin(['GLOBAL', 'NAC'])
    blank_patterns = ['', '-', ' -', '- ', ' - ']
    cond2 = df['NAMED ACCOUNT'].isin(blank_patterns)
    df.loc[cond1 & cond2, 'GLOBAL/\nNAC'] = 'GLOBAL'
    df.loc[cond1 & ~cond2, 'GLOBAL/\nNAC'] = 'NAC'
    df.loc[~df['RFQ HANDLED BY'].isin(VALID_HANDLERS), 'RFQ HANDLED BY'] = ''
    df['WWA MEMBER EMAIL ID'] = df['WWA MEMBER EMAIL ID'].apply(clean_email)
    for c in DATE_COLUMNS:
        df[c] = df[c].apply(parse_messy_date)
    df['MONTH'] = df['MONTH'].apply(normalize_month)
    df['ENTRY COMPLETE YES / NO'] = (
        df['ENTRY COMPLETE YES / NO']
        .astype(str)
        .str.strip()
        .str.upper()
        .apply(lambda x: x if x in ['YES', 'NO'] else '')
    )
    df['COMPLIANT (YES/NO)'] = df['COMPLIANT (YES/NO)'].apply(clean_compliant)
    df['SUBMISSION CATEGORY'] = df['SUBMISSION CATEGORY'].apply(
        lambda x: multiline_cleaner(x, VALID_SUBMISSION_CATEGORY)
    )
    df['SUBMISSION SUB-CATEGORY'] = df['SUBMISSION SUB-CATEGORY'].apply(
        lambda x: multiline_cleaner(x, VALID_SUB_CATEGORY)
    )
    df['ERROR CATEGORY'] = df['ERROR CATEGORY'].apply(
        lambda x: multiline_cleaner(x, VALID_ERROR_CATEGORY)
    )
    df['STATUS UPDATE/OUTCOME'] = df['STATUS UPDATE/OUTCOME'].apply(
        lambda x: multiline_cleaner(x, VALID_STATUS_OUTCOME)
    )
    df['PENALTY REPORTED Y/N'] = (
        df['PENALTY REPORTED Y/N']
        .astype(str)
        .str.strip()
        .str.upper()
        .map(MAPPING_YN)
        .fillna('')
    )
    return df


def process_rfq_file(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)
        temp_path = temp_file.name

    sheets = [
        'Aseem', 'Sunil', 'Samuel',
        'Kajal', 'Shraddha', 'Sonali',
        'Sachin', 'Rohan', 'Krushna'
    ]
    all_data = []
    columns = None

    try:
        for i, sheet in enumerate(sheets):
            if i == 0:
                df = pd.read_excel(temp_path, sheet_name=sheet, header=7)
                columns = list(df.columns)
            else:
                df = pd.read_excel(temp_path, sheet_name=sheet, header=None, skiprows=8)
                if df.shape[1] < len(columns):
                    for c in range(df.shape[1], len(columns)):
                        df[c] = None
                elif df.shape[1] > len(columns):
                    df = df.iloc[:, :len(columns)]
                df.columns = columns
            df.dropna(how='all', inplace=True)
            all_data.append(df)
        df = pd.concat(all_data, ignore_index=True)
        df = clean_rfq_dataframe(df)
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
        df.to_excel(output_path, index=False)
        with open(output_path, 'rb') as out_file:
            content = out_file.read()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
    return content
