import libxml2, httplib, re, os, urllib
from xml.dom import minidom

class HttpDownloader:
	def download(self, url):
		# we alreayd know we're using http, so discard the protocol
		cleanUrl = url.replace('http://', '')
		
		# get the first part of the url (the host name)
		host = cleanUrl.split('/')[0]
		
		# the path is all the remaining parts
		path = '/' + '/'.join(cleanUrl.split('/')[1:])
		
		# download the feed using GET
		http = httplib.HTTPConnection(host)
		http.request('GET', path)
		resp = http.getresponse()
		
		if resp.status != 200:
			raise Exception('Unable to download: %i %s' % (resp.status, resp.reason))
		
		return resp.read()

class TargetInfo:
	def __init__(self, extractor, value):
		self.extractor = extractor
		self.parts = self.getParts(value)

	def getParts(self, value):
		# trim as the user specifies
		if self.extractor.trim:
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
			if self.extractor.regex and self.extractor.regex.has_key(i):
				# regex replace (first array item is the match, second is the replace)
				part = re.sub(self.extractor.regex[i][0], self.extractor.regex[i][1], part)
			
			string = string.replace('{' + str(i) + '}', part)
			i += 1
		
		if spacechar:
			# replace space with another char (useful for URLs)
			string = string.replace(' ', spacechar)
		
		return string

class TargetExtractor:
	def __init__(self, xpath, trim=None, split=None, regex=None):
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
	def __init__(self, linkfmt, textfmt, spacechar, te):
		self.linkfmt = linkfmt
		self.textfmt = textfmt
		self.spacechar = spacechar
		self.downloader = HttpDownloader()
		self.te = te

	def genFromUrl(self, feedUrl, outfile):
		# download the feed xml
		feedXml = self.downloader.download(feedUrl)
		
		# create some easy to use target objects
		targets = self.te.getTargets(feedXml)
		
		# generate the html
		html = self.generateHtml(targets)
		
		# and save to file
		self.writeToFile(html, outfile)
	
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

class TargetProcessor:
	def __init__(self, linkfmt, actionLinkfmt, procRecFile, spacechar, srcTe, procTe, actionResult):
		self.linkfmt = linkfmt
		self.actionLinkfmt = actionLinkfmt
		self.procRecFile = procRecFile
		self.spacechar = spacechar
		self.downloader = HttpDownloader()
		self.srcTe = srcTe
		self.procTe = procTe
		self.actionResult = actionResult

	def process(self, feedUrl):		
		# download the feed xml
		feedXml = self.downloader.download(feedUrl)
		
		# create some easy to use target objects
		srcTargets = self.srcTe.getTargets(feedXml)
		
		# for each source target, get a target to process 
		procTargets = self.getProcTargets(srcTargets)
		
		# actions each proc target assiming they are urls
		return self.handleProcTargets(procTargets)
	
	def handleProcTargets(self, procTargets):		
		# get a list of formatted processed target strings
		targetStrings = [pt.getString('{0}') for pt in procTargets]
		
		# get a list of already processed targets
		procRecord = self.getprocRecord()
		
		handled = 0
		for ts in targetStrings:
			
			# only process targets that haven't been processed yet
			if ts not in procRecord:
				
				# get the action url based on the target url
				actionUrl = self.actionLinkfmt % urllib.quote(ts)
				
				# go ahead and action the url
				result = self.downloader.download(actionUrl).rstrip('\n')
				
				if result == self.actionResult:
					# once the target has ben processed ok
					self.appendProcRec(ts)
					handled += 1
				else:
					print 'Result: ' + result
					print "Error: Did not get expected result (%s)." % self.actionResult
		
		return handled
	
	def getProcTargets(self, srcTargets):		
		procTargets = list()
		for source in srcTargets:
			feedUrl = source.getString(self.linkfmt, self.spacechar)
			
			# assume that each target will get us a link to an xml feed
			xml = self.downloader.download(feedUrl)
			
			# get some sub-targets as can be found in the xml
			subTargets = self.procTe.getTargets(xml)
			
			if len(subTargets) > 0:
				# but only use the first (if there are any at all)
				procTargets.append(subTargets[0])
		
		return procTargets
	
	def getprocRecord(self):
		if os.path.exists(self.procRecFile):
			doc = libxml2.parseFile(self.procRecFile)
			nodes = doc.xpathEval('/procrec/target')
			return [node.content for node in nodes]
		else:
			return list()

	def appendProcRec(self, target):
		# if the xml file exists, open it, otherwise create with root node
		if os.path.exists(self.procRecFile):
			doc = minidom.parse(self.procRecFile)
			root = doc.getElementsByTagName('procrec')[0]
		else:
			doc = minidom.Document()
			root = doc.createElement('procrec')
			doc.appendChild(root)
		
		# append a target node
		targetXml = doc.createElement('target')
		root.appendChild(targetXml)
		
		# set the target node's text
		textXml = doc.createTextNode(target)
		targetXml.appendChild(textXml)
		
		# save each time (not IO friendly, but makes the system more robust)
		file = open(self.procRecFile, 'w+')
		doc.writexml(file)
		file.close()
