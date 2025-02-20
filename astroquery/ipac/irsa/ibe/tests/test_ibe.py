# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os
import requests

import pytest
from astropy.table import Table
from astropy.coordinates import SkyCoord
import astropy.units as u

from astroquery.utils.mocks import MockResponse
from astroquery.ipac.irsa.ibe import Ibe

DATA_FILES = {
    ('https://irsa.ipac.caltech.edu/ibe/search/', None): 'missions.html',
    ('https://irsa.ipac.caltech.edu/ibe/search/ptf/', None): 'datasets.html',
    ('https://irsa.ipac.caltech.edu/ibe/search/ptf/images/',
     None): 'tables.html',
    ('https://irsa.ipac.caltech.edu/ibe/search/ptf/images/level1',
     frozenset((('FORMAT', 'METADATA'),))): 'columns.txt',
    ('https://irsa.ipac.caltech.edu/ibe/search/ptf/images/level1',
     frozenset((('where', 'expid <= 43010'), ('POS', '148.969687,69.679383'),
                ('INTERSECT', 'OVERLAPS')))): 'pos.txt',
    ('https://irsa.ipac.caltech.edu/ibe/search/ptf/images/level1',
     frozenset((('where', "ptffield = 4808 and filter='R'"),
                ('INTERSECT', 'OVERLAPS')))): 'field_id.txt'}


def data_path(filename):
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    return os.path.join(data_dir, filename)


@pytest.fixture
def patch_get(request):
    mp = request.getfixturevalue("monkeypatch")

    mp.setattr(requests.Session, 'request', get_mockreturn)
    return mp


def get_mockreturn(self, method, url,
                   params=None,
                   data=None,
                   headers=None,
                   cookies=None,
                   files=None,
                   auth=None,
                   timeout=None,
                   allow_redirects=True,
                   proxies=None,
                   hooks=None,
                   stream=None,
                   verify=None,
                   cert=None,
                   json=None):
    filename = data_path(DATA_FILES[(url,
                                     params and frozenset(params.items()))])
    with open(filename, 'rb') as infile:
        content = infile.read()
    return MockResponse(
        content, url=url, headers=headers, stream=stream, auth=auth)


def test_list_missions(patch_get):
    assert Ibe.list_missions() == ['twomass', 'wise', 'ptf']


def test_list_datasets(patch_get):
    assert Ibe.list_datasets('ptf') == ['images']


def test_list_tables(patch_get):
    assert Ibe.list_tables('ptf', 'images') == ['level1', 'level2']


def test_get_columns(patch_get):
    columns = Ibe.get_columns('ptf', 'images', 'level1')
    assert len(columns) == 173
    assert columns[0]['name'] == 'expid'


def test_ibe_pos(patch_get):
    table = Ibe.query_region(
        SkyCoord(148.969687 * u.deg, 69.679383 * u.deg),
        where='expid <= 43010')
    assert isinstance(table, Table)
    assert len(table) == 21


def test_ibe_field_id(patch_get):
    table = Ibe.query_region(
        where="ptffield = 4808 and filter='R'")
    assert isinstance(table, Table)
    assert len(table) == 22


def test_deprecated_namespace_import_warning():
    with pytest.warns(DeprecationWarning):
        import astroquery.ibe  # noqa: F401
