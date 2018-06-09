# Builtins
import json
import logging

#Third-party
import tornado
from tornado import gen
import tornado_components.web 
from jsonrpcserver.aio import methods
from jsonrpcclient.http_client import HTTPClient
from qtum_utils.qtum import Qtum
import settings



class AllContentHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles all blockchain content requests
	"""

	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'GET, OPTIONS')


	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email

	async def get(self):
		"""Returns all content as list 
		"""
		logging.debug("[+] -- Get all content")
		# List for contents
		content = await self.client_storage.request(method_name="getallcontent")
		try:
			content["error"]
		except:
			self.write(json.dumps(content))
		else:
			self.set_status(content["error"])
			self.write(content)

	def options(self):
		self.write(json.loads(["GET"]))


class ContentHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles blockchain content requests
	"""

	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email

	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')


	async def get(self, cid):
		"""Receives content by content id
		"""
		logging.debug("[+] -- Get single content")
		content = await self.client_storage.request(method_name="getsinglecontent", 
																		cid=cid)
		logging.debug(content)
		if "error" in content.keys():
			self.set_status(content["error"])
			self.write(content)
			raise tornado.web.Finish 

		self.write(content)


	async def post(self, public_key=None):
		"""Writes content to blockchain

		Accepts:
			- cus (content)
			- public_key

		"""
		logging.debug("[+] -- Post content to blockchain")
		#super().verify()
		# Check if public_key exists
		account = await self.client_storage.request(method_name="getaccountdata", 
											public_key=public_key)

		logging.debug("[+] -- Post data to blockchain debugging")
		if "error" in account.keys():
			self.set_status(account["error"])
			self.write(account)
			raise tornado.web.Finish

		# Get message from request 
		data = json.loads(self.request.body)
		if not data:
			self.set_status(403)
			self.write({"error":403, "reason":"Forbidden"})
			raise tornado.web.Finish
		logging.debug(data)
		# Overload data dictionary
		if isinstance(data["message"], str):
			message = json.loads(data["message"])
		elif isinstance(data["message"], dict):
			message = data["message"]
		cus = message.get("cus", None)
		description = message.get("description", None)
		price = message.get("price", 0)
		if not all([cus, description, price]):
			self.set_status(400)
			self.write({"error":400, "reason":"Missed required fields"})
			raise tornado.web.Finish
		# Send requests to bridge
		owneraddr = Qtum.public_key_to_hex_address(public_key)
		data = {"cus":cus, 
				"owneraddr":owneraddr, 
				"description":description, 
				"price":price
				}
		logging.debug(data)
		response = await self.client_bridge.request(method_name="makecid", **data)
		if "error" in response.keys():
			self.set_status(400)
			self.write(response)
			raise tornado.web.Finish
		logging.debug(response)
		# Write content to database
		contentdata = {"txid":response["result"]["txid"], "account_id":account["id"],
						"price":price, "description":description, "content":cus,
						"seller_pubkey":None, "seller_access_string":None}
		result = await self.client_storage.request(method_name="setuserscontent", 
																**contentdata)
		if "error" in result.keys():
			self.set_status(result["error"])
			self.write(result)

		self.write(response)


	def options(self, public_key):
		self.write(json.dumps(["GET", "POST"]))



class DescriptionHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles blockchain content description requests
	"""
	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'POST, OPTIONS')


	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email


	async def post(self, cid):
		"""Set description for content
		"""
		super().verify()
		body = json.loads(self.request.body)
		public_key = body.get("public_key", None)
		if isinstance(body["message"], str):
			message = json.loads(body["message"])
		elif isinstance(body["message"], dict):
			message = body["message"]
		cid = message.get("cid")
		descr = message.get("description")
		if not all([public_key, cid, descr]):
			self.set_status(400)
			self.write({"error":400, "reason":"Missed required fields"})
			raise tornado.web.Finish
		
		# Get content owner
		response = await self.client_bridge.request(method_name="ownerbycid", cid=cid)
		if "error" in response.keys():
			error_code = response["code"]
			self.set_status(error_code)
			self.write({"error":error_code, "reason":response["error"]})
			raise tornado.web.Finish

		# Check if content owner has current public key 
		if not response["owneraddr"] == Qtum.public_key_to_hex_address(public_key):
			self.set_status(403)
			self.write({"error":403, "reason":"Owner does not match."})
			raise tornado.web.Finish
		# Set description for content
		request = await self.client_bridge.request(method_name="setdescrforcid", 
						cid=cid, descr=descr, owneraddr=response["owneraddr"])
		if "error" in request.keys():
			self.set_status(request["error"])
			self.write(request)
			raise tornado.web.Finish
		self.write(request)


	def options(self, cid):
		self.write(json.dumps(["POST"]))
	


class PriceHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles content price requests
	"""


	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')


	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email


	async def post(self, cid):
		"""Sets price for blockchain content

		Accepts:
			- cid
			- owners public key
			- price
		""" 
		super().verify()
		body = json.loads(self.request.body)
		public_key = body.get("public_key", None)
		if isinstance(body["message"], str):
			message = json.loads(body["message"])
		elif isinstance(body["message"], dict):
			message = body["message"]
		cid = message.get("cid")
		price = message.get("price", "")
		descr = message.get("description")
		
		if not all([public_key, str(cid).isdigit(), str(price).isdigit()]):
			self.set_status(400)
			self.write({"error":400, "reason":"Missed required fields"})
			raise tornado.web.Finish
		# Check if current public key is content owner
		response = await self.client_bridge.request(method_name="ownerbycid", cid=cid)

		if "error" in response.keys():
			self.set_status(404)
			self.write({"error":404, "reason":"Owner not found."})
			raise tornado.web.Finish

		if not response["owneraddr"] == Qtum.public_key_to_hex_address(public_key):
			self.set_status(403)
			self.write({"error":403, "reason":"Owner does not match."})
			raise tornado.web.Finish
		# Make setprice request to the bridge
		response = await self.client_bridge.request(method_name="setprice", 
								cid=cid, price=price, owneraddr=response["owneraddr"])
		self.write(response)

	def options(self, cid):
		self.write(json.dumps(["GET", "POST"]))



class OfferHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles requests binded with offers (make, reject etc)
	"""
	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email


	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'POST, PUT, OPTIONS')


	async def post(self, public_key=None):
		"""Creates new offer

		Accepts:
			- buyer public key
			- cid
			- buyer access string
		Returns:
			- offer parameters as dictionary
		"""
		super().verify()
		body = json.loads(self.request.body)
		if isinstance(body["message"], str):
			message = json.loads(body["message"])
		elif isinstance(body["message"], dict):
			message = body["message"]
		cid = message.get("cid")
		price = message.get("price")
		buyer_access_string = message.get("buyer_access_string")
		# Get cid price from bridge
		if not price:
			price = await self.client_bridge.request(method_name="getprice", cid=cid)
			
		if not all([message, buyer_access_string, str(cid).isdigit()]):
			self.set_status(400)
			self.write({"error":400, "reason":"Missed required fields"})
			raise tornado.web.Finish

		# Check if public key exists
		account = await self.client_storage.request(method_name="getaccountdata", 
									public_key=public_key)
		if "error" in account.keys():
			# If account does not exist
			self.set_status(account["error"])
			self.write(account)
			raise tornado.web.Finish

		# Check if current offer already exists
		offer = await self.client_storage.request(method_name="getoffer",
			cid=cid, buyer_address=Qtum.public_key_to_hex_address(public_key))
		if "cid" in offer.keys():
			self.set_status(403)
			self.write({"error":403,
						"reason":"Current offer already exists"})
			raise tornado.web.Finish


		#Get sellers balance
		balance = await self.client_balance.request(method_name="getbalance", 
													uid=account["id"])
		#Detect contents owner
		owneraddr = await self.client_bridge.request(method_name="ownerbycid", 
													cid=cid)
		owneraddr = owneraddr.get("owneraddr")
		if owneraddr == Qtum.public_key_to_hex_address(public_key):
			self.set_status(400)
			self.write({"error":400, 
						"reason":"Content belongs to current user"})
			raise tornado.web.Finish

		# Get difference with balance and price
		difference = float(list(balance.values())[0]) - float(price)
		if difference < 0:
			# If Insufficient funds
			self.set_status(402)
			self.write({"error":402, "reason":"Balance is not enough"})
			raise tornado.web.Finish

		# Make offer
		buyer_address = Qtum.public_key_to_hex_address(public_key)
		offer_data = {
			"cid":cid,
			"price":price,
			"buyer_address": buyer_address,
			"buyer_access_string":buyer_access_string
		}
		response = await self.client_bridge.request(method_name="make_offer", 
													**offer_data)
		try:
			response["error"]
		except:
			pass
		else:
			self.set_status(response["error"])
			self.write(response)
			raise tornado.web.Finish

		# Send e-mail to seller
		seller = await self.client_storage.request(method_name="getaccountbywallet",
											wallet=owneraddr)
		if "error" in seller.keys():
			self.set_status(seller["error"])
			self.write(seller)
			raise tornado.web.Finish

		if seller.get("email"):
			emaildata = {
				"to": seller["email"],
				"subject": "Robin8 support",
     			"optional": "You`ve got an offer for content %s." % cid
			}
			await self.client_email.request(method_name="sendmail", **emaildata)

		# Insert offer to database
		await self.client_storage.request(method_name="insertoffer", 
				owner_pubkey=seller["public_key"], owner_addr=owneraddr,
				txid=response["result"]["txid"],
				cid=cid, price=price, buyer_address=buyer_address)

		self.write(response)


	async def put(self, public_key=None):
		"""Reject offer

		Accepts:
			- cid
			- buyer public key
			- buyer address
		"""
		super().verify()
		# Check if message contains required data
		body = json.loads(self.request.body)
		if isinstance(body["message"], str):
			message = json.loads(body["message"])
		elif isinstance(body["message"], dict):
			message = body["message"]
		cid = message["offer_id"].get("cid", 0)
		cid = int(cid)
		buyer_address = message["offer_id"].get("buyer_address")

		account = await self.client_storage.request(method_name="getaccountdata", 
										public_key=public_key)
		if "error" in account.keys():
			error_code = account["error"]
			self.set_status(error_code)
			self.write(account)
			raise tornado.web.Finish

		# Check if current offer exists
		offer = await self.client_storage.request(method_name="getoffer",
									cid=cid, buyer_address=buyer_address)
		if not "cid" in offer.keys():
			self.set_status(400)
			self.write({"error":400,
						"reason":"Current offer does not exist"})
			raise tornado.web.Finish
	
		# Check if one of sellers or buyers rejects offer
		owneraddr = await self.client_bridge.request(method_name="ownerbycid", cid=cid)
		owneraddr = owneraddr.get("owneraddr")
		hex_ = Qtum.public_key_to_hex_address(public_key)
		if buyer_address != hex_ and owneraddr != hex_:
			# Avoid rejecting offer
			self.set_status(403)
			self.write({"error": 403, "reason":"Forbidden"})
		# Reject offer
		response = await self.client_bridge.request(method_name="reject_offer",
										cid=cid, buyer_address=buyer_address)
		if "error" in response.keys():
			self.set_status(response["error"])
			self.write(response)
			raise tornado.web.Finish

		# Get buyer for email sending
		buyer = await self.client_storage.request(method_name="getaccountbywallet",
												wallet=buyer_address)
		if "error" in buyer.keys():
			self.set_status(buyer["error"])
			self.write(buyer)
			raise tornado.web.Finish
	
		if buyer.get("email"):
			emaildata = {
				"to": buyer.get("email"),
				"subject": "Robin8 support",
     			"optional": "Your offer with cid %s was rejected." % cid
			}
			await self.client_email.request(method_name="sendmail", **emaildata)
			# Remove offer from database
			rejected = await self.client_storage.request(method_name="removeoffer",
							cid=cid, buyer_address=buyer_address)
			if "error" in rejected.keys():
				self.set_status(rejected["error"])
				self.write(rejected)
				raise tornado.web.Finish

		self.write(response)


	def options(self, public_key):
		self.write(json.dumps(["PUT", "POST"]))



class DealHandler(tornado_components.web.ManagementSystemHandler):
	"""Handles accept offer requests
	"""

	def initialize(self, client_bridge, client_storage, client_balance, client_email):
		self.client_bridge = client_bridge
		self.client_storage = client_storage
		self.client_balance = client_balance
		self.client_email = client_email

	def set_default_headers(self):
		self.set_header("Access-Control-Allow-Origin", "*")
		self.set_header("Access-Control-Allow-Headers", "Content-Type")
		self.set_header('Access-Control-Allow-Methods', 'POST, OPTIONS')

	async def post(self, public_key=None):
		"""Accepting offer by buyer

		Function accepts:
			- cid
			- buyer access string
			- buyer public key
			- seller public key
		"""
		#super().verify()
		# Check if message contains required data
		body = json.loads(self.request.body)
		if isinstance(body["message"], str):
			message = json.loads(body["message"])
		elif isinstance(body["message"], dict):
			message = body["message"]
		cid = message.get("cid")
		buyer_pubkey = message.get("buyer_pubkey")
		buyer_access_string = message.get("buyer_access_string")
		seller_access_string = message.get("seller_access_string")
		logging.debug("[+] -- Accept offer debugging")
		logging.debug(message)
		logging.debug(cid)
		logging.debug(buyer_pubkey)
		logging.debug(buyer_access_string)
		logging.debug(seller_access_string)
		# check passes data
		if not all([buyer_access_string, cid, buyer_pubkey]):
			self.set_status(400)
			self.write({"error":400, "reason":"Missed required fields"})
			raise tornado.web.Finish

		# Check if accounts exists
		seller_account = await self.client_storage.request(method_name="getaccountdata", 
										public_key=public_key)
		try:
			error_code = seller_account["error"]
		except:
			pass
		else:
			self.set_status(error_code)
			self.write(seller_account)
			raise tornado.web.Finish
		buyer_account = await self.client_storage.request(method_name="getaccountdata", 
										public_key=buyer_pubkey)
		try:
			error_code = buyer_account["error"]
		except:
			pass
		else:
			self.set_status(error_code)
			self.write(buyer_account)
			raise tornado.web.Finish

		# Check if content belongs to current account
		owneraddr = await self.client_bridge.request(method_name="ownerbycid", cid=cid)
		if "error" in owneraddr.keys():
			self.set_status(owneraddr["error"])
			self.write(owneraddr)
			raise tornado.web.Finish

		owneraddr = owneraddr.get("owneraddr")
		if owneraddr != Qtum.public_key_to_hex_address(public_key):
			self.set_status(403)
			self.write({"error":403, "reason":"Forbidden."})
			raise tornado.web.Finish

		# Check if current offer exists
		offer = await self.client_storage.request(method_name="getoffer",
			cid=cid, buyer_address=Qtum.public_key_to_hex_address(buyer_pubkey))
		if "error" in offer.keys():
			self.set_status(offer["error"])
			self.write(offer)
			raise tornado.web.Finish

		#buyer_access_string = Qtum.to_compressed_public_key(buyer_access_string)

		#Get buyers balance
		balance = await self.client_balance.request(method_name="getbalance", 
										uid=buyer_account["id"])
		if "error" in balance.keys():
			self.set_status(balance["error"])
			self.write(balance)
			raise tornado.web.Finish 

		# Get difference with balance and price
		difference = float(list(balance.values())[0]) - float(offer["buyer_price"])
		if difference >= 0:
			# Change content owner
			chownerdata = {
				"cid":cid,
				"new_owner": Qtum.public_key_to_hex_address(buyer_pubkey),
				"access_string": buyer_access_string
			}
			chown = await self.client_bridge.request(method_name="changeowner", 
													**chownerdata)
			if "error" in chown.keys():
				self.set_status(chown["error"])
				self.write(chown)
				raise tornado.web.Finish
			# Write access string to database
			setaccessdata = {
				"cid":cid,
				"seller_access_string": seller_access_string,
				"seller_pubkey": public_key
			}
			res = await self.client_storage.request(method_name="setaccessstring",
															**setaccessdata)

			# Sellcontent
			selldata = {
				"cid":cid,
				"buyer_address":Qtum.public_key_to_hex_address(buyer_pubkey),
				"access_string":buyer_access_string
			}
			logging.debug("[+] -- Sell data")
			logging.debug(selldata)
			sell = await self.client_bridge.request(method_name="sellcontent", 
													**selldata)
			
			# Check if selling was successfull
			try:
				sell["content_owner"]
			except:
				self.set_status(500)
				self.write({"error":500, "reason":"Unpossible to implement selling."})
				raise tornado.web.Finish
			else:
				# Increment and decrement balances of seller and buyer
				await self.client_balance.request(method_name="decbalance", 
									uid=buyer_account["id"], amount=offer["buyer_price"])
				await self.client_balance.request(method_name="incbalance", 
									uid=seller_account["id"], amount=offer["buyer_price"])

				# Remove offer from database
				await self.client_storage.request(method_name="removeoffer",cid=cid,
						buyer_address=Qtum.public_key_to_hex_address(buyer_pubkey))

				# Change owner in database
				con = await self.client_storage.request(method_name="changecontentowner",
												cid=cid, buyer_pubkey=buyer_pubkey)
				
				self.write(con)
		else:
			# If Insufficient funds
			self.set_status(402)
			self.write({"error":402, "reason":"Insufficient funds"})


	def options(self, public_key):
		self.write(json.dumps(["POST"]))