import pycouchdb
import time
import sys
import pprint

reload(sys)
sys.setdefaultencoding('utf-8')

# example output https://gist.github.com/sente/e5dd3d20fd0919722d83a9520a6f9984


from optparse import OptionParser
import pycouchdb

import sys
reload(sys)
sys.setdefaultencoding('utf-8')


usage = "usage: %prog [options] arg"
parser = OptionParser(usage)

parser.add_option("--id", "--_id",
                dest="id",
                default="",
                action="store",
                help="the resource to change"
                )

parser.add_option("-H", "--host",
                dest="host",
                default="",
                action="store",
                help="The couchdb server/host"
                )

parser.add_option("--database",
                dest="database",
                default="",
                action="store",
                help="the database on the host"
                )



(options, args) = parser.parse_args()



def list_attachments(host, database):

    server = pycouchdb.Server(host)
    db = server.database(database)

    resources = list(db.all())
    docs = [r.get('doc') for r in resources if r['doc'].get("title")]

    #attachments = [att for att in doc['_attachments'] if att.endswith('.jpg')]
    for i,d in enumerate(docs):
        print "{}\t{}/_utils/document.html?{}/{}\t{}".format(i, host, database, d.get('_id'), d.get('openWith',''))
        if 'title' not in d:
            next
        for att in d.get('_attachments',{}):
            print '{}\t{}\t{}\t{}/{}'.format(d.get('openWith'),len(d.get('_attachments',{})),d['_id'], d.get('title'), att)
        print



def delete_attachments_and_update_openwith(database, d, dryrun=True):

    d.get('_id')
    keys = d.get('_attachments',{}).keys()

    opener = d.get('openWith')

    jpgs = [k for k in keys if k.endswith('.jpg')]
    pdfs = [k for k in keys if k.endswith('.pdf')]

    bail = False

    if not jpgs:
        bail = True

    if not pdfs:
        bail = True

    if opener != 'Bell-Reader':
        bail = True


    if bail:
        print "SKIP\tid: {}\tjpgs:{}\tpdfs:{}\topenwith:{}".format(d.get('_id'),len(jpgs),len(pdfs), opener)
    else:
        print "DELETE\tid: {}\tjpgs:{}\tpdfs:{}\topenwith:{}".format(d.get('_id'),len(jpgs),len(pdfs), opener)

    if dryrun || bail:
        return

    for k in jpgs:
        del d['_attachments'][k]

    d['openWith'] = 'PDF.js'

    return database.save(d)


if __name__ == '__main__':

    server = pycouchdb.Server(options.host)
    db = server.database(options.database)

    print 'getting docs'
    docs = list(db.all())
    print 'got {} docs'.format(len(docs))

    for d in docs:
#        print d
        delete_attachments_and_update_openwith(db, d.get('doc'), dryrun=True)

