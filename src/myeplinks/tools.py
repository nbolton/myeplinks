import libxml2, httplib, re, os, urllib, logging
from xml.dom import minidom

class LoggerFactory:
	LOG_LEVELS = {
		'debug' : logging.DEBUG,
		'info' : logging.INFO,
		'warning' : logging.WARNING,
		'error' : logging.ERROR,
		'critical' : logging.CRITICAL
	}
	
	def create(self, logLevel):
		# get level number from text name
		levelNum = self.LOG_LEVELS.get(logLevel, logging.INFO)
		
		# create logger
		log = logging.getLogger()
		log.setLevel(levelNum)
		
		# create formatter, add formatter to ch, add ch to logger
		formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
		
		# console logger
		ch = logging.StreamHandler()
		ch.setLevel(levelNum)
		ch.setFormatter(formatter)
		log.addHandler(ch)
		
		log.debug("logging setup complete")
		
		return log
	
	def empty(self):
		return logging.getLogger()

class HttpDownloader:
	def __init__(self, log=LoggerFactory().empty()):
		self.log = log
	
	def download(self, url):
		# we alreayd know we're using http, so discard the protocol
		cleanUrl = url.replace('http://', '')
		
		# get the first part of the url (the host name)
		host = cleanUrl.split('/')[0]
		
		# the path is all the remaining parts
		path = '/' + '/'.join(cleanUrl.split('/')[1:])
		
		self.log.debug('downloading from: %s' % url)
		
		# download the feed using GET
		http = httplib.HTTPConnection(host)
		http.request('GET', path)
		resp = http.getresponse()
		
		self.log.debug('got status: %i', resp.status)
		
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
	def __init__(self, xpath, trim=None, split=None, regex=None, log=LoggerFactory().empty()):
		self.log = log
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
		
class TargetPair:
	def __init__(self, source, proc):
		self.source = source
		self.proc = proc
		
class TargetProcessor:
	def __init__(self, linkfmt, actionLinkfmt, procRecFile, spacechar, srcTe, procTe, actionResult, log=LoggerFactory().empty()):
		self.log = log
		self.linkfmt = linkfmt
		self.actionLinkfmt = actionLinkfmt
		self.procRecFile = procRecFile
		self.spacechar = spacechar
		self.srcTe = srcTe
		self.procTe = procTe
		self.actionResult = actionResult
		self.downloader = HttpDownloader(log=log)

	def process(self, feedUrl):
		try:
			self.log.debug('processing feed')
		
			# download the feed xml
			feedXml = self.downloader.download(feedUrl)
			
			# create some easy to use target objects
			srcTargets = self.srcTe.getTargets(feedXml)
			self.log.debug('source targets: %i' % len(srcTargets))
			
			# for each source target, get a target to process 
			procTargets = self.getProcTargets(srcTargets)
			self.log.debug('targets to process: %i' % len(procTargets))
			
			# action each proc target assiming they are urls
			procCount = self.handleProcTargets(procTargets)
			self.log.info('processed targets: %i', procCount);
	
		except KeyboardInterrupt:
			self.log.warning('user aborted')
	
	def handleProcTargets(self, procTargets):
		
		handled = 0
		for pt in procTargets:
			
			# get formatted string to process
			ts = pt.proc.getString('{0}')
			
			# get the action url based on the target url
			actionUrl = self.actionLinkfmt % urllib.quote(ts)
			
			try:
				# go ahead and action the url
				result = self.downloader.download(actionUrl).rstrip('\n')
			
				if result == self.actionResult:
					# once the target has ben processed ok
					self.appendProcRec(pt.source)
					handled += 1
				else:
					self.log.warning('result: %s' % result)
					self.log.error('did not get expected result (%s).' % self.actionResult)
					
			except Exception, e:
				self.log.error('unable to download: %s' % e)
		
		return handled
	
	def getProcTargets(self, srcTargets):
		# get a list of already processed targets
		procRecord = self.getProcRecord()
		
		procTargets = list()
		for source in srcTargets:
		
			# construct a url from the source
			sourceUrl = source.getString(self.linkfmt, self.spacechar)
			
			# make sure we don't re-run already successful source urls
			if sourceUrl not in procRecord:
				
				# assume that each target will get us a link to an xml feed
				xml = self.downloader.download(sourceUrl)
				
				# get some sub-targets as can be found in the xml
				subTargets = self.procTe.getTargets(xml)
				
				if len(subTargets) > 0:
					# but only use the first (if there are any at all)
					procTargets.append(TargetPair(sourceUrl, subTargets[0]))
			else:
				self.log.debug(
					'ignoring already successful source, %s (%s)' % (
						' - '.join(source.parts), sourceUrl
					)
				)
		
		return procTargets
	
	def getProcRecord(self):
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
