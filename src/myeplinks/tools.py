import libxml2, httplib, re

class LinkInfo:
	def __init__(self, gen, value):
		self.gen = gen
		self.parts = self.getParts(value)

	def getParts(self, value):
		# trim as the user specifies
		if len(self.gen.trim) != 0:
			for trim in self.gen.trim:
				if value.startswith(trim):
					value = value[len(trim):]
				elif value.endswith(trim):
					value = value[:-len(trim)]
		
		# if no split specified, 1 part is returned, which is fine
		return value.split(self.gen.split)
	
	def getText(self):
		text = self.gen.textfmt
		i = 0
		# for each part of the xpath match, return the link text
		for part in self.parts:
			text = text.replace('{' + str(i) + '}', part)
			i += 1
		return text
	
	def getUrl(self):
		link = self.gen.linkfmt
		i = 0
		# for each part of whatever the user wants to process in to links...
		for part in self.parts:
			if self.gen.regex.has_key(i):
				# regex replace (first array item is the match, second is the replace)
				part = re.sub(self.gen.regex[i][0], self.gen.regex[i][1], part)
			link = link.replace('{' + str(i) + '}', part)
			i += 1
		if self.gen.spacechar:
			# replace space with another char (useful for URLs)
			link = link.replace(' ', self.gen.spacechar)
		return link

class FeedDownloader:
	def downloadFeed(self, feedUrl):
		# we alreayd know we're using http, so discard the protocol
		cleanUrl = feedUrl.replace('http://', '')
		
		# get the first part of the url (the host name)
		host = cleanUrl.split('/')[0]
		
		# the path is all the remaining parts
		path = '/' + '/'.join(cleanUrl.split('/')[1:])
		
		# download the feed using GET
		http = httplib.HTTPConnection(host)
		http.request('GET', path)
		resp = http.getresponse()
		
		if resp.status != 200:
			raise Exception('Unable to download feed: %i %s' % (resp.status, resp.reason))
		
		return resp.read()
		
class HtmlFileGenerator:
	def __init__(self, xpath, linkfmt, textfmt, split, trim, spacechar, regex):
		self.regex = regex
		self.xpath = xpath
		self.linkfmt = linkfmt
		self.textfmt = textfmt
		self.split = split
		self.trim = trim
		self.spacechar = spacechar
	
	def generateHtml(self, links):
		
		# create a list of URLs
		html = '<ul>\n'
		for link in links:
			html += '<li><a href="%s" target="_blank">%s</a></li>\n' % (
				link.getUrl(), link.getText()
			)
			
		html += '</ul>\n'
		
		return html
	
	def writeToFile(self, html, outfile):
		file = open(outfile, 'w')
		file.write(html)
		file.close()
		
	def getLinks(self, feedXml):
		# use xpath to extract whatever the user specified with their xpath,
		# and return a collection of LinkInfo objects
		doc = libxml2.parseDoc(feedXml)
		nodes = doc.xpathEval(self.xpath)
		return [LinkInfo(self, node.content) for node in nodes]

	def genFromUrl(self, feedUrl, outfile):
		# download the feed xml
		fd = FeedDownloader()
		feedXml = fd.downloadFeed(feedUrl)
		
		# create some easy to use link objects
		links = self.getLinks(feedXml)
		
		# generate the html
		html = self.generateHtml(links)
		
		# and save to file
		self.writeToFile(html, outfile)
