class ApiError(Exception):
    code: str = ''
    status: int = 400
    message: str = 'Unknown error'


class NotAuthorized(ApiError):
    message = 'Вы не авторизованы'
    code = 1
    status = 403


class AlreadyRegistered(ApiError):
    message = 'Вы уже зарегистрированы'
    code = 1
    status = 400


class WrongKeys(ApiError):
    message = 'Вы ввели невалидные ключи'
    code = 1
    status = 400
