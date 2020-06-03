import os
import time

import pytest
import uuid

from app import app

def createFile(name, size):
    # create a file of random data
    with open(name, 'wb') as fout:
        fout.write(os.urandom(size)) # replace 1024 with size_kb if not unreasonably large


@pytest.fixture
def client():
    app.config['TESTING'] = True

    # create fake pre-gen terrain files if they don't exist
    #preGen = ['S35E149.DAT', 'S35E147.DAT', 'S30E137.DAT', 'S31E136.DAT', 'S31E137.DAT', 'S31E138.DAT',
    #          'S30E136.DAT', 'S30E137.DAT', 'S30E138.DAT', 'S29E136.DAT', 'S29E137.DAT', 'S29E138.DAT']
    #for fileSingle in preGen:
    #    full = os.path.join(os.getcwd(), "processedTerrain", fileSingle)
    #    print(full)
    #    if not os.path.exists(full):
    #        print("Making fake file: " + full)
    #        createFile(full, 1024 * 1024)

    with app.test_client() as client:
        yield client

def test_homepage(client):
    """Test that the homepage can be generated"""

    rv = client.get('/')
    # assert all the controls are there
    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'<form action="/generate" method="post">' in rv.data
    assert b'<input type="text" id="lat" name="lat" value="-35.363261">' in rv.data
    assert b'<input type="text" id="long" name="long" value="149.165230">' in rv.data
    assert b'<input type="number" id="radius" name="radius" value="100" min="1" max="400">' in rv.data
    assert b'<input type="submit" value="Submit" method="post">' in rv.data

def test_badinput(client):
    """Test bad inputs"""
    # no input
    rv = client.post('/generate', data=dict(
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' in rv.data
    assert b'Link To Download' not in rv.data

    #partial input
    rv = client.post('/generate', data=dict(
        lat='-35.363261',
        long='149.165230',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' in rv.data
    assert b'Link To Download' not in rv.data

    #bad lon/lat
    rv = client.post('/generate', data=dict(
        lat='I am bad data',
        long='echo test',
        radius='1',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' in rv.data
    assert b'download="terrain.zip"' not in rv.data

    #out of bounds lon/lat
    rv = client.post('/generate', data=dict(
        lat='206.56',
        long='-400',
        radius='1',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' in rv.data
    assert b'download="terrain.zip"' not in rv.data

def test_simplegen(client):
    """Test that a small piece of terrain can be generated"""

    rv = client.post('/generate', data=dict(
        lat='-35.363261',
        long='149.165230',
        radius='1',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' not in rv.data
    assert b'Tiles outside of +60 to -60 latitude were requested' not in rv.data
    assert b'download="terrain.zip"' in rv.data

    uuidkey = (rv.data.split(b"footer")[1][1:-2]).decode("utf-8") 
    assert uuidkey != ""

    #file should be ready for download and around 2MB in size
    rdown = client.get('/terrain/' + uuidkey + ".zip", follow_redirects=True)
    assert b'404 Not Found' not in rdown.data
    assert len(rdown.data) > (1*1024*1024)

def test_simplegenoutside(client):
    """Test that a small piece of terrain can be generated with partial outside +-60latitude"""

    rv = client.post('/generate', data=dict(
        lat='-58.363261',
        long='149.165230',
        radius='200',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' not in rv.data
    assert b'Tiles outside of +60 to -60 latitude were requested' in rv.data
    assert b'download="terrain.zip"' in rv.data

    uuidkey = (rv.data.split(b"footer")[1][1:-2]).decode("utf-8") 
    assert uuidkey != ""

    #file should be ready for download and around 2MB in size
    rdown = client.get('/terrain/' + uuidkey + ".zip", follow_redirects=True)
    assert b'404 Not Found' not in rdown.data
    assert len(rdown.data) > (0.25*1024*1024)

def test_multigen(client):
    """Test that a a few small piece of terrains can be generated"""

    rva = client.post('/generate', data=dict(
        lat='-35.363261',
        long='149.165230',
        radius='1',
    ), follow_redirects=True)
    time.sleep(0.1)

    rvb = client.post('/generate', data=dict(
        lat='-35.363261',
        long='147.165230',
        radius='10',
    ), follow_redirects=True)
    time.sleep(0.1)

    rvc = client.post('/generate', data=dict(
        lat='-30.363261',
        long='137.165230',
        radius='100',
    ), follow_redirects=True)
    time.sleep(0.1)

    # Assert reponse is OK and get UUID for each ter gen
    allUuid = []
    for rv in [rva, rvb, rvc]:
        assert b'<title>AP Terrain Generator</title>' in rv.data
        assert b'Error' not in rv.data
        assert b'download="terrain.zip"' in rv.data
        uuidkey = (rv.data.split(b"footer")[1][1:-2]).decode("utf-8") 
        assert uuidkey != ""
        allUuid.append(uuidkey)

    #files should be ready for download and around 0.7MB in size
    for uukey in allUuid:
        rdown = client.get('/terrain/' + uukey + ".zip", follow_redirects=True)
        assert b'404 Not Found' not in rdown.data
        assert len(rdown.data) > (0.7*1024*1024)



