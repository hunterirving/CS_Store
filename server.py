import os
import mimetypes
import json
import logging
import base64
import html
import re
import time
import tornado.httpclient
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
	"image/gif",
	"video/mp4",
	"application/pdf",
	"audio/mpeg"
]

SVG_PATTERN = re.compile(rb"<svg\b.*?</svg\s*>", re.IGNORECASE | re.DOTALL)
TITLE_PATTERN = re.compile(rb"<title[^>]*>(.*?)</title\s*>", re.IGNORECASE | re.DOTALL)
CHARSET_PATTERN = re.compile(rb"charset\s*=\s*[\"\']?([a-z0-9_-]+)", re.IGNORECASE)
BROWSER_USER_AGENT = (
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

def body_encoding(response):
	for source in (response.headers.get("Content-Type", "").encode(), response.body[:4096]):
		found = CHARSET_PATTERN.search(source)
		if found:
			return found.group(1).decode("ascii", "replace")
	return "utf-8"

async def fetch_page_title(url):
	response = await tornado.httpclient.AsyncHTTPClient().fetch(
		url,
		follow_redirects=True,
		user_agent=BROWSER_USER_AGENT,
		connect_timeout=10,
		request_timeout=20,
	)
	match = TITLE_PATTERN.search(SVG_PATTERN.sub(b"", response.body))
	if not match:
		logger.warning(f"No <title> found at {url}")
		return None
	try:
		text = match.group(1).decode(body_encoding(response), "replace")
	except LookupError:
		text = match.group(1).decode("utf-8", "replace")
	return " ".join(html.unescape(text).split()) or None

def save_layout(layout):
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	data = {
		"layout": layout
	}
	
	try:
		with open(cs_store_path, "w") as f:
			json.dump(data, f, indent=4)
		logger.info(f"Layout saved successfully to {cs_store_path}")
	except Exception as e:
		logger.error(f"Error saving layout: {str(e)}")

def load_layout():
	global FILE_PATH
	cs_store_path = f"{FILE_PATH}/.CS_Store"
	
	if os.path.exists(cs_store_path):
		try:
			with open(cs_store_path, "r") as f:
				data = json.load(f)
			logger.info(f"Layout loaded successfully from {cs_store_path}")
			return data.get("layout", {})
		except json.JSONDecodeError as e:
			logger.error(f"Error decoding .CS_Store file: {str(e)}")
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
	# Sort by modification time, newest first, so recently added files
	# appear at the top of the stage.
	listing.sort(
		key=lambda f: os.path.getmtime(os.path.join(FILE_PATH, f)),
		reverse=True,
	)
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

	return { 
		"path": FILE_PATH,
		"files": files,
		"layout": load_layout(),
	}

class WSHandler(tornado.websocket.WebSocketHandler):
	def on_message(self, message):
		global FILE_PATH

		message = json.loads(message)
		if message["type"] == "initialize":
			self.write_message(json.dumps(pwd()))
			logger.info("Sent initial data to client")

		elif message["type"] ==  "layout":
			save_layout(message["layout"])
			logger.info("Received and saved new layout from client")

		elif message["type"] == "save_image":
			try:
				mime = message.get("mime", "image/png")
				ext = mimetypes.guess_extension(mime) or ".png"
				if ext == ".jpe":
					ext = ".jpg"
				now = time.time()
				filename = f"pasted_{int(now * 1000)}{ext}"
				dest = os.path.join(FILE_PATH, filename)
				with open(dest, "wb") as f:
					f.write(base64.b64decode(message["data"]))

				os.utime(dest, (now, now))
				logger.info(f"Saved pasted image to {dest}")
				self.write_message(json.dumps({
					"type": "image_saved",
					"path": f"/files/{filename}",
					"mime": mime,
					"x": message.get("x"),
					"y": message.get("y"),
					"requestId": message.get("requestId"),
				}))
			except Exception as e:
				logger.error(f"Error saving pasted image: {str(e)}")

		elif message["type"] == "page_title":
			tornado.ioloop.IOLoop.current().add_callback(self.send_page_title, message["url"])

		elif message["type"] == "cd":
			FILE_PATH = message["path"]
			os.chdir(FILE_PATH)
			server.redirect()
			response = pwd()
			self.write_message(json.dumps(response))
			logger.info(f"Changed directory to {FILE_PATH}")

	async def send_page_title(self, url):
		try:
			title = await fetch_page_title(url)
			logger.info(f"Title for {url}: {title}")
		except Exception as e:
			logger.error(f"Error fetching title for {url}: {str(e)}")
			title = None
		self.write_message(json.dumps({
			"type": "page_title",
			"url": url,
			"title": title,
		}))

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