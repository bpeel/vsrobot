#!/usr/bin/python3

import urllib.request
import json
import io
import html
import sys
import time
import os
import random

ALL_TILES = ("AAAAAAAAABBBCCĈĈDDDEEEEEEEEFFFGGĜĜHHĤIIIIIIIIIIJJJJJĴKKKKKKLL"
             "LLMMMMMMNNNNNNNNOOOOOOOOOOOPPPPPRRRRRRRSSSSSSSŜŜTTTTTUUUŬŬVVZ")
N_TILES_PER_GAME = 3

conf_dir = os.path.expanduser("~/.vsrobot")
update_id_file = os.path.join(conf_dir, "update_id")
apikey_file = os.path.join(conf_dir, "apikey")

with open(apikey_file, 'r', encoding='utf-8') as f:
    apikey = f.read().rstrip()

urlbase = "https://api.telegram.org/bot" + apikey + "/"
get_updates_url = urlbase + "getUpdates"
send_message_url = urlbase + "sendMessage"

try:
    with open(update_id_file, 'r', encoding='utf-8') as f:
        last_update_id = int(f.read().rstrip())
except FileNotFoundError:
    last_update_id = None

class GetUpdatesException(Exception):
    pass

class ProcessCommandException(Exception):
    pass

class User:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.words = []

class Game:
    def __init__(self):
        self.players = {}
        self.player_order = []
        self.started = False
        self.tile_pos = 0

        tiles = list(ALL_TILES)
        for i in range(len(tiles) - 1, 0, -1):
            j = random.randrange(0, i + 1)
            tiles[i], tiles[j] = tiles[j], tiles[i]

        self.tile_bag = tiles[0 : N_TILES_PER_GAME]
        self.tiles_in_play = []
        
    def add_player(self, player):
        if len(self.players) == 0:
            self.next_go = player
        self.players[player.id] = player
        self.player_order.append(player)

    def turn(self):
        if self.tile_pos >= len(self.tile_bag):
            return False

        if not self.started:
            self.started = True

        self.tiles_in_play.append(self.tile_bag[self.tile_pos])
        self.tile_pos += 1
        this_index = self.player_order.index(self.next_go)
        self.next_go = self.player_order[(this_index + 1) %
                                         len(self.player_order)]

        return True

the_game = None

def send_message(args):
    try:
        req = urllib.request.Request(send_message_url,
                                     json.dumps(args).encode('utf-8'))
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        rep = json.load(io.TextIOWrapper(urllib.request.urlopen(req), 'utf-8'))
    except urllib.error.URLError as e:
        raise ProcessCommandException(e)
    except json.JSONDecodeError as e:
        raise ProcessCommandException(e)

    try:
        if rep['ok'] is not True:
            raise ProcessCommandException("Unexpected response from "
                                          "sendMessage request")
    except KeyError as e:
        raise ProcessCommandException(e)

def report_status(chat):
    buf = []

    if the_game.started:
        buf.append("<b>Literoj:</b>\n\n")
        buf.append(' '.join(the_game.tiles_in_play))
        buf.append("\n\n")

    for player in the_game.player_order:
        if player == the_game.next_go:
            buf.append("👉 ")
        buf.append("<b>")
        buf.append(html.escape(player.name))
        buf.append("</b>\n")
        buf.append(html.escape(', '.join(player.words)))
        buf.append("\n\n")

    if not the_game.started:
        buf.append("Tajpu /turni por komenci la ludon aŭ atendu "
                   "pli da ludantoj")

    args = {
        'chat_id' : message['chat']['id'],
        'text' : ''.join(buf),
        'parse_mode' : 'HTML'
    }

    send_message(args)

def save_last_update_id(last_update_id):
    with open(update_id_file, 'w', encoding='utf-8') as f:
        print(last_update_id, file=f)

def is_valid_update(update, last_update_id):
    try:
        update_id = update["update_id"]
        if not isinstance(update_id, int):
            raise GetUpdatesException("Unexpected response from getUpdates "
                                      "request")
        if last_update_id is not None and update_id <= last_update_id:
            return False

        if 'message' not in update:
            return False

        message = update['message']

        if 'chat' not in message:
            return False
    except KeyError as e:
        raise GetUpdatesException(e)

    return True

def get_updates(last_update_id):
    args = {
        'timeout': 60 * 5,
        'allowed_updates': ['message']
    }

    if last_update_id is not None:
        args['offset'] = last_update_id + 1

    try:
        req = urllib.request.Request(get_updates_url,
                                     json.dumps(args).encode('utf-8'))
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        rep = json.load(io.TextIOWrapper(urllib.request.urlopen(req), 'utf-8'))
    except urllib.error.URLError as e:
        raise GetUpdatesException(e)
    except json.JSONDecodeError as e:
        raise GetUpdatesException(e)

    try:
        if rep['ok'] is not True or not isinstance(rep['result'], list):
            raise GetUpdatesException("Unexpected response from getUpdates "
                                      "request")
    except KeyError as e:
        raise GetUpdatesException(e)
        
    updates = [x for x in rep['result'] if is_valid_update(x, last_update_id)]
    updates.sort(key = lambda x: x['update_id'])
    return updates

def get_from_user(message):
    if 'from' not in message:
        return None

    from_user = message['from']
    if 'id' not in from_user or 'first_name' not in from_user:
        return None

    return User(from_user['id'], from_user['first_name'])

def send_reply(message, note):
    args = {
        'chat_id' : message['chat']['id'],
        'text' : note,
        'reply_to_message_id' : message['message_id']
    }

    send_message(args)

def command_komenci(message, args):
    global the_game

    user = get_from_user(message)

    if user is None:
        return

    if the_game is None:
        the_game = Game()
        the_game.add_player(user)
        report_status(message['chat'])
    else:
        send_reply(message, "La ludo jam komenciĝis")

def command_aligxi(message, args):
    global the_game

    user = get_from_user(message)

    if user is None:
        return

    if the_game is None:
        send_reply(message, "Estas neniu ludo. Tajpu /komenci por komenci unu")
    elif user.id in the_game.players:
        send_reply(message, "Vi jam estas en la ludo")
    elif the_game.started:
        send_reply(message, "La ludo jam komenciĝis")
    else:
        the_game.add_player(user)
        report_status(message['chat'])

def command_turni(message, args):
    global the_game

    user = get_from_user(message)

    if user is None:
        return

    if the_game is None:
        send_reply(message, "Estas neniu ludo. Tajpu /komenci por komenci unu")
    elif user.id != the_game.next_go.id:
        send_reply(message, "Ne estas via vico")
    elif not the_game.turn():
        send_reply(message,
                   "La literoj elĉerpiĝis. "
                   "Tajpu /fini por fini la ludon")
    else:
        report_status(message['chat'])

command_map = {
    '/aligxi' : command_aligxi,
    '/komenci' : command_komenci,
    '/turni' : command_turni
}

def process_command(message, command, args):
    if command in command_map:
        command_map[command](message, args)

def find_command(message):
    if 'entities' not in message or 'text' not in message:
        return None

    for entity in message['entities']:
        if 'type' not in entity or entity['type'] != 'bot_command':
            continue

        start = entity['offset']
        length = entity['length']
        # For some reason the offsets are in UTF-16 code points
        text_utf16 = message['text'].encode('utf-16-le')
        command_utf16 = text_utf16[start * 2 : (start + length) * 2]
        command = command_utf16.decode('utf-16-le')
        remainder_utf16 = text_utf16[(start + length) * 2 :]
        remainder = remainder_utf16.decode('utf-16-le')

        return (command, remainder)

    return None

while True:
    try:
        updates = get_updates(last_update_id)
    except GetUpdatesException as e:
        print("{}".format(e), file=sys.stderr)
        # Delay for a bit before trying again to avoid DOSing the server
        time.sleep(60)
        continue

    for update in updates:
        last_update_id = update['update_id']
        message = update['message']

        command = find_command(message)

        if command is not None:
            try:
                process_command(message, command[0], command[1])
            except ProcessCommandException as e:
                print("{}".format(e), file=sys.stderr)
                time.sleep(30)
                break

        save_last_update_id(last_update_id)
