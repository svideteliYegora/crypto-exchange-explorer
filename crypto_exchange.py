import asyncio
import itertools as itrt
from urllib.parse import urlparse
from aiohttp import ClientSession
import json


class ExchangeRateCalculator:
    def __init__(self, start_currency: str, end_currency: str, crypto_exchanges_json: str, currencies_list: list = None):
        self.currencies = ['ETH', 'BNB', 'BTC', 'USDT']
        if currencies_list:
            self.currencies.extend(currencies_list)
            self.currencies = list(set(self.currencies))

        self.start_currency = start_currency
        self.end_currency = end_currency

        with open(crypto_exchanges_json, 'r', encoding='UTF-8') as file:
            self.cryptocurrency_exchanges = json.load(file)

        self.best_direct_path = ''
        self.best_complex_path = ''

        self.path_combinations = []
        self.currency_pairs_with_price = []

        self.create_paths()

    def __str__(self):
        return f"The best direct path:\n{self.best_direct_path or 'No data.'}\n\nThe best complex path:\n{self.best_complex_path or 'No data.'}"

    def create_paths(self) -> None:
        '''
        Создает всевозможные комбинации сложных путей.

        Заполняет атрибут self.path_combinations списком списков, представляющих различные комбинации путей.

        :return: None
        '''
        currencies = self.currencies.copy()
        currencies.remove(self.start_currency)
        currencies.remove(self.end_currency)
        for i in range(1, len(currencies) + 1):
            for y in list(itrt.combinations(currencies, i)):
                y = itrt.permutations(y)
                for q in y:
                    self.path_combinations.append([self.start_currency] + list(q) + [self.end_currency])

    async def create_currency_pairs(self) -> None:
        '''
        Последовательно перебирает список сайтов-критобирж `self.fetch_exchange_data`,
        применяя к его элементам метод `self.fetch_exchange_data`, получая валютные пары с ценой обмена.

        Создает и заполняет список задач для ассинхронного выполнения.

        :return: None
        '''
        pair_combo = list(itrt.combinations(self.currencies, 2))
        async with ClientSession() as session:
            tasks = []
            for dt in self.cryptocurrency_exchanges:
                tasks.append(asyncio.create_task(self.fetch_exchange_data(session, dt, pair_combo)))

            await asyncio.gather(*tasks)

    async def fetch_exchange_data(self, session: ClientSession, dt: dict, pair_combo: list) -> None:
        '''
        Получает данные о курсах обмена для заданных валютных пар и заполняет ими атрибут `self.currency_pairs_with_price`.

        :param session: Экземпляр класса `ClientSession()` из `aiohttp`
        :param dt: Словарь, где ключ - это ссылка сайта криптобиржи, а значение - это шаблон для создания параметров в GET запрос.
        :param pair_combo: Список кортежей, представляющих валютные пары для запроса курсов обмена.
        :return: None
        '''
        dicty = {}
        url, params = tuple(dt.items())[0]
        params_key, params_value = tuple(params.items())[0]

        for pair in set(pair_combo):
            try:
                url, params = tuple(dt.items())[0]
                value = params_value.format(pair[0], pair[1])
                params[params_key] = value
                async with session.get(url, params=params) as r:
                    resp = await r.json()
                    if not resp.get('price'):
                        dicty[(pair[0], pair[1])] = float(resp['data']['price'])
                        dicty[(pair[1], pair[0])] = 1 / float(resp['data']['price'])
                    else:
                        dicty[(pair[0], pair[1])] = float(resp['price'])
                        dicty[(pair[1], pair[0])] = 1 / float(resp['price'])
            except:
                try:
                    url, params = tuple(dt.items())[0]
                    value = params_value.format(pair[1], pair[0])
                    params[params_key] = value
                    async with session.get(url, params) as r:
                        resp = await r.json()
                        if not resp.get('price'):
                            dicty[(pair[1], pair[0])] = float(resp['data']['price'])
                            dicty[(pair[0], pair[1])] = 1 / float(resp['data']['price'])
                        else:
                            dicty[(pair[1], pair[0])] = float(resp['price'])
                            dicty[(pair[0], pair[1])] = 1 / float(resp['price'])
                except:
                    dicty[(pair[1], pair[0])] = None
                    dicty[(pair[0], pair[1])] = None

            site = urlparse(url).netloc
            self.currency_pairs_with_price.append({site: dicty})

    def execute_exchange_requests(self) -> None:
        '''
        Вычисляет лучшие прямые и сложные пути на основе пар криптовалют и их цен.

        Функция заполняет `self.best_direct_path` и `self.best_complex_path` вычисленными результатами.

        :return: None
        '''
        direct_paths = {}   # Словарь для прямых путей
        complex_paths = {}  # Словарь для сложных путей

        for item in self.currency_pairs_with_price:
            site, pairs = tuple(item.items())[0]
            pair = (self.start_currency, self.end_currency)
            price = pairs.get(pair)
            if price:
                direct_paths[price] = f'{site}\n{self.start_currency} -> {self.end_currency} -> {price}'
            for path in self.path_combinations:
                buffer_text = ''
                buffer_price = 1
                for i in range(len(path) - 1):
                    pair = (path[i], path[i+1])
                    price = pairs.get(pair)
                    if price is None:
                        buffer_text = ''
                        buffer_price = 1
                        break
                    buffer_price *= price
                    buffer_text += f'{path[i]} -> {path[i+1]} -> {buffer_price}\n'
                if buffer_text:
                    complex_paths[buffer_price] = f'{site}\n{buffer_text}'
                buffer_text = ''
                buffer_price = 1

        if direct_paths:
            best_direct_path_price = list(direct_paths.keys())
            best_direct_path_price.sort(reverse=True)
            self.best_direct_path = direct_paths.get(best_direct_path_price[0])

        if complex_paths:
            best_complex_path_price = list(complex_paths.keys())
            best_complex_path_price.sort(reverse=True)
            self.best_complex_path = complex_paths.get(best_complex_path_price[0])


async def main():
    exchanges_json = 'cryptocurrency_exchanges.json'
    erc = ExchangeRateCalculator('BTC', 'ETH', exchanges_json)
    await erc.create_currency_pairs()
    erc.execute_exchange_requests()
    print(erc)


if __name__ == '__main__':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
