import base64
import random
import string
from functools import lru_cache
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

templates = Jinja2Templates(directory='templates')

ACCESS_TOKEN = ''


class Settings(BaseSettings):
    ## OAuth 2.0
    client_id: SecretStr = SecretStr('')
    client_secret: SecretStr = SecretStr('')

    ## Spotify API
    spotify_token_url: str = 'https://accounts.spotify.com/api/token'
    spotify_auth_url: str = 'https://accounts.spotify.com/authorize?redirect_uri='

    ## Redirect URI
    redirect_uri: str = 'http://localhost:8000/callback'

    model_config = SettingsConfigDict(env_file='.env')


@lru_cache
def get_settings():
    return Settings()


app = FastAPI()


def generate_random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def set_access_token(code: str, settings: Settings = Depends(get_settings)):
    oauth_credentials = f'{settings.client_id.get_secret_value()}:{settings.client_secret.get_secret_value()}'
    data = {
        'code': code,
        'redirect_uri': settings.redirect_uri,
        'grant_type': 'authorization_code'
    }
    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + base64.b64encode(oauth_credentials.encode()).decode()
    }
    response = requests.post(settings.spotify_token_url, headers=headers, data=data)
    access_token = response.json().get('access_token')
    global ACCESS_TOKEN
    ACCESS_TOKEN = access_token


@app.get('/callback')
def callback(_: str = Depends(set_access_token)):
    return RedirectResponse('http://localhost:8000/songs')


@app.get('/songs', response_class=HTMLResponse)
def get_songs(request: Request, time_range: str = 'long_term', limit: int = 10):
    url = 'https://api.spotify.com/v1/me/top/tracks'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }
    response = requests.get(url, headers=headers, params={'time_range': time_range, 'limit': limit})

    data = response.json()['items']
    song_names = [song['name'] for song in data]
    album_covers = [song['album']['images'][0]['url'] for song in data]

    return templates.TemplateResponse(
        request=request, name='songs.html', context={'songs_and_covers': zip(song_names, album_covers)}
    )


@app.get('/login')
async def login(settings: Settings = Depends(get_settings)):
    scope = 'user-read-private user-read-email user-top-read'
    state = generate_random_string(16)

    query_params = {
        'response_type': 'code',
        'client_id': settings.client_id.get_secret_value(),
        'scope': scope,
        'state': state
    }

    spotify_auth_url = f'{settings.spotify_auth_url}{settings.redirect_uri}&{urlencode(query_params)}'
    return RedirectResponse(spotify_auth_url)
