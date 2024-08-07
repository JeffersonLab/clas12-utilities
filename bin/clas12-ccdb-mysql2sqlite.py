#!/usr/bin/env python

import os, sys
from subprocess import Popen, PIPE
import argparse

parser = argparse.ArgumentParser(description='Create an SQLite file from a CCDB MySQL database.  Defaults are for clas12.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('outfile', type=str, help='output file', nargs='?', default='clas12.sqlite')
parser.add_argument('-H', metavar='HOST', help='host', default='clasdb.jlab.org')
parser.add_argument('-D', metavar='DB', help='database', default='clas12')
parser.add_argument('-U', metavar='USER', help='username', default='clas12writer')
parser.add_argument('-P', metavar='PASS', help='password', required=True)
args = parser.parse_args()

if os.path.exists(args.outfile):
    raise RuntimeError('File exists: {}'.format(args.outfile))


# Converts a mysqldump file into a Sqlite 3 compatible file. It also extracts the MySQL `KEY xxxxx` from the
# CREATE block and create them in separate commands _after_ all the INSERTs.

# Awk is choosen because it's fast and portable. You can use gawk, original awk or even the lightning fast mawk.
# The mysqldump file is traversed only once.

# Usage: $ ./mysql2sqlite mysqldump-opts db-name | sqlite3 database.sqlite
# Example: $ ./mysql2sqlite --no-data -u root -pMySecretPassWord myDbase | sqlite3 database.sqlite

# Thanks to and @artemyk and @gkuenning for their nice tweaks.

cmd = r'''\
mysqldump --skip-tz-utc --compatible=ansi --skip-extended-insert --compact  \
-u___USER___ -p'___PASS___' -h___HOST___ ___DB___ | \
awk '

BEGIN {
    FS=",$"
    print "PRAGMA synchronous = OFF;"
    print "PRAGMA journal_mode = MEMORY;"
    print "BEGIN TRANSACTION;"
}

# CREATE TRIGGER statements have funny commenting.  Remember we are in trigger.
/^\/\*.*CREATE.*TRIGGER/ {
    gsub( /^.*TRIGGER/, "CREATE TRIGGER" )
    print
    inTrigger = 1
    next
}

# The end of CREATE TRIGGER has a stray comment terminator
/END \*\/;;/ { gsub( /\*\//, "" ); print; inTrigger = 0; next }

# The rest of triggers just get passed through
inTrigger != 0 { print; next }

# Skip other comments
/^\/\*/ { next }

# Print all `INSERT` lines. The single quotes are protected by another single quote.
/INSERT/ {
    gsub( /\\\047/, "\047\047" )
    gsub(/\\n/, "\n")
    gsub(/\\r/, "\r")
    gsub(/\\"/, "\"")
    gsub(/\\\\/, "\\")
    gsub(/\\\032/, "\032")
    print
    next
}

# Print the `CREATE` line as is and capture the table name.
/^CREATE/ {
    print
    if ( match( $0, /"[^"]+/ ) ) tableName = substr( $0, RSTART+1, RLENGTH-1 )
}

# Replace `FULLTEXT KEY` or any other `XXXXX KEY` except PRIMARY by `KEY`
/^  [^"]+KEY/ && !/^  PRIMARY KEY/ { gsub( /.+KEY/, "  KEY" ) }

# Get rid of field lengths in KEY lines
/ KEY/ { gsub(/\([0-9]+\)/, "") }

# Print all fields definition lines except the `KEY` lines.
/^  / && !/^(  KEY|\);)/ {
    gsub( /AUTO_INCREMENT|auto_increment/, "" )
    gsub( /(CHARACTER SET|character set) [^ ]+ /, "" )
    gsub( /DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP|default current_timestamp on update current_timestamp/, "" )
    gsub( /(COLLATE|collate) [^ ]+ /, "" )
    gsub(/(ENUM|enum)[^)]+\)/, "text ")
    gsub(/(SET|set)\([^)]+\)/, "text ")
    gsub(/UNSIGNED|unsigned/, "")
    gsub(/" [^ ]*(INT|int)[^ ]*/, "\" integer")
    if (prev) print prev ","
    prev = $1
}

# `KEY` lines are extracted from the `CREATE` block and stored in array for later print
# in a separate `CREATE KEY` command. The index name is prefixed by the table name to
# avoid a sqlite error for duplicate index name.
/^(  KEY|\);)/ {
    if (prev) print prev
    prev=""
    if ($0 == ");"){
        print
    } else {
        if ( match( $0, /"[^"]+/ ) ) indexName = substr( $0, RSTART+1, RLENGTH-1 )
        if ( match( $0, /\([^()]+/ ) ) indexKey = substr( $0, RSTART+1, RLENGTH-1 )
        key[tableName]=key[tableName] "CREATE INDEX \"" tableName "_" indexName "\" ON \"" tableName "\" (" indexKey ");\n"
    }
}

# Print all `KEY` creation lines.
END {
    for (table in key) printf key[table]
    print "END TRANSACTION;"
}
' | sqlite3 ''' + args.outfile

cmd = cmd.replace('___HOST___',args.H)
cmd = cmd.replace('___DB___',args.D)
cmd = cmd.replace('___USER___',args.U)
cmd = cmd.replace('___PASS___',args.P)

proc = Popen(cmd, shell=True, executable='/bin/bash')
sys.exit(proc.wait())
