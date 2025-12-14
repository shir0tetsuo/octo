import uuid
def is_valid_uuid4(ID:str):
    '''Checks if a string is a valid UUIDv4.'''
    try:
        if len(ID) == 36:
            uuid_obj = uuid.UUID(ID, version=4)
        else:
            raise ValueError('Length of ID not equal to 36 (Invalid ID).')
    except (ValueError, AttributeError, TypeError):
        return False
    return str(uuid_obj) == ID.lower()