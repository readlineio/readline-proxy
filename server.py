# TODO: this is all probably better handled with an express + websocket
# server for the long polling

import sys
import json
import time
import tornado.ioloop
import tornado.web
from collections import defaultdict, namedtuple

CHANNEL_MESSAGES = defaultdict(list)
CHANNEL_HANDLERS = {}

class ChannelHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    def get(self, channel_id):
        # check if there's already a handler for this channel id
        # if so, then raise an error
        self.channel_id = channel_id
        """
        TODO: figure out how to recover from client disconnect --
        otherwise you end up with infinite empty messages issue. Maybe
        prompt user for how to handle?
        if CHANNEL_HANDLERS.get(self.channel_id):
            # TODO: raise error
            self.finish()
        """

        # Check if there are any messages backed up.
        messages = CHANNEL_MESSAGES[self.channel_id]
        if messages:
            message = messages.pop(0)
            self.send_message(message)
        else:
            CHANNEL_HANDLERS[self.channel_id] = self

    def send_message(self, message):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.write(message)
        self.finish()

    def post(self, channel_id):
        self.channel_id = channel_id
        message = self.request.body
        print("Received message on channel '{channel_id}': len={n}".format(channel_id=channel_id, n=len(message)))
        handler = CHANNEL_HANDLERS.get(self.channel_id)
        if handler:
            handler.send_message(message)
            del CHANNEL_HANDLERS[self.channel_id]
        else:
            CHANNEL_MESSAGES[self.channel_id].append(message)

        # TODO: make this do the proper CORS strategy
        self.set_header("Access-Control-Allow-Origin", "*")
        self.write('ok')
        self.finish()


PROGRAM_REGISTRAR = {} # channel_id -> program information
PROGRAM_UPDATE_HANDLERS = [] # callables on updates to registrar
PROGRAM_TIMEOUT = 120

def add_program(channel, program):
    print("Update received from program:", program)
    clean_program_list()
    PROGRAM_REGISTRAR[channel] = program
    while PROGRAM_UPDATE_HANDLERS:
        handler = PROGRAM_UPDATE_HANDLERS.pop()
        handler.send_update()

def clean_program_list():
    global PROGRAM_REGISTRAR
    to_delete = []
    for channel, program in PROGRAM_REGISTRAR.items():
        if program.last_update_time < (time.time() - PROGRAM_TIMEOUT):
            to_delete.append(channel)
    for channel in to_delete:
        del PROGRAM_REGISTRAR[channel]

Program = namedtuple('Program', ['title', 'channel', 'last_update_time'])

def get_program_data():
    program_data = list(PROGRAM_REGISTRAR.values())
    program_data.sort(key=lambda o: o.last_update_time, reverse=True)
    program_data = [o._asdict() for o in program_data]
    return program_data

class ProgramRegisterHandler(tornado.web.RequestHandler):

    def post(self):
        message = self.request.body
        message = json.loads(message.decode('utf-8'))
        program = Program(
            title=message.get('title', 'Untitled Program'),
            channel=message.get('page_id'),
            last_update_time=time.time()
            )
        add_program(message['page_id'], program)


class ProgramListHandler(tornado.web.RequestHandler):

    def get(self):
        clean_program_list()
        self.set_header("Access-Control-Allow-Origin", "*")
        self.write(json.dumps(get_program_data()))
        self.finish()


class ProgramUpdateHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    def get(self):
        PROGRAM_UPDATE_HANDLERS.append(self)

    def send_update(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.write(json.dumps(get_program_data()))
        self.finish()


application = tornado.web.Application([
    tornado.web.url(r'/channel/([A-Za-z0-9\-]+)', ChannelHandler, name="channel_id"),
    tornado.web.url(r'/program/register', ProgramRegisterHandler),
    tornado.web.url(r'/program/list', ProgramListHandler),
    tornado.web.url(r'/program/updates', ProgramUpdateHandler)
])

if __name__ == "__main__":
    # TODO: Make better argparse version
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 8888
    application.listen(port)
    print("Listening for connections on port {port}...".format(port=port))
    tornado.ioloop.IOLoop.current().start()
