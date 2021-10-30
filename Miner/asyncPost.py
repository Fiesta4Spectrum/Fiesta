from multiprocessing import Process
import requests

class AsyncPost(Process):

    def __init__(self, target_list, content, api):
        super().__init__() # damn idiot python, will not call super init for you !!!
        self.list = target_list
        self.content = content
        self.api = api

    def run(self):
        for addr in self.list:
            try:
                requests.post(
                    url = addr + self.api,
                    json = self.content
                )
            except requests.exceptions.ConnectionError:
                print("[AsyncPost] Fails to connect to " + addr)