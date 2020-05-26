import os
import time

import pytest
import uuid

from app import app, queueStatus, shutdown, wholeStat


@pytest.fixture
def client():
    app.config['TESTING'] = True

    with app.test_client() as client:
        #with app.app_context():
        #    app.init_db()
        yield client

    #shutdown()

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

def test_status(client):
    """Test bad inputs to status page"""
    uuidkey = str(uuid.uuid1())
    rc = client.get('/status/' + uuidkey, follow_redirects=True)
    assert b'Error: bad UUID' in rc.data

    rc = client.get('/status/', follow_redirects=True)
    assert b'404 Not Found' in rc.data

    rc = client.get('/status/notauuid123' + uuidkey, follow_redirects=True)
    assert b'404 Not Found' in rc.data

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
    assert b'Link To Download' not in rv.data

    #out of bounds lon/lat
    rv = client.post('/generate', data=dict(
        lat='206.56',
        long='-400',
        radius='1',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' in rv.data
    assert b'Link To Download' not in rv.data

def test_simplegen(client):
    """Test that a small piece of terrain can be generated"""

    rv = client.post('/generate', data=dict(
        lat='-35.363261',
        long='149.165230',
        radius='1',
    ), follow_redirects=True)

    assert b'<title>AP Terrain Generator</title>' in rv.data
    assert b'Error' not in rv.data
    assert b'Link To Download' in rv.data

    uuidkey = (rv.data.split(b"footer")[1][1:-2]).decode("utf-8") 
    assert uuidkey != ""

    #wait for generator to complete, up to 30 seconds
    startime = time.time()
    while True:
        time.sleep(0.5)
        if time.time() - startime > 30:
            assert False
            break
        else:
            rc = client.get('/status/' + uuidkey, follow_redirects=True)
            if "ready" in rc.data.decode("utf-8") :
                break

    #file should be ready for download and around 2MB in size
    rdown = client.get('/terrain/' + uuidkey + ".zip", follow_redirects=True)
    assert len(rdown.data) > (1*1024*1024)

    #shutdown()

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
        radius='1',
    ), follow_redirects=True)
    time.sleep(0.1)

    rvc = client.post('/generate', data=dict(
        lat='-30.363261',
        long='137.165230',
        radius='1',
    ), follow_redirects=True)
    time.sleep(0.1)

    # Assert reponse is OK and get UUID for each ter gen
    allUuid = []
    for rv in [rva, rvb, rvc]:
        assert b'<title>AP Terrain Generator</title>' in rv.data
        assert b'Error' not in rv.data
        assert b'Link To Download' in rv.data
        uuidkey = (rv.data.split(b"footer")[1][1:-2]).decode("utf-8") 
        assert uuidkey != ""
        allUuid.append(uuidkey)

    #wait for generator to complete, up to 50 seconds
    startime = time.time()
    allUuidComplete = []
    while len(allUuid) != len(allUuidComplete):
        time.sleep(1)
        if time.time() - startime > 120:
            break
        else:
            # check if done
            for uukey in allUuid:
                rcc = client.get('/status/' + uukey, follow_redirects=True)
                if "ready" in rcc.data.decode("utf-8") and (uukey not in allUuidComplete):
                    allUuidComplete.append(uukey)

    #files should be ready for download and around 2MB in size
    for uukey in allUuid:
        rdown = client.get('/terrain/' + uukey + ".zip", follow_redirects=True)
        assert len(rdown.data) > (0.7*1024*1024)

    print(wholeStat())
    shutdown()


