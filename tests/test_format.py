def format_wa_number(wa_id):
    if not wa_id:
        return ''
    wa_id = wa_id.strip()
    if not wa_id.startswith('+'):
        return f'+{wa_id}'
    return wa_id

print(f'Test 1 (+447447840003): {format_wa_number("+447447840003")}')
print(f'Test 2 (447447840003): {format_wa_number("447447840003")}')

# Now test the actual app.py function
import os
os.environ["MESSAGES_TABLE_NAME"] = "test"
os.environ["MESSAGES_PK_NAME"] = "test"
os.environ["MEDIA_BUCKET"] = "test"

from app import format_wa_number as app_format

print(f'App Test 1 (+447447840003): {app_format("+447447840003")}')
print(f'App Test 2 (447447840003): {app_format("447447840003")}')
