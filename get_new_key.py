import engine.security
from pathlib import Path

tokendata = [
    'user:' + input('Discord ID? '),
    'isLevel' + input('(int) isLevel? ')
]  # isLevel1 means basic user

times = int(input('(int) TIMES? '))

while times > 0:
    APIKey=(engine.security.create_api_key(*tokendata, key_storage_file=Path('engine/key.json')).decode())
    print(APIKey)
    print(engine.security.decrypt_api_key(APIKey, key_storage_file=Path('engine/key.json')))
    times -= 1