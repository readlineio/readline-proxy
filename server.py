import sys
import tornado.ioloop
import tornado.web
from collections import defaultdict

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


application = tornado.web.Application([
    tornado.web.url(r'/channel/([A-Za-z0-9]+)', ChannelHandler, name="channel_id"),
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