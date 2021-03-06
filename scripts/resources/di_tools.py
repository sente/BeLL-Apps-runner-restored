"""This file contains some convenience functions. They are to be used, not be
freaked out about how they're implemented, although it is pretty clean IMHO.

Currently, it includes the DictedData class, which makes going over data with
a dictionary really easy. Given a dictionary in foo.dic, some data in
foo.txt, and two of the columns being called "column1" and "column2", this
will print out their values:

  for r in DictedData("foo.dic", "foo.txt"):
          print r.column1, r.column2

then the first question usually is "well what about fields with spaces in
their names? what about those, huh?" and the answer is this:

  for r in DictedData("foo.dic", "foo.txt"):
          print r['column 1'], r['column 2']
"""
import dircache
import logging
import os
import time
import types
from stat import *
import om

def comma_ints(ints):
	return ", ".join([str(x) for x in ints])

# helper function, given a libom dict file, return a dictionary mapping from
# column name to column number.
#
# TODO: make this more robust, it only handles machine-generated dicts
def parse_dict(d):
	cols = {}
	i = 0
	lines = d.split("\n")
	if lines[0] =='Type:variable(\t)': # old-style dict
		for l in lines[1:]:
			if l == '':
				break
			colname = l.split(':')[0]
			cols[colname.lower()] = i
			i = i + 1
	else:
		for l in lines:
			l = l.strip()
			if l.startswith("Name="):
				l = l[6:-1]
				cols[l.lower()] = i
				i = i + 1
	return cols

class ColAccessor:
	"""This is a helper class that DictData will return an instance of
	when it's being iterated over. Its job is to return the relevant value
	when an unknown fieldname (which should be a column name) is read."""
	def __init__(self, cols, fields):
		self.cols = cols
		self.fields = fields
	def __getitem__(self, i):
		return self.fields[self.cols[i.lower()]]
	def __getattr__(self, name):
		return self.fields[self.cols[name.lower()]]
	def keys(self):
		return self.cols.keys()
	def __str__(self):
		d = {}
		for cn in self.cols:
			ci = self.cols[cn]
			d[cn] = self.fields[ci]
		return str(d)
	def __repr__(self):
		return self.__str__()

class _DelimitedFileReader:
	def __init__(self, strip):
		self.coldict = None
		self.handle = None
		self.line_reader = None
		self.lineno = 0
		self.strip = strip
		self.original_line = None
	def __iter__(self):
		return self
	def next(self):
		done = 0
		while done == 0:
			self.original_line = self.line_reader(self.handle)
			if self.original_line == None:
				raise StopIteration
			l = self.original_line.rstrip("\r\n")
			if len(l) == 0:
				raise StopIteration
			self.lineno = self.lineno + 1
			self.fields = l.split("\t")
			if self.strip:
				self.fields = [f.strip() for f in self.fields]
			if len(self.fields) == len(self.coldict):
				return ColAccessor(self.coldict, self.fields)

# Apparently for NewBalance we need to handle filenames flipping case at any
# drop. The segments lookup file, segment_lu.txt, may suddenly be called
# Segment_lu.txt. call init_resolve_filename() with the path where the feed
# files are, then pass every filename through resolve_filename() and it'll
# pick the one with the highest timestamp.
resolve_filename_map = None	# after init_resolve_filename, this will
		# contain a mapping from lower-cases filename to a tuple with
		# actual filename and timestamp

class DictedData_cb(_DelimitedFileReader):
	"""This is a generalized DictedData that takes a callback function to
	get a line from some handle. This is useful if what you want to
	iterate over is not a file. update.py uses this to iterate over rows
	of tab-delimited text that is stored in a table."""
	def __init__(self, dictfile, data_handle, line_reader, strip = 0):
		DelimitedFileReader.__init__(self, strip)
		if resolve_filename_map != None:
			if dictfile[0] != '/':
				dictfile = resolve_filename_map[dictfile.lower()][0]
		self.coldict = parse_dict(open(dictfile).read())
		self.handle = data_handle
		self.line_reader = line_reader
		self.strip = strip
	
class DictedData(DictedData_cb):
	'Easily iterate over a tab-delimited text file with a dictionary.'
	def __init__(self, dictfile, datafile, strip = 0):
		if resolve_filename_map != None:
			if datafile[0] != '/':
				datafile = resolve_filename_map[datafile.lower()][0]
		def line_reader(handle):
			line = handle.readline()
			return line
		DictedData_cb.__init__(self, dictfile, open(datafile), line_reader, strip)

class FileWithHeaders(_DelimitedFileReader):
	'Easily iterate over a tab-delimited text file with a header line.'
	def __init__(self, datafile, strip = 0):
		_DelimitedFileReader.__init__(self, strip)
		self.handle = open(datafile)
		self.coldict = {}
		i = 0
		for h in self.handle.readline().strip().split("\t"):
			self.coldict[h.lower()] = i
			i = i + 1
		def line_reader(handle):
			return handle.readline()
		self.line_reader = line_reader
	
def join(iterables, columns):
	"""Given a list of DictedData (or anything else iterable that returns
	dictionaries) and a list of columns to join on, produce an iterable
	that gives the tuples from the first iterable joined on those columns
	which each of the other iterables."""
	hashes = []
	for iterable in iterables[1:]:
		hash = {}
		for r in iterable:
			key = [ r[x] for x in columns ]
			value_columns = r.keys()[:]
			for x in columns:
				value_columns.remove(x)
			values = dict([ (x, r[x]) for x in value_columns ])
			hash[HashableList(key)] = values
		hashes.append(hash)
	for r in iterables[0]:
		r = dict(r)
		key = HashableList([ r[x] for x in columns ])
		oops = 0
		for h in hashes:
			if key in h:
				for k, v in h[key].items():
					r[k] = v
			else:
				oops = 1
		if oops:
			continue
		yield r

def init_filename_resolver(path):
	global resolve_filename_map
	resolve_filename_map = {}
	for fname in dircache.listdir(path):
		status = os.stat(path + "/" + fname)
		if S_ISREG(status[ST_MODE]):
			mtime = status[ST_MTIME]
			if resolve_filename_map.has_key(fname.lower()):
				entry = resolve_filename_map[fname.lower()]
				if entry[1] < mtime:
					resolve_filename_map[fname.lower()] = (fname, mtime)
			else:
				resolve_filename_map[fname.lower()] = (fname, mtime)

def set_up_html_logger(filename_html, filename_css, level=logging.INFO):
	"""Set up the standard Python logging infrastructure to log in a basic
	HTML format to the given file, and have that file point to some CSS."""
	logfile = open(filename_html, "w")
	logfile.write('<html><head><link rel="stylesheet" type="text/css" href="%s"/><title>Update log</title></head><body>' % filename_css)

	levelmap = {
		logging.INFO: '<a class="info">INFO</a>',
		logging.DEBUG: '<a class="debug">DEBUG</a>',
		logging.ERROR: '<a class="error">ERROR</a>',
		logging.WARNING: '<a class="warning">WARNING</a>',
	}
	class HTMLFormatter(logging.Formatter):
		def format(self, record):
			t = time.strftime("%Y-%m-%d %H:%M:%S")
			msg = record.msg.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
			return "<br><a class='time'>%s</a> %s <a class='msg'>%s</a>" % (t, levelmap[record.levelno], msg)

	loghandler = logging.StreamHandler(logfile)
	loghandler.setFormatter(HTMLFormatter())
	logging.root.setLevel(level)
	logging.root.addHandler(loghandler)

class ImmutableDict(dict):
	'A hashable wrapper around the standard dict.'

	def __init__(self, *args, **kwds):
		dict.__init__(self, *args, **kwds)
	def __setitem__(self, key, value):
		raise NotImplementedError, "don't do that"
	def __delitem__(self, key):
		raise NotImplementedError, "don't do that"
	def clear(self):
		raise NotImplementedError, "don't do that"
	def setdefault(self, k, default=None):
		raise NotImplementedError, "don't do that"
	def popitem(self):
		raise NotImplementedError, "don't do that"
	def update(self, other):
		raise NotImplementedError, "don't do that"
	def __hash__(self):
		return hash(tuple(self.iteritems()))

class HashableList(list):
	'A hashable wrapper around the standard list.'

	def __init__(self, l):
        if l:
            self.list = tuple(l)
        else:
            self.list = []
	def __str__(self):
		return str(self.list)
	def __hash__(self):
		return hash(self.list)
	def __len__(self):
		return len(self.list)
	def __getitem__(self, i):
		return self.list[i]
	def __iter__(self):
		return iter(self.list)

def di_pickle(o):
	"""Given an object, which can be an integer, string, float, list,
	tuple, set, frozenset, dictionary, ImmutableDict or any combination
	thereof, return a string such that di_unpickle() will reconstruct
	the object. The point, ofcourse, being that that di_unpickle() need
	not be in this process on this computer, or even be di_unpickle()
	itself but some function in another language entirely."""
	if o == None:
		return "None"
	t = type(o)
	if t is types.IntType or t is types.LongType:
		return "i%d" % o
	if t is types.BooleanType:
		if o:
			return "i1"
		else:
			return "i0"
	if t is types.FloatType:
		return "d%f" % o
	if t is types.StringType:
		return "s'%s'" % o.replace("'", "\\'")
	if t is types.ListType:
		return "L(%s)" % "".join([ di_pickle(x) for x in o])
	if isinstance(o, HashableList):
		return "L(%s)" % "".join([ di_pickle(x) for x in o.list])
	if t is types.TupleType:
		return "T(%s)" % "".join([ di_pickle(x) for x in o])
	if isinstance(o, (set, frozenset)):
		return "S(%s)" % "".join([ di_pickle(x) for x in o])
	if t is types.DictType or isinstance(o, ImmutableDict):
		return "D(%s)" % "".join([ "%s%s" % (di_pickle(k), di_pickle(v)) for k, v in o.items()])
	raise "Unsupported type in di_pickle()", str(t)

def di_unpickle(s):
	"""This is the converse of di_pickle(), or anything that encodes like
	it. Given a string, reconstruct the encoded object."""
	def do_unpickle(s):
		if s[:4] == "None":
			return None, s[4:]
		if s[0] == 'i':
			j = 1
			if s[j] == '-':
				negative = 1
				j = j + 1
			else:
				negative = 0
			while s[j].isdigit():
				j = j + 1
			if negative:
				return -int(s[2:j]), s[j:]
			else:
				return int(s[1:j]), s[j:]
		if s[0] == 'd':
			j = 1
			if s[j] == '-':
				negative = 1
				j = j + 1
			else:
				negative = 0
			while s[j].isdigit() or s[j] == '.':
				j = j + 1
			if negative:
				return -float(s[2:j]), s[j:]
			else:
				return float(s[1:j]), s[j:]
		if s[0] == 's':
			if s[1] != "'":
				raise "Malformed input in di_unpickle()"
			j = 2
			while s[j] != "'" or s[j - 1] == "\\":
				j = j + 1
			return s[2:j].replace("\\", ""), s[j + 1:]
		if s[0] == 'D':
			if s[1] != "(":
				raise "Malformed input in di_unpickle()"
			l = {}
			s = s[2:]
			while s[0] != ")":
				key, s = do_unpickle(s)
				value, s = do_unpickle(s)
				if type(key) is types.ListType:
					key = HashableList(key)
				elif type(key) is types.DictType:
					key = ImmutableDict(key)
				l[key] = value
			return l, s[1:]
		# the rest of the legitimate options are list-like
		what = s[0]
		if s[1] != "(":
			raise "Malformed input in di_unpickle()"
		l = []
		s = s[2:]
		while s[0] != ")":
			item, s = do_unpickle(s)
			l.append(item)
		if what == 'L':
			return l, s[1:]
		if what == 'S':
			if len(l) > 0 and type(l[0]) is types.ListType:
				l2 = [ HashableList(x) for x in l ]
				return frozenset(l2), s[1:]
			return frozenset(l), s[1:]
		if what == 'T':
			return tuple(l), s[1:]

	o, rest = do_unpickle(s)
	if len(rest) > 0:
		raise "Extra garbage in di_unpickle()"
	return o
