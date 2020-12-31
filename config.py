import os
import json

class Config:
    def __init__(self):
        if "HEROKU_TEST" not in os.environ:
            config_ = json.load(open('./config.json', 'rb'))
            for k in config_:
                exec('self.{} = config_["{}"]'.format(k, k))

        else:
            for k in os.environ:
                exec('self.{} = os.environ["{}"]'.format(k, k))

