#__author__ == "Jackie Cohen (jczetta)"
# An application about recording favorite songs & info

import os
from flask import Flask, render_template, session, redirect, url_for, flash
from flask_script import Manager, Shell
# from flask_moment import Moment # requires pip/pip3 install flask_moment
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField
from wtforms.validators import Required
from flask_sqlalchemy import SQLAlchemy
import random
from flask_migrate import Migrate, MigrateCommand # needs: pip/pip3 install flask-migrate

from werkzeug import secure_filename

# Configure base directory of app
basedir = os.path.abspath(os.path.dirname(__file__))

# Application configurations
app = Flask(__name__)
app.debug = True
app.use_reloader = True
app.static_folder = 'static'
app.config['SECRET_KEY'] = 'hard to guess string'
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/songs_data" # TODO: decide what your new database name will be, and create it in postgresql, before running this new application (it's similar to an old one, but has some more to it)
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Set up Flask debug stuff
manager = Manager(app)
db = SQLAlchemy(app) # For database use
migrate = Migrate(app, db) # For database use/updating
manager.add_command('db', MigrateCommand) # Add migrate command to manager


## You will get the following message when running command to create migration folder:
## python main_app.py db init
## -->
# Please edit configuration/connection/logging settings in ' ... migrations/alembic.ini' before proceeding
## This is what you are supposed to see!

#########
######### Everything above this line is important/useful setup, not problem-solving.
#########


##### Set up Models #####

# Set up association Table between artists and albums
collections = db.Table('collections',db.Column('album_id',db.Integer, db.ForeignKey('albums.id')),db.Column('artist_id',db.Integer, db.ForeignKey('artists.id')))

class Album(db.Model):
    __tablename__ = "albums"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    artists = db.relationship('Artist',secondary=collections,backref=db.backref('albums',lazy='dynamic'),lazy='dynamic')
    songs = db.relationship('Song',backref='Album')


class Artist(db.Model):
    __tablename__ = "artists"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    songs = db.relationship('Song',backref='Artist')

    def __repr__(self):
        return "{} (ID: {})".format(self.name,self.id)

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64),unique=True) # Only unique title songs
    album_id = db.Column(db.Integer, db.ForeignKey("albums.id"))
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"))
    genre = db.Column(db.String(64))

    def __repr__(self):
        return "{} by {} | {}".format(self.title,self.artist_id, self.genre)

##### Set up Forms #####

class SongForm(FlaskForm):
    song = StringField("What is the title of your favorite song?", validators=[Required()])
    artist = StringField("What is the name of the artist who performs it?",validators=[Required()])
    genre = StringField("What is the genre of that song?", validators
        =[Required()])
    album = StringField("What is the album this song is on?", validators
        =[Required()])
    submit = SubmitField('Submit')

class UploadForm(FlaskForm):
    file = FileField()

##### Helper functions

### For database additions / get_or_create functions

def get_or_create_artist(db_session,artist_name):
    artist = db_session.query(Artist).filter_by(name=artist_name).first()
    if artist:
        return artist
    else:
        artist = Artist(name=artist_name)
        db_session.add(artist)
        db_session.commit()
        return artist

def get_or_create_album(db_session, album_name, artists_list=[]):
    album = db_session.query(Album).filter_by(name=album_name).first() # by name filtering for album
    if album:
        return album
    else:
        album = Album(name=album_name)
        for artist in artists_list:
            artist = get_or_create_artist(db_session,artist)
            album.artists.append(artist)
        db_session.add(album)
        db_session.commit()
    return album

def get_or_create_song(db_session, song_title, song_artist, song_album, song_genre):
    song = db_session.query(Song).filter_by(title=song_title).first()
    if song:
        return song
    else:
        artist = get_or_create_artist(db_session, song_artist)
        album = get_or_create_album(db_session, song_album, artists_list=[song_artist]) # list of one song artist each time -- check out get_or_create_album and get_or_create_artist!
        song = Song(title=song_title,genre=song_genre,artist_id=artist.id)
        db_session.add(song)
        db_session.commit()
        return song




##### Set up Controllers (view functions) #####

## Error handling routes
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

## Main route

@app.route('/', methods=['GET', 'POST'])
def index():
    songs = Song.query.all()
    num_songs = len(songs)
    form = SongForm()
    if form.validate_on_submit():
        if db.session.query(Song).filter_by(title=form.song.data).first(): # If there's already a song with that title, though...nvm, can't. Gotta add something like "(covered by..) or whatever"
            flash("You've already saved a song with that title!")
        else:
            get_or_create_song(db.session,form.song.data, form.artist.data, form.album.data, form.genre.data)
        return redirect(url_for('see_all'))
    return render_template('index.html', form=form,num_songs=num_songs)

@app.route('/all_songs')
def see_all():
    all_songs = [] # To be tuple list of title, genre
    songs = Song.query.all()
    for s in songs:
        artist = Artist.query.filter_by(id=s.artist_id).first()
        all_songs.append((s.title,artist.name, s.genre))
    return render_template('all_songs.html',all_songs=all_songs)

@app.route('/all_artists')
def see_all_artists():
    artists = Artist.query.all()
    names = [(a.name, len(Song.query.filter_by(artist_id=a.id).all())) for a in artists]
    return render_template('all_artists.html',artist_names=names)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        filename = secure_filename(form.file.data.filename)
        form.file.data.save('static/imgs/' + filename) # Get file data due to the way the form specifies it -- FileField is special
        # Then can save it wherever you direct it to be saved
        # Can also save File Blobs to database --
        return redirect(url_for('upload'))

    return render_template('upload.html', form=form)
# ...static/imgs/whatevername.jpg
# .../static/imgs/yosemite.jpg
@app.route('/viewimage')
def random_image():
    names = os.listdir(os.path.join(app.static_folder, 'imgs'))
    img_url = url_for('static', filename=os.path.join('imgs', random.choice(names)))
    return render_template('random_image.html', img_url=img_url)

@app.route('/all_images')
def all_images():
    names = os.listdir(os.path.join(app.static_folder, 'imgs'))
    img_urls = []
    for name in names:
        img_url = url_for('static', filename=os.path.join('imgs', name))
        img_urls.append(img_url)
    return render_template('all_images.html',img_urls=img_urls)

if __name__ == '__main__':
    db.create_all()
    manager.run() # NEW: run with this: python main_app.py runserver
    # Also provides more tools for debugging
