""" Script:  generator

Generate a Selenium testcase using request / response logiles from tcpwatch.

$Id$
"""

import sys
import re
import getopt
import glob
import cgi
import mimetools
import urllib
import urlparse
import multifile
import StringIO

_TEST_CASE_HEADER = """\
<html>
<head>
<title>%(TEST_CASE_TITLE)s</title>
</head>
<body>
<table cellpadding="1" cellspacing="1" border="1">
 <tbody>
  <tr>
   <td rowspan="1" colspan="3">%(TEST_CASE_TITLE)s<br>
  </td>
 </tr>
"""

_TEST_CASE_FOOTER = """
 </tbody>
</table>
</body>
</html>
"""

_GET_REQUEST_SKELETON = """
  <tr>
   <td>open</td>
   <td>%(REQUEST_URI)s</td>
   <td>&nbsp;</td>
  </tr>
"""

_POST_REQUEST_SKELETON = """
  <tr>
   <td>click</td>
   <td>submit</td>
   <td>&nbsp;</td>
  </tr>
"""

_REDIRECT_SKELETON = """
  <tr>
   <td>verifyLocation</td>
   <td>%(REDIRECTED_URL)s</td>
   <td>&nbsp;</td>
  </tr>
"""

_INPUT_FIELD_SKELETON = """
  <tr>
   <td>type</td>
   <td>%(FIELD_NAME)s</td>
   <td>%(FIELD_VALUE)s</td>
  </tr>
"""

_SELECT_FIELD_SKELETON = """
  <tr>
   <td>select</td>
   <td>%(FIELD_NAME)s</td>
   <td>%(FIELD_VALUE)s</td>
  </tr>
"""

class ScenarioGenerator:
    """
        Convert a series of HTTP requests files (as generated by
        LoggingProxy) into a scenario file (to be consumed by
        FT_Runner).
    """
    _verbosity              = 1
    _logfile_directory      = '/tmp'
    _logfile_prefix         = 'watch'
    _logfile_extension_req  = 'request'
    _logfile_extension_resp = 'response'
    _output_file            = None
    _exclude_patterns       = []
    _exclude_file           = None
    _exclude_regex          = None
    _site_host              = None
    _site_path              = None
    _test_case_title        = None

    def __init__( self, args ):

        self.parseOptions( args )

    def printUsage( self, msg=None ):
        """
            Dump a help message, and bail out.
        """
        sys.stderr.write( """
  %(GENERATOR_EXE)s [-?vq] \\
                     [-l log_dir] [-f log_prefix] [-e log_extension] \\
                     [-o file] [-x pattern] [-X file] \\
                     [-h site_host] [-r site_path]

    -?, --help                      Print this help message

    -v, --verbose                   Increment verbosity (default is '1')

    -q, --quiet                     Set verbosity to '0'

    -l, --logfile-directory         Directory from which to read log files
                                    (default '%(LOGFILE_DIRECTORY)s')

    -f, --logfile-prefix            Prefix for log file names
                                    (default '%(LOGFILE_PREFIX)s')

    -e, --logfile-extension         Extension for log file request names
                                    (default '%(LOGFILE_EXTENSION_REQ)s')

    -E, --logfile-response          Extension for log file response names
                                    (default '%(LOGFILE_EXTENSION_RESP)s')

    -o, --output-file               Write to 'file', instead of default
                                    (%(LOGFILE_PREFIX)s.zft).
                                    Use '-' to write to stdout.

    -x, --exclude-pattern           Exclude requests which match 'pattern'
                                    (e.g., to suppress stylesheet or images).

    -X, --exclude-file              Exclude requests which match any pattern
                                    read from 'file' (one pattern per line).

    -h, --site-host                 Specify the host / port of the site being
                                    tested.

    -p, --site-path                 Specify the path to the "base" of the
                                    site being tested.

%(MESSAGE)s\n""" % { 'GENERATOR_EXE'        : sys.argv[0]
                   , 'LOGFILE_DIRECTORY'    : self._logfile_directory
                   , 'LOGFILE_PREFIX'       : self._logfile_prefix
                   , 'LOGFILE_EXTENSION_REQ'    : self._logfile_extension_req
                   , 'LOGFILE_EXTENSION_RESP'    : self._logfile_extension_resp
                   , 'MESSAGE'              : msg or ''
                   } )
        sys.exit( 1 )

    def parseOptions( self, args ):
        """
            Parse command-line options.
        """
        verbosity = self._verbosity
        logfile_directory = logfile_prefix = None
        logfile_extension_req = logfile_extension_resp = None
        output_file = exclude_file = site_host = site_path = None
        test_case_title = None

        try:
            opts, ignored = getopt.getopt( args
                                         , "?vql:f:e:E:o:x:X:h:p:T:"
                                         , [ 'help'
                                           , 'verbose'
                                           , 'quiet'
                                           , 'logfile-directory='
                                           , 'logfile-prefix='
                                           , 'logfile-extension='
                                           , 'logfile-extension-response='
                                           , 'output-file='
                                           , 'exclude-pattern'
                                           , 'exclude-file'
                                           , 'site-host='
                                           , 'site-path='
                                           , 'test-case-title='
                                           ]
                                         )
        except getopt.GetoptError, msg:
            self.printUsage( msg=msg)

        for o, v in opts:

            if o == '-?' or o == '--help':
                self.printUsage()

            if o == '-v' or o == '--verbose':
                verbosity = verbosity + 1

            if o == '-q' or o == '--quiet':
                verbosity = 0

            if o == '-l' or o == '--logfile-directory':
                logfile_directory = v

            if o == '-f' or o == '--logfile-prefix':
                logfile_prefix = v

            if o == '-e' or o == '--logfile-extension':
                logfile_extension_req = v

            if o == '-E' or o == '--logfile-extension-response':
                logfile_extension_resp = v

            if o == '-o' or o == '--output-file':
                output_file = v

            if o == '-x' or o == '--exclude-pattern':
                self._addExcludePattern( v )

            if o == '-X' or o == '--exclude-file':
                exclude_file = v

            if o == '-h' or o == '--site-host':
                site_host = v

            if o == '-p' or o == '--site-path':
                site_path = v

            if o == '-T' or o == '--test-case-title':
                test_case_title = v

        self._verbosity = verbosity

        if logfile_directory is not None:
            self._logfile_directory = logfile_directory

        if logfile_prefix is not None:
            self._logfile_prefix = logfile_prefix

        if logfile_extension_req is not None:
            self._logfile_extension_req = logfile_extension_req

        if logfile_extension_resp is not None:
            self._logfile_extension_resp = logfile_extension_resp

        if site_host is not None:
            self._site_host = site_host

        if site_path is not None:
            self._site_path = site_path

        if test_case_title is not None:
            self._test_case_title = test_case_title

        if output_file == '-':
            self._output_file = sys.stdout
        elif output_file is not None:
            self._output_file = open( output_file, 'w' )
        else:
            self._output_file = sys.stdout

        if exclude_file is not None:
            self._exclude_file = exclude_file

    def _log( self, msg, level ):
        """
            Write a note to stderr (if verbosity enabled).
        """
        if level <= self._verbosity:
            sys.stderr.write( "%s\n" % msg )

    def _print( self, fmt, **kw ):
        """
            Dump the appropriately-formatted values to our output
            file.
        """
        self._output_file.write( fmt % kw )


    def _addExcludePattern( self, pattern ):
        """
            Add a pattern to our list of excluded patterns.
        """
        self._exclude_patterns.append( r'(%s)' % pattern )
        self._exclude_regex = None

    def _getExcludeRegex( self
                        ):
        """
            Return a regex which, if matched, indicates that we should
            skip the file.
        """
        if self._exclude_regex is None:

            if self._exclude_file:
                f = open( self._exclude_file )
                for line in f.readlines():
                    line = line.strip()
                    self._addExcludePattern( line )

            if self._exclude_patterns:
                self._exclude_regex = re.compile(
                                        '|'.join( self._exclude_patterns ) )
        return self._exclude_regex

    def _stripSitePath(self, uri, parms):
        """
            Strip off our site-host and site-path from 'uri'.
        """
        ( scheme
        , netloc
        , path
        , url_parm
        , query
        , fragment
        ) = urlparse.urlparse( uri )

        site_host = urlparse.urlunparse( ( scheme, netloc, '', '', '', '' ) )

        if scheme and parms.get( 'site_host' ) is None:
            parms[ 'site_host' ] = site_host

        if site_host != parms[ 'site_host' ]: # XXX foreign site!  Punt!
            return None, None

        if self._site_path and path.startswith( self._site_path ):
            path = path[ len( self._site_path ) : ]

        uri = urlparse.urlunparse(
                            ( '', '', path, url_parm, query, fragment ) )

        return uri, query

    def processFile( self
                   , infilename
                   , outfilename
                   , parms={}
                   , REQUEST_LINE=re.compile( r'^([^\s]+)\s+'
                                              r'([^\s]+)\s+'
                                              r'([^\s]+)$' )
                   , RESPONSE_LINE=re.compile( r'^([^\s]+)\s+'
                                               r'([0-9][0-9][0-9])\s+'
                                               r'(.*)$' )
                   ):
        """
            Process a single request file;  record global context
            in parms.
        """
        self._log( 'Scanning request file: %s' % infilename, 1 )

        parms[ 'content_type' ] = None

        f = open( infilename )
        all_text = f.read()
        body_end = f.tell()
        f.seek( 0 )

        exclude = self._getExcludeRegex()
        if exclude is not None and exclude.search( all_text ):
            self._log( '** matches exclude regex, skipping', 1 )
            return

        request = f.readline().rstrip()
        match = REQUEST_LINE.match( request )

        if not match:
            self._log( 'Invalid request line: %s' % request, 0 )
            return

        http_verb, uri, http_version = match.groups()

        uri, query = self._stripSitePath( uri, parms )

        if uri is None:
            return # XXX foreign site

        headers = mimetools.Message( f )

        body_start = f.tell()
        content_length = body_end - body_start

        content_type = parms[ 'content_type' ] = headers.gettype()
        parms[ 'encoding' ] = headers.getencoding()

        cgi_environ = { 'REQUEST_METHOD' : http_verb
                      , 'QUERY_STRING'   : query
                      , 'CONTENT_TYPE'   : headers.typeheader
                      , 'CONTENT_LENGTH' : content_length
                      }

        if http_verb == 'POST':

            if content_type == 'text/xml':   # XXX XML-RPC, punt!
                return

            form_data = cgi.FieldStorage( fp=f
                                        , environ=cgi_environ
                                        , keep_blank_values=1
                                      # , headers=headers.dict  XXX
                                        )
            for k in form_data.keys():

                v = form_data.getvalue( k )

                # TODO: handle uploaded files.

                self._print( _INPUT_FIELD_SKELETON
                           , FIELD_NAME=k
                           , FIELD_VALUE=v
                           )

            payload = f.read()
            f.close()

            self._print( _POST_REQUEST_SKELETON
                       , REQUEST_URI=uri
                       )
        else:
            self._print( _GET_REQUEST_SKELETON
                       , REQUEST_URI=uri
                       )

        if outfilename:
            self._log( 'Scanning response file: %s' % outfilename, 1 )
            response_file = open( outfilename )
            # could exclude here as well
            status = response_file.readline().rstrip()
            match = RESPONSE_LINE.match( status )
            http_verb, code, reason = match.groups()
            response_headers = mimetools.Message( response_file )
            response_file.close()
        else:
            code = 200

        if code in ('301', '302', '307'):
            response_location = response_headers[ 'Location' ]
            response_uri, query = self._stripSitePath( response_location
                                                     , parms
                                                     )
            self._print( _REDIRECT_SKELETON
                       , REDIRECTED_URL=response_uri
                       )


        return

    def processScenario( self ):
        """
            Read all files in '_logfile_directory' whose prefix
            matches '_logfile_prefix', '_logfile_extension_req', and
            '_logfile_extension_resp';
            create a scenario file with one section per request file,
            dumping to specified output file.
        """
        self._print( _TEST_CASE_HEADER
                   , TEST_CASE_TITLE=self._test_case_title or 'TEST CASE'
                   )

        glob__in_pattern = '%s/%s*.%s' % ( self._logfile_directory
                                         , self._logfile_prefix
                                         , self._logfile_extension_req
                                         )

        glob__out_pattern = '%s/%s*.%s' % ( self._logfile_directory
                                          , self._logfile_prefix
                                          , self._logfile_extension_resp
                                          )

        parms = { 'site_host' : self._site_host
                , 'site_path' : self._site_path
                }

        infilenames = glob.glob( glob__in_pattern )
        infilenames.sort()
        outfilenames = glob.glob( glob__out_pattern )
        outfilenames.sort()
        for infilename in infilenames:
            # find the response file name that matches this request file
            outfilename = re.sub( self._logfile_extension_req + '$'
                                , self._logfile_extension_resp
                                , infilename
                                )
            # XXX error if missing?  Optional outfile processing?
            if outfilename in outfilenames:
                self.processFile( infilename
                                , outfilename
                                , parms
                                )
            else:
                self.processFile( infilename
                                , None
                                , parms
                                )

        self._print( _TEST_CASE_FOOTER )

if __name__ == '__main__':

    ScenarioGenerator( sys.argv[1:] ).processScenario()
