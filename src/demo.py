from myeplinks.tools import HtmlFileGenerator

url = 'www.myepisodes.com/rss.php?feed=unacquired&showignored=0&uid=nickbolton2705&pwdmd5=3d549f8b0a75ba033e3b788b581a6d21'
outfile = 'links.html'
linkfmt = 'http://www.tv.com/search.php?qs={0}+{1}'
textfmt = '{0} - {2}'
split = dict()
xpath = '/rss/channel/item/title'
split = ' ][ '
trim = dict()
trim = ('[ ', ' ]')
spacechar = '+'
regex = dict()

gen = HtmlFileGenerator(xpath, linkfmt, textfmt, split, trim, spacechar, regex)
gen.genFromUrl(url, outfile)