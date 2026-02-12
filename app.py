import random
import requests
import json

# 创建用户类
class User(object):

    def __init__(self, username, post_frequency, post_prompt):
        self.username = username
        self.frequency = post_frequency
        self.prompt = post_prompt

    def post(self):
        return self.prompt



# 导入用户信息
user_config = []
with open("ai_users_config.json", "r", encoding= "UTF-8") as USER_CONFIG:
    config = json.load(USER_CONFIG)
    for user in config["ai_users"]:
        user_config.append(User(
            user["username"],
            user["post_frequency"],
            user["post_prompt"])
        )





