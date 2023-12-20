import requests
import json
import configparser
import os
import time
from progress.bar import IncrementalBar
from urllib.parse import urlencode
from pprint import pprint


class VKAPIClient:
    API_BAS_URL = 'https://api.vk.com/method'

    def __init__(self, token, user_id):
        self.token = token
        self.user_id = user_id

    def get_common_params(self):
        return {
            'access_token': self.token,
            'v': '5.199'
        }

    def _build_url(self, api_metod):
        return f'{self.API_BAS_URL}/{api_metod}'

    def get_profile_photos(self):
        params = self.get_common_params()
        params.update({'owner_id': self.user_id,
                       'album_id': 'profile',
                       'extended': 1,
                       'photo_sizes': 1})
        response = requests.get(self._build_url('photos.get'),
                                params=params)
        return response.json()


class YDClient:
    API_BAS_URL = 'https://cloud-api.yandex.net'

    def __init__(self, oAuth_token):
        self.Authorization = 'OAuth ' + oAuth_token

    def get_create_folder(self, name_folder):
        url_create_folder = self.API_BAS_URL + '/v1/disk/resources'
        params_dict = {'path': name_folder}
        headers_dict = {'Authorization': self.Authorization}
        response = requests.put(url_create_folder,
                                params=params_dict,
                                headers=headers_dict)
        return response.status_code

    def get_discharge(self, name_folder, name_file):
        # вариант для выгрузки в 2 этапа (через ж.диск)
        # запрос url на ЯД
        url_get_link = self.API_BAS_URL + '/v1/disk/resources/upload'
        params_dict = {
            'path': f'{name_folder_for_cloud}/{name_file}'}
        headers_dict = {'Authorization': self.Authorization}

        response = requests.get(url_get_link,
                                params=params_dict,
                                headers=headers_dict)

        url_for_upload = response.json().get('href')

        # Загрузить файл по полученному адресу.
        with open(name_file, 'rb') as file:
            response = requests.put(url_for_upload,
                                    files={"file": file},
                                    headers=headers_dict)
            # print(response.status_code)
        return (response.status_code)

    def get_discharge_url(self, name_folder, url_file, name_file):
        # вариант для выгрузки через url (2)
        url_for_upload = self.API_BAS_URL + '/v1/disk/resources/upload'
        params_dict = {'url': url_file,
                       'path': f'{name_folder}/{name_file}'}
        headers_dict = {'Authorization': self.Authorization}
        response = requests.post(url_for_upload, params=params_dict,
                                 headers=headers_dict)
        return (response.status_code)


if __name__ == '__main__':
    config = configparser.ConfigParser()  # создаём объекта парсера
    config.read("settings.ini")  # читаем конфиг

    # идентификационные данные
    token = config["VK"]["token"]
    oAuth_token = config["YD"]["token"]
    vk_client = VKAPIClient(token, config["VK"]["user_id"])
    yd_client = YDClient(oAuth_token)

    # получаем путь для json-файла с отчетом по выгрузке "file_for_discharge.json"
    file_path = os.path.join(os.getcwd(), 'file_for_discharge.json')

    # получаем данные о фото из ВК
    photos = vk_client.get_profile_photos()

    # формирум словарь "photos_from_vk" из ВК
    # и перечень в виде списка "photos_list"
    photos_from_vk = {}
    photos_list = photos['response']['items']
    for item in photos_list:
        photos_from_vk[item['id']] = {'file_name': '', 'size': '', 'url': ''}
        max_size = 1
        for size in item['sizes']:
            if size['url'] and size['height'] * size['width'] > max_size:
                max_size = size['height'] * size['width']
                file_max_name = f"{item['likes']['count'] + item['likes']['user_likes']}_{item['id']}.jpg"
                photos_from_vk[item['id']] = {'file_name': f'{file_max_name}', 'size': size['type'],
                                              'url': f"{size['url']}"}
    photos_list = list(photos_from_vk)

    # создаем папку на ЯД и получаем ссылку для дальнейшего использования
    name_folder_for_cloud = input('Введите имя папки для ЯД: ')
    result = yd_client.get_create_folder(name_folder_for_cloud)
    while result > 202:
        print('Возникла проблема при создании папки, код: ', result)
        name_folder_for_cloud = input('Попробуйте ввести другое имя папки для ЯД: ')
        result = yd_client.get_create_folder(name_folder_for_cloud)
    else:
        print(f'папка {name_folder_for_cloud} создана, код: {result}')

    # запрашиваем кол-во фото для выгрузки
    print(f'У Вас в профиле {len(photos_from_vk)} фотографий.')
    how_many_photos = int(input('Введите количество, которое Вы хотите выгрузить на Яндекс диск: '))
    while how_many_photos < 1 or how_many_photos > len(photos_from_vk):
        how_many_photos = int(input(
            f'Введите корректное количество (от 1 до {len(photos_from_vk)}), которое Вы хотите выгрузить на Яндекс диск: '))

    while result not in ('1', '2'):
        print("Введите 1 - загрузить файлы из интернет")
        print("        2 - сохранить на ПК и отправить на ЯД")
        result = input()

    # запускаем цикл отбора и отправки фото на ЯД
    bar = IncrementalBar('Countdown', max=how_many_photos)

    photos_for_cloud = []
    for i in range(how_many_photos):
        url_file = photos_from_vk.get(photos_list[i])['url']
        name_file = photos_from_vk.get(photos_list[i])['file_name']

        if result == '1':
            # загружаем файл на ЯД из url
            print(f'файл {name_file} загружен' if 201 <= yd_client.get_discharge_url(name_folder_for_cloud, url_file,
                                                                                     name_file) <= 202 else 'что-то пошло не так')
        else:
            # загружаем фото из ВК себе на диск (пока не работает выгрузка по url)
            response = requests.get(url_file)
            with open(name_file, 'wb') as file:
                file.write(response.content)
            # загружаем файл на ЯД (2 этапа) cd
            print(yd_client.get_discharge(name_folder_for_cloud, name_file))

        # копим инфо в json-файл о загруженных файлах
        photos_for_cloud.append({'file_name': photos_from_vk.get(photos_list[i])['file_name'],
                                 'size': photos_from_vk.get(photos_list[i])['size']})
        bar.next()
        time.sleep(1)

    bar.finish()

    # вносим инфо в json-файл о загруженных файлах
    with open(file_path, 'w') as f:
        json.dump(photos_for_cloud, f, ensure_ascii=False, indent=4)
