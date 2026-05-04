# RFQ

Django website for cleaning RFQ Excel submissions and exporting a cleaned workbook.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run database migrations:
   ```bash
   python manage.py migrate
   ```
4. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Usage

Open `http://127.0.0.1:8000/` in your browser. Upload an RFQ Excel file and download the cleaned workbook.
