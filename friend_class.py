import tweepy
import re
import os
from config import Config
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pymongo import MongoClient

def friendInOne(
    USER_NAME=None,
    EMAIL_TO=None,
    EMAIL_FROM=None
):
    fc = friendComparer(USER_NAME, EMAIL_TO, EMAIL_FROM)
    fc.wholeComparer()
    fc.updateFriends()
    fc.sendEmail()

class friendComparer(Config):
    def __init__(self, 
        USER_NAME=None,
        EMAIL_TO=None,
        EMAIL_FROM=None
        ):
        super().__init__()

        if USER_NAME is not None:
            self.USER_NAME = USER_NAME

        if EMAIL_FROM is not None:
            self.EMAIL_FROM = EMAIL_FROM
        
        if EMAIL_TO is not None:
            self.EMAIL_TO = EMAIL_TO
        
        print('running friend comparer for: ', self.USER_NAME)
        self.dbClient()
        self.tweepyClient()

        return
    
    def dbClient(self):
        """
        Initiate mongoDB connection and get og friends list
        """
        # 'fff' is db name
        self.client = MongoClient(
    "mongodb+srv://blanky_blank:{}@fff-cluster.6blj2.mongodb.net/{}?retryWrites=true&w=majority".format(
        self.MONGO_PW, 'fff'
    ))
        
        self.col = self.client['db']['all_users']
        try:
            og_friends = [f for f in self.col.find({'user_name': self.USER_NAME})][0]['friends']
            self.og_friends = [f['user_id'] for f in og_friends] # only need user ids
        except IndexError:
            print('no data found, making blank data')
            self.col.insert_one(
                {
                    'user_name': self.USER_NAME,
                    'friends': []
                }
            )
            self.og_friends = [f for f in self.col.find({'user_name': self.USER_NAME})][0]['friends']

        
    def tweepyClient(self):
        """
        Initiate tweepy connection
        """
        
        auth = tweepy.OAuthHandler(self.CONSUMER_KEY, self.CONSUMER_SECRET)
        auth.set_access_token(self.ACCESS_TOKEN, self.ACCESS_TOKEN_SECRET)

        self.api = tweepy.API(auth, 
                              wait_on_rate_limit=True, 
                              wait_on_rate_limit_notify=True, 
                              retry_count=3, 
                              retry_delay=60)
        
    def getNewFriends(self):
        """
        Load friends list
        """
        self.new_friends = []
        page_count = 0
        for page in tweepy.Cursor(self.api.friends_ids, id=self.USER_NAME, count=5000).pages():
            page_count += 1
            self.new_friends.extend(page)

    def compareFriends(self):
        """
        Find if friends have been added or removed
        """
        self.added = [f for f in self.new_friends if f not in self.og_friends]
        self.unfollowed = [f for f in self.og_friends if f not in self.new_friends]
        print(self.USER_NAME, 'added: ', str(len(self.added)))
        print(self.USER_NAME, 'unfollowed: ', str(len(self.unfollowed)))

    def getScreenNames(self, id_list):
        """
        Make list of friend user ids and user names from a list of ids
        """
        start = 0
        batch_size = 100
        user_data = []
        id_list = [0] + id_list + [0]
        if set(id_list) == {0}:
            return user_data
            
        while start < len(id_list):
            print(start)
            new_user_names = self.api.lookup_users(
                user_ids=[id_list[start:start+batch_size]],
                include_entities=True
            )
            print(len(new_user_names))
            new_user_data = [(u.id, u.screen_name) for u in new_user_names]
            print(len(new_user_data))
            user_data += new_user_data
            start += batch_size
            print(len(user_data))
            print('***')
        
        
        if len(user_data) < len(id_list):
            print('rerunning...')
            searched_ids = [f[0] for f in user_data]
            missed_ids = [f for f in id_list if f not in searched_ids]
            print(len(id_list))
            print(len(user_data))
            print(len(missed_ids))
            print(missed_ids)
            user_data += self.getScreenNames(missed_ids)
            return user_data
            
        else:
            print('...')
            return user_data
    
    def updateFriends(self):
        """
        Update friends list in database
        """
        self.new_friend_data = self.getScreenNames(self.new_friends)
        new_q = {'user_name': self.USER_NAME}
        new_data = {'$set': {
            'friends': [{'user_id': f[0], 'user_name': f[1]} for f in self.new_friend_data],
            'user_name': self.USER_NAME
        }
                   }
        
        self.col.update_one(new_q, new_data)
        print('friends list updated')
    
    def sendEmail(self):
        if not self.added and not self.unfollowed:
            print('no change')
            return
            
        else:
            added_data = self.getScreenNames(self.added)
            unfollowed_data = self.getScreenNames(self.unfollowed)
            text_ = """
            New friends for {}:
            {}
            
            Unfollowed by {}:
            {}
            """.format(self.USER_NAME, 
                ', '.join([f[1] for f in added_data]),
                self.USER_NAME, 
                ', '.join([f[1] for f in unfollowed_data]))
            print(text_)
            
            message = Mail(
            from_email=self.EMAIL_FROM,
            to_emails=self.EMAIL_TO,
            subject='{} Friends Update'.format(self.USER_NAME),
            plain_text_content=text_
            )
        try:
            sg = SendGridAPIClient(self.SENDGRID_KEY)
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.args)
            
            
    def wholeComparer(self):
        self.getNewFriends()
        self.compareFriends()
