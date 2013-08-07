import cherrypy
import thread
import core, connect
import twitter
import gplus
import apptree
import view
from sessioninfo import get_session


    
    #modelled off gplus oauth login


class Server(object):
    def __init__(self, dbconn=None, colls=None, **kwargs):
        if not dbconn:
            dbconn = connect.init_connection(**kwargs)
        self.dbconn = dbconn
        self.gplus_keys = gplus.get_keys()
        self.twitter_keys = twitter.read_keyfile()
        self.reload_views(colls)

    def start(self):
        'start cherrypy server as background thread, retaining control of main thread'
        self.threadID = thread.start_new_thread(self.serve_forever, ())

    def serve_forever(self):
        cherrypy.quickstart(self, '/', 'cp.conf')

    def reload_views(self, colls=None):
        'reload view templates from disk'
        if not colls:
            colls = apptree.get_collections()
        for attr, c in colls.items(): # bind collections to server root
            setattr(self, attr, c)

    def login(self, email, password):
        'check password and create session if authenticated'
        try:
            a = core.EmailAddress(email)
        except KeyError:
            return 'no such email address'
        p = a.parent
        if p.authenticate(password):
            get_session()['email'] = email
            get_session()['person'] = p
        else:
            return 'bad password'
        return view.redirect('/view?view=person&person=' + str(p._id))
    login.exposed = True

    #31.7.2013 (Rod Shapeley):
    #
    #note that localhost:8000 will have to be changed if moving to production.
    #need to refer to cp.conf here

    def twitter_login(self):
        redirect_url, tokens = twitter.start_oauth('http://localhost:8000/twitter_oauth')
        get_session()['twitter_request_token'] = tokens
        self.twitter_session = get_session()['twitter_request_token']    #workaround for disappearing session key 2.8.2013 Rod Shapeley
        return view.redirect(redirect_url)
    twitter_login.exposed = True


    def twitter_oauth(self, oauth_token, oauth_verifier):
        t = self.twitter_session
        auth = twitter.complete_oauth(t[0], t[1], oauth_verifier)    #now up to here 7:54pm 2.8.2013 Rod Shapeley
        #print "no problems so far"
        p, user, api = twitter.get_auth_person(auth)  #now up to here 7:58pm 2.8.2013 Rod Shapeley
        get_session()['twitter_oauth'] = auth     # workaround - extract p, user, api from auth. 7.8.2013 Rod Shapeley
        self.twitter_auth = auth # just for hand testing
        # pickling error http://docs.python.org/2/library/pickle.html#what-can-be-pickled-and-unpickled
        # therefore will need to rewrite previous functions (oauth_twitter) as a class twitter.Oauth
        # in order that it can be pickled.  at least, that's a good start. 8:26pm 2.8.2013 Rod Shapeley
        #the problem is not with twitter.complete_oauth, twitter.start_oauth.  No, the problem is with
        #twitter.get_auth_person(auth) .... this is where the problem lies.
        #no, not even there.  looks like it is in assignation of get_session()['person'] = p.
        #return 'Logged in to twitter'
        print 'Logged in to twitter'
        return view.redirect('http://localhost:8000')  #might need to be changed in production
    twitter_oauth.exposed = True

    def gplus_login(self):
        oauth = gplus.OAuth(keys=self.gplus_keys)
        get_session()['gplus_oauth'] = oauth
        return view.redirect(oauth.get_authorize_url())
    gplus_login.exposed = True

    def oauth2callback(self, error=False, **kwargs):
        if error:
            return error
        oauth = get_session()['gplus_oauth']
        oauth.get_credentials(**kwargs)
        get_session()['person'] = oauth.get_person()
        return view.redirect('/')
    oauth2callback.exposed = True

    def signout(self):
        'force this session to expire immediately'
        cherrypy.lib.sessions.expire()
        return view.redirect('/')
    signout.exposed = True
            

if __name__ == '__main__':
    s = Server()
    thread.start_new_thread(view.poll_recent_events, (s.papers.klass, s.topics.klass))
    print 'starting server...'
    s.start()
    #print 'starting gplus #spnetwork polling...'
    #gplus.publicAccess.start_poll(300, 10, view.recentEventsDeque)

