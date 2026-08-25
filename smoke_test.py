"""Run after dependencies are installed: python smoke_test.py"""
import os, tempfile
import app as tutor

with tutor.app.test_client() as client:
    r=client.get('/login')
    assert r.status_code == 200
    print('login route OK')
print('Smoke test passed.')
