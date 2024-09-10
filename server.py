import os
import mimetypes
import json
import logging
import tornado.ioloop
import tornado.web
import tornado.websocket

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FILE_PATH = os.getcwd()
SRC_PATH = os.path.dirname(__file__)

VALID_TYPES = [
	"image/png",
	"image/jpeg",
	"video/mp4",
	"application/pdf",
	"audio/mpeg"
]

def save_layout(layout):
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	try:
		with open(cs_store_path, "w") as f:
			json.dump(layout, f, indent=4)
		logger.info(f"Layout saved successfully to {cs_store_path}")
	except Exception as e:
		logger.error(f"Error saving layout: {str(e)}")

def load_layout():
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	if os.path.exists(cs_store_path):
		try:
			with open(cs_store_path, "r") as f:
				layout = json.load(f)
			logger.info(f"Layout loaded successfully from {cs_store_path}")
			return layout
		except json.JSONDecodeError as e:
			logger.error(f"Error decoding layout file: {str(e)}")
		except Exception as e:
			logger.error(f"Error loading layout: {str(e)}")
	return {}

def pwd():
	files = [{
		"type": "dir", 
		"path": "parent",
		"absolute": os.path.split(FILE_PATH)[0],
	}]

	listing = os.listdir(FILE_PATH)
	for f in listing:
		t = mimetypes.guess_type(f)[0]
		if t in VALID_TYPES:
			files.append({ 
				"type": t,
				"path": f"/files/{f}", 
			})
		elif os.path.isdir(f) and f[0] != ".":
			files.append({
				"type": "dir", 
				"path": f,
				"absolute": os.path.join(FILE_PATH, f)
			})

	layout = load_layout()

	return { 
		"path": FILE_PATH,
		"files": files,
		"layout": layout,
	}

class WSHandler(tornado.websocket.WebSocketHandler):
	def on_message(self, message):
		global FILE_PATH

		message = json.loads(message)
		if message["type"] == "initialize":
			response = pwd()
			self.write_message(json.dumps(response))
			logger.info("Sent initial data to client")

		elif message["type"] ==  "layout":
			save_layout(message["layout"])
			logger.info("Received and saved new layout from client")

		elif message["type"] == "cd":
			FILE_PATH = message["path"]
			os.chdir(FILE_PATH)
			server.redirect()
			response = pwd()
			self.write_message(json.dumps(response))
			logger.info(f"Changed directory to {FILE_PATH}")

	def open(self):
		logger.info("WebSocket connection opened")

	def on_close(self):
		logger.info("WebSocket connection closed")

class Server:
	def __init__(self):
		pass

	def start(self):
		self.app = tornado.web.Application([
			(r'/ws', WSHandler),
			(r'/static/(.*)', tornado.web.StaticFileHandler, { "path": SRC_PATH  }),
			(r'/files/(.*)',  tornado.web.StaticFileHandler, { "path": FILE_PATH }),
		])
		self.server = self.app.listen(1234)
		tornado.ioloop.IOLoop.current().start()

	def redirect(self):
		global FILE_PATH, SRC_PATH
		
		self.app.default_router.rules = []
		self.app.add_handlers(r".*", [
			(r'/ws', WSHandler),
			(r'/static/(.*)', tornado.web.StaticFileHandler, { "path": SRC_PATH  }),
			(r'/files/(.*)',  tornado.web.StaticFileHandler, { "path": FILE_PATH }),
		])

server = Server()

if __name__ == "__main__":
	print("Files:", FILE_PATH)
	print("Code:", SRC_PATH)
	server.start()