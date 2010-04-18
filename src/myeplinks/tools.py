import libxml2, httplib, re

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

class TargetInfo:
	def __init__(self, extractor, value):
		self.extractor = extractor
		self.parts = self.getParts(value)

	def getParts(self, value):
		# trim as the user specifies
		if len(self.extractor.trim) != 0:
			for trim in self.extractor.trim:
				if value.startswith(trim):
					value = value[len(trim):]
				elif value.endswith(trim):
					value = value[:-len(trim)]
		
		# if no split specified, 1 part is returned, which is fine
		return value.split(self.extractor.split)
	
	def getString(self, fmt, spacechar=None):
		string = fmt
		i = 0
		# for each part of whatever the user wants to process...
		for part in self.parts:
			if self.extractor.regex.has_key(i):
				# regex replace (first array item is the match, second is the replace)
				part = re.sub(self.extractor.regex[i][0], self.extractor.regex[i][1], part)
			string = string.replace('{' + str(i) + '}', part)
			i += 1
		if spacechar:
			# replace space with another char (useful for URLs)
			string = string.replace(' ', spacechar)
		return string

class TargetExtractor:
	def __init__(self, xpath, trim, split, regex):
		self.xpath = xpath
		self.trim = trim
		self.split = split
		self.regex = regex
		
	def getTargets(self, feedXml):
		# the user's xpath should return a list of targets, and for each 
		# target, we create a TargetInfo object and return them as a 
		# collection (each of which could represent a link for example)
		doc = libxml2.parseDoc(feedXml)
		nodes = doc.xpathEval(self.xpath)
		return [TargetInfo(self, node.content) for node in nodes]

class HtmlFileGenerator:
	def __init__(self, xpath, linkfmt, textfmt, split, trim, spacechar, regex):
		self.linkfmt = linkfmt
		self.textfmt = textfmt
		self.spacechar = spacechar
		self.fd = FeedDownloader()
		self.te = TargetExtractor(xpath, trim, split, regex)
	
	def generateHtml(self, targets):
		html = '<ul>\n'
		
		# for each item, add a new url
		for target in targets:
			html += '<li><a href="%s" target="_blank">%s</a></li>\n' % (
				target.getString(self.linkfmt, self.spacechar),
				target.getString(self.textfmt)
			)
			
		html += '</ul>\n'
		
		return html
	
	def writeToFile(self, html, outfile):
		file = open(outfile, 'w')
		file.write(html)
		file.close()

	def genFromUrl(self, feedUrl, outfile):
		# download the feed xml
		feedXml = self.fd.downloadFeed(feedUrl)
		
		# create some easy to use target objects
		targets = self.te.getTargets(feedXml)
		
		# generate the html
		html = self.generateHtml(targets)
		
		# and save to file
		self.writeToFile(html, outfile)
