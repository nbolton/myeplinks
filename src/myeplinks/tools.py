import libxml2, httplib, re

class LinkInfo:
	def __init__(self, gen, value):
		self.gen = gen
		self.parts = self.getParts(value)

	def getParts(self, value):
		# trim as the user needs
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
		for part in self.parts:
			text = text.replace('{' + str(i) + '}', part)
			i += 1
		return text
	
	def getUrl(self):
		link = self.gen.linkfmt
		i = 0
		for part in self.parts:
			if self.gen.regex.has_key(i):
				part = re.sub(self.gen.regex[i][0], self.gen.regex[i][1], part)
			link = link.replace('{' + str(i) + '}', part)
			i += 1
		if self.gen.spacechar:
			link = link.replace(' ', self.gen.spacechar)
		return link

class HtmlFileGenerator:
	def __init__(self, xpath, linkfmt, textfmt, split, trim, spacechar, regex):
		self.regex = regex
		self.xpath = xpath
		self.linkfmt = linkfmt
		self.textfmt = textfmt
		self.split = split
		self.trim = trim
		self.spacechar = spacechar
	
	def generateHtml(self, inputXml):
		doc = libxml2.parseDoc(inputXml)
		nodes = doc.xpathEval(self.xpath)
		links = [LinkInfo(self, node.content) for node in nodes]
		
		html = '<ul>\n'
		for link in links:
			html += '<li><a href="%s" target="_blank">%s</a></li>\n' % (link.getUrl(), link.getText())
			
		html += '</ul>\n'
		
		return html
		
	def downloadFeed(self, feedUrl):
		host = feedUrl.replace('http://', '').split('/')[0]
		path = '/' + '/'.join(feedUrl.split('/')[1:])
		http = httplib.HTTPConnection(host)
		http.request('GET', path)
		resp = http.getresponse()
		if resp.status != 200:
			raise Exception('Unable to download feed: %i %s' % (resp.status, resp.reason))
		return resp.read()
	
	def writeToFile(self, html, outfile):
		file = open(outfile, 'w')
		file.write(html)
		file.close()

	def genFromUrl(self, feedUrl, outfile):
		feedXml = self.downloadFeed(feedUrl)
		html = self.generateHtml(feedXml)
		self.writeToFile(html, outfile)
