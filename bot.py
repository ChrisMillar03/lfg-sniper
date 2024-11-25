import os
import re
import json
import base64
import time
import datetime
import threading
import requests
import websocket
import sqlite3
from dotenv import load_dotenv

reactions = {
	"grey_question": "%E2%9D%94",
	"white_check_mark": "%E2%9C%85",
	"x": "%E2%9D%8C",
	"zzz": "%F0%9F%92%A4"
}

cmd_channels = {}

with open("channels.json", "r") as f:
	cmd_channels = json.load(f)

class LFGSniper:
	def __init__(self, token, admin_id):
		self.prefix = ">"
		self.token = token
		self.admin_id = admin_id
		self.id = base64.b64decode(token.split(".")[0]).decode("utf-8")
		self.db = sqlite3.connect(f"{self.id}.db")
		self.ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=10&encoding=json",
			on_open=self.on_open,
			on_message=self.on_message,
			on_error=self.on_error,
			on_close=self.on_close)
		self.heartbeat = 0
		self.heartbeat_thread = None
		self.update_thread = None

	def send(self, data):
		self.ws.send(json.dumps(data))

	def get_targets(self):
		targets = []
		cursor = self.db.execute("SELECT * FROM `targets`;")

		for row in cursor:
			targets.append(row)

		return targets

	def add_target(self, uid, reason):
		self.db.execute("INSERT INTO `targets` (`id`, `reason`) VALUES (?, ?) ON CONFLICT(`id`) DO UPDATE SET `reason`=?;", (uid, reason, reason))
		self.db.commit()

	def remove_target(self, uid):
		self.db.execute("DELETE FROM `targets` WHERE `id`=?;", (uid,))
		self.db.commit()

	def send_reaction(self, channel, message, reaction):
		if not cmd_channels[channel]:
			return

		embed_json = {
			"content": f":{reaction}:",
			"embeds": None,
			"attachments": []
		}

		requests.post(cmd_channels[channel], embed_json)

		# headers = { "Authorization": self.token }
		# return requests.put(f"https://discord.com/api/v10/channels/{channel}/messages/{message}/reactions/{reactions[reaction]}/@me?location=Message&type=0", headers=headers)

	def get_hitlist(self, search_ids):
		targets = [i for i in self.get_targets() if not search_ids or i[0] in search_ids]
		chunk_size = 10
		chunks = [targets[i:i + chunk_size] for i in range(0, len(targets), chunk_size)]
		embeds = []

		for i, chunk in enumerate(chunks):
			ids = [f"<@{j[0]}>" for j in chunk]
			reasons = [j[1] or "N/A" for j in chunk]

			embeds.append({
				"title": f"Targets #{str(i + 1)}",
				"color": None,
				"fields": [
					{
						"name": "User",
						"value": "\n".join(ids),
						"inline": True
					},
					{
						"name": "Reason",
						"value": "\n".join(reasons),
						"inline": True
					}
				]
			})

		embed_json = {
			"content": None if len(targets) > 0 else "No targets stored",
			"embeds": embeds,
			"attachments": []
		}

		return embed_json

	def post_to_webhooks(self, msg, ids):
		timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")

		embed_json = {
			"content": None,
			"embeds": [
				{
					"description": msg["content"],
					"color": None,
					"author": {
						"name": msg["author"]["username"],
						"url": f"https://discord.com/channels/{msg['guild_id']}/{msg['channel_id']}/{msg['id']}",
						"icon_url": f"https://cdn.discordapp.com/avatars/{msg['author']['id']}/{msg['author']['avatar']}.png"
					},
					"timestamp": timestamp
				}
			] + self.get_hitlist(ids)["embeds"],
			"attachments": []
		}

		for i in cmd_channels.values():
			requests.post(i, json=embed_json)

	def parse_command(self, msg):
		args = re.split("\s+", msg["content"])
		cmd = args.pop(0).lower()

		if not cmd.startswith(self.prefix):
			return None

		match cmd[len(self.prefix):]:
			case "add":
				if len(args) < 1:
					return "x"

				uid = args.pop(0)
				reason = " ".join(args)

				if len(reason) > 100:
					return "x"

				if not uid.isnumeric() or len(uid) not in [18, 19]:
					return "x"

				self.add_target(uid, reason)
				
				return "white_check_mark"

			case "checkban":
				headers = {
					"Authorization": self.token
				}

				res = requests.get("https://discord.com/api/v9/users/@me/guilds", headers=headers)

				if any([i["id"] == "253581140072464384" for i in res.json()]):
					return "green_circle"

				return "red_circle"

			case "hitlist":
				requests.post(cmd_channels[msg["channel_id"]], json=self.get_hitlist(None))

				return None

			case "ping":
				return "zzz"

			case "remove":
				if msg["author"]["id"] != self.admin_id:
					return "x"

				if len(args) < 1:
					return "x"

				self.remove_target(args.pop(0))
				
				return "white_check_mark"

			case "testwebhooks":
				if msg["author"]["id"] != self.admin_id:
					return "x"

				embed_json = {
					"content": None,
					"embeds": [
						{
							"title": "Webhook is working!",
							"color": None,
						}
					],
					"attachments": []
				}

				for i in cmd_channels.values():
					requests.post(i, json=embed_json)

				return None

			case _:
				return "grey_question"

	def _heartbeat_thread(self):
		print("Heartbeat begun")

		while self.heartbeat > 0:
			heartbeat_json = {
				"op": 1,
				"d": None
			}

			self.send(heartbeat_json)

			print("Heartbeat sent")

			time.sleep(self.heartbeat)

		print("Heartbeat stopped")

	def _update_thread(self):
		print("Updater begun")

		while self.heartbeat > 0:
			# Make sure guild messages are visible
			update_json = {
				"op": 14,
				"d": {
					"guild_id": "253581140072464384",
					"typing": True,
					"threads": False,
					"activities": True,
					"members": [],
					"channels": {
						"975773650701672509": [
							[0, 99]
						]
					}
				}
			}

			self.send(update_json)

			time.sleep(1)

		print("Updater stopped")

	def join_threads(self):
		self.heartbeat = 0

		if self.update_thread.is_alive():
			self.update_thread.join()

		if self.heartbeat_thread.is_alive():
			self.heartbeat_thread.join()

	def on_close(self, ws, status, msg):
		print(f"[{status}] {msg}")

		self.join_threads()

	def on_error(self, ws, err):
		print(f"[ERROR] {err}")

		self.join_threads()

	def on_message(self, ws, msg):
		event = json.loads(msg)

		match event["op"]:
			case 10:
				print("Heartbeat set")

				self.heartbeat = int(event["d"]["heartbeat_interval"] / 1000)
				self.heartbeat_thread.start()
				self.update_thread.start()

			case 11:
				print("Heartback ack")

			case _:
				if event["t"] == "MESSAGE_CREATE":
					# check message is in command channel
					if event["d"]["channel_id"] in cmd_channels.keys():
						reaction = self.parse_command(event["d"])

						if reaction:
							self.send_reaction(event["d"]["channel_id"], event["d"]["id"], reaction)

						return

					# check message is in lfg ranked channel
					if event["d"]["channel_id"] not in ["269519917693272074", "269566972977610753"]:
						return

					# check author is FairFight Jr
					if event["d"]["author"]["id"] != "278980093102260225":
						return

					ids = [i["id"] for i in event["d"]["mentions"]]
					targets = [i[0] for i in self.get_targets()]

					if any([i in targets for i in ids]):
						self.post_to_webhooks(event["d"], ids)

	def on_open(self, ws):
		self.heartbeat_thread = threading.Thread(target=self._heartbeat_thread)
		self.update_thread = threading.Thread(target=self._update_thread)

		auth_json = {
			"op": 2,
			"d": {
				"token": self.token,
				"capabilities": 61,
				"properties": {
					"$os": "Windows 10",
					"$device": "Windows",
					"$browser": "Google Chrome"
				}
			}
		}

		self.send(auth_json)

	def start(self):
		if self.heartbeat > 0:
			return

		self.db.execute("CREATE TABLE IF NOT EXISTS `targets` (`id` VARCHAR(20) PRIMARY KEY NOT NULL, `reason` VARCHAR(100));")

		while True:
			try:
				print("Restarting...")
				self.ws.run_forever()
			except:
				pass

def main():
	bot = LFGSniper(os.getenv("TOKEN"), os.getenv("ADMIN_ID"))
	bot.start()

if __name__ == "__main__":
	load_dotenv()
	main()
