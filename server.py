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

def save_layout(layout, theme):
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	data = {
		"layout": layout,
		"theme": theme
	}
	
	try:
		with open(cs_store_path, "w") as f:
			json.dump(data, f, indent=4)
		logger.info(f"Layout and theme saved successfully to {cs_store_path}")
	except Exception as e:
		logger.error(f"Error saving layout and theme: {str(e)}")

def load_layout_and_theme():
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	if os.path.exists(cs_store_path):
		try:
			with open(cs_store_path, "r") as f:
				data = json.load(f)
			logger.info(f"Layout and theme loaded successfully from {cs_store_path}")
			return data.get("layout", {}), data.get("theme", "default")
		except json.JSONDecodeError as e:
			logger.error(f"Error decoding .CS_Store file: {str(e)}")
		except Exception as e:
			logger.error(f"Error loading layout and theme: {str(e)}")
	return {}, "default"

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

	layout, theme = load_layout_and_theme()

	return { 
		"path": FILE_PATH,
		"files": files,
		"layout": layout,
		"theme": theme,
	}

class WSHandler(tornado.websocket.WebSocketHandler):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.current_theme = "default"

	def on_message(self, message):
		global FILE_PATH

		message = json.loads(message)
		if message["type"] == "initialize":
			response = pwd()
			self.current_theme = response["theme"]
			self.write_message(json.dumps(response))
			logger.info("Sent initial data to client")

		elif message["type"] ==  "layout":
			save_layout(message["layout"], self.current_theme)
			logger.info("Received and saved new layout from client")

		elif message["type"] == "save_theme":
			self.current_theme = message["theme"]
			layout, _ = load_layout_and_theme()
			save_layout(layout, self.current_theme)
			logger.info(f"Received and saved new theme: {self.current_theme}")

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