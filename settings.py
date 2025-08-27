import configparser
import os


def load_config():
    """Загрузка конфигурации из settings.ini"""
    config = configparser.ConfigParser()

    # Проверяем существование файла конфигурации
    if not os.path.exists('settings.ini'):
        raise FileNotFoundError("Файл settings.ini не найден.")

    config.read('settings.ini', encoding='utf-8')
    return config


# Загружаем конфигурацию при импорте
config = load_config()

# Настройки базы данных
DB_CONFIG = {
    'dbname': config['Database']['dbname'],
    'user': config['Database']['user'],
    'password': config['Database']['password'],
    'host': config['Database']['host'],
    'port': config['Database']['port']
}

# Токен бота
BOT_TOKEN = config['Bot']['token']
