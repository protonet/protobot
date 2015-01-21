#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  protobot.py [Version 1.2]
#  
#  Copyright 2015 Silvano Wegener [Protonet GmbH]

import requests, json, time, thread, urllib2
import sys, os

class ProtonetServerConnection(object):
	def __init__(self, server, user, password):
		self.server = server
		self.url = "https://"+self.server+'/api/v1/'
		self.user = user
		self.password = password
		self.auth = (self.user, self.password)
		self.users = self.get_users()
		self.me = self.__get_own_data()
		self.username = self.me['username']
		self.first_name = self.me['first_name']
		self.last_name = self.me['last_name']
		self.email = self.me['email']
		self.id = self.me['id']

	def __get_own_data(self):
		response = requests.get(self.url + 'me', auth=self.auth)
		data = response.json()['me']	
		return data

	def get_users(self):
		response = requests.get(self.url + 'users', auth=self.auth)
		users = response.json()['users']
		data = {}
		for user in users:
			entry = {}
			entry['first_name'] = user['first_name']
			entry['last_name'] = user['last_name']
			entry['url'] = user['url']
			entry['deactivated'] = user['deactivated']
			entry['email'] = user['email']
			entry['role'] = user['role']
			entry['avatar']	= user['avatar']
			entry['online'] = user['online']
			entry['id'] = user['id']
			entry['last_active_at'] = user['last_active_at']
			data[user['username']] = entry
		return data

	def get_private_chats(self):
		data = {}
		response = requests.get(self.url + 'private_chats', auth=self.auth)
		chats = response.json()['private_chats']
		for chat in chats:
			entry = {}
			entry['username'] =  chat['other_user']['username']
			entry['user_id'] = chat['other_user']['id']
			entry['last_seen_meep_no'] = chat['subscription']['last_seen_meep_no']
			entry['subscription_id'] = os.path.split(chat['subscription']['url'])[1]
			data[chat['id']] = entry
		return data

	def get_private_chat_ids(self):
		data = self.get_private_chats().keys()
		return sorted(data)

	def get_private_chats_content(self, chat_id=False):
		chats = self.get_private_chats()
		data = {}
		if chat_id == False:
			for key in chats.keys():
				data[key] = []
				response = requests.get(self.url + 'private_chats/' + str(key) + '/meeps?limit=5' , auth=self.auth)
				meeps = response.json()['meeps']
				for id, meep in enumerate(meeps[::-1]):
					entry = self.__create_entry(meep, id, key)
					data[key].append(entry)
		else:
			data = []
			response = requests.get(self.url + 'private_chats/' + str(chat_id) + '/meeps?limit=5' , auth=self.auth)
			meeps = response.json()['meeps']
			for id, meep in enumerate(meeps[::-1]):
				entry = self.__create_entry(meep, id, chat_id)
				data.append(entry)
		return data
		
	def __create_entry(self, meep, id, chat_id):
		entry = {}
		entry['id'] = id
		entry['message'] = meep['message']
		entry['type'] = meep['type']
		entry['files'] = meep['files']
		entry['sender'] = meep['user']['username']
		entry['no'] = meep['no']
		entry['meep_id'] = meep['id']
		entry['private_chat_id'] = chat_id
		return entry	

	def crate_private_chat(self, username):
		headers = {'content-type': 'application/json;charset=UTF-8'}
		user_id = self.users[username]['id']
		data = {'other_user_id':  user_id}
		data_json = json.dumps(data)
		response = requests.post(self.url + 'private_chats', auth=self.auth, data=data_json, headers=headers)
		chat = response.json()
		return chat['private_chat']['id']

	def send_private_chat_meep(self, receiver, message, files=[]):
		chat_id = self.crate_private_chat(receiver)
		if chat_id == False:
			return False
		headers = {'content-type': 'application/json;charset=UTF-8'}
		data = {'message':  message}
		data_json = json.dumps(data)
		lurl = self.url + 'private_chats/' + str(chat_id) + '/meeps'
		response = requests.post(lurl , auth=self.auth, data=data_json, headers=headers)
		return response

	def set_last_seen_meep(self, chat_id, subscription_id, meep_no):
		headers = {'content-type': 'application/json;charset=UTF-8'}
		data = {'last_seen_meep_no':  meep_no}
		data_json = json.dumps(data)
		response = requests.put(self.url + 'private_chats/' + str(chat_id) + '/subscriptions/'+subscription_id , auth=self.auth, data=data_json, headers=headers)






class ProtoBot(object):
	def __init__(self, protonet_server, protonet_username, answers, default_msg='Das habe ich leider nicht verstanden.'):
		self.answers = answers
		self.protonet_server = protonet_server
		self.username = protonet_username
		self.terminate = False
		self.default_msg = default_msg
		self.robot_thread_run = thread.start_new_thread(self.robot_thread, (None,))

	def robot_thread(self, value):
		self.set_all_meeps_as_seen()
		while not self.terminate:
			try:
				for meep in self.get_new_meeps():
					chat_id = meep['private_chat_id']
					subscription_id = meep['subscription_id']
					meep_no = meep['no']
					sender = meep['sender']
					message = meep['message'].lower()
					
					if sender == self.username:
						self.set_last_seen_meep(chat_id, subscription_id, meep_no)
						continue

					print sender + ": " + message
					
					try:
						message = self.answers[message]
						if 'tuple' in str(type(message)):
							message = message[0](message[1]).read()
					except KeyError:
						message = self.default_msg

					self.set_last_seen_meep(chat_id, subscription_id, meep_no)
					self.protonet_server.send_private_chat_meep(sender, message)
			except:
				pass

			time.sleep(1)

	def set_all_meeps_as_seen(self):
		private_chats = self.protonet_server.get_private_chats()
		private_chats_content = self.protonet_server.get_private_chats_content()

		for key in private_chats.keys():
			subscription_id = private_chats[key]['subscription_id']
			privat_chat_id = key
			try:
				last_meep_id = private_chats_content[key][-1]['no']
				self.protonet_server.set_last_seen_meep(privat_chat_id, subscription_id, last_meep_id)
			except:
				pass

	def get_new_meeps(self):
		private_chats = self.protonet_server.get_private_chats()
		private_chats_content = self.protonet_server.get_private_chats_content()
		meeps = []
		for key in private_chats.keys():
			last_seen_meep = private_chats[key]['last_seen_meep_no']
			subscription_id = private_chats[key]['subscription_id']
			for meep in private_chats_content[key]:
				if meep['no'] > last_seen_meep:
					meep['subscription_id'] = subscription_id
					meeps.append(meep)
		return meeps
		
	def set_last_seen_meep(self, chat_id, subscription_id, meep_no):
		self.protonet_server.set_last_seen_meep(chat_id, subscription_id, meep_no)

	def get_timestamp(self):
		stamp = time.strftime("%a_%H_%M").split('_')
		return stamp

	def __del__(self):
		self.terminate = True
		time.sleep(3)



default_message = 'Das habe ich leider nicht verstanden.'

answers = {}
answers['ip?'] = (os.popen, 'ifconfig')  # (python funktion, parameter)
answers['hallo'] = 'Guten Tag! :)'		 # normale Antwort
answers['kaffee'] = 'Gibt`s nicht! :P'

server = sys.argv[1]
email = sys.argv[2]
password = sys.argv[3]


serverConnection = ProtonetServerConnection(server, email, password)
bot = ProtoBot(serverConnection, serverConnection.username, answers, default_message)
try:
	while True:
		time.sleep(1)
except KeyboardInterrupt:
	del bot
	sys.exit()

