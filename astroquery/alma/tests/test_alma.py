# Licensed under a 3-clause BSD style license - see LICENSE.rst
from io import StringIO
import os

import pytest
from unittest.mock import patch, Mock

from astropy import units as u
from astropy import coordinates as coord
from astropy.table import Table
from astropy.coordinates import SkyCoord
from astropy.time import Time

from astroquery.alma import Alma
from astroquery.alma.core import _gen_sql, _OBSCORE_TO_ALMARESULT
from astroquery.alma.tapsql import _val_parse


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def data_path(filename):
    return os.path.join(DATA_DIR, filename)


def assert_called_with(mock, band=None, calib_level=None, collection=None,
                       data_rights=None, data_type=None, exptime=None,
                       facility=None,
                       field_of_view=None, instrument=None, maxrec=None,
                       pol=None, pos=None, publisher_did=None, res_format=None,
                       spatial_resolution=None, spectral_resolving_power=None,
                       target_name=None, time=None, timeres=None):
    mock.assert_called_once_with(
        band=band, calib_level=calib_level,
        collection=collection, data_rights=data_rights, data_type=data_type,
        exptime=exptime, facility=facility,
        field_of_view=field_of_view, instrument=instrument,
        maxrec=maxrec, pol=pol, pos=pos, publisher_did=publisher_did,
        res_format=res_format, spatial_resolution=spatial_resolution,
        spectral_resolving_power=spectral_resolving_power,
        target_name=target_name, time=time, timeres=timeres)


def test_arg_parser():
    assert _val_parse('11') == [11.0]
    assert _val_parse('<11') == [(None, 11.0)]
    assert _val_parse('<11') == [(None, 11.0)]
    assert _val_parse('>11') == [(11.0, None)]
    assert _val_parse('11|12') == [11, 12]
    assert _val_parse('11|12', val_type=str) == ['11', '12']
    assert _val_parse('2000-01-01 .. 2010-01-01', val_type=str) == \
        [('2000-01-01', '2010-01-01')]
    assert _val_parse('11|12|21') == [11.0, 12.0, 21.0]
    assert _val_parse('(11 | 12 | 21)') == [11.0, 12.0, 21.0]
    assert _val_parse('11 .. 12') == [(11.0, 12.0)]
    assert _val_parse('90 .. 99') == [(90.0, 99.0)]
    assert _val_parse('<11|>12') == [(None, 11.0), (12.0, None)]
    assert _val_parse('11..12|21..22') == [(11.0, 12.0), (21.0, 22.0)]
    assert _val_parse('!(11 .. 12)') == \
        [(None, 11.0), (12.0, None)]

    with pytest.raises(ValueError):
        _val_parse('11 .. 12 .. 13')
    with pytest.raises(ValueError):
        _val_parse('!11')
    with pytest.raises(ValueError):
        _val_parse('11 ..')
    with pytest.raises(ValueError):
        _val_parse('.. 11')


def test_help():
    with patch('sys.stdout', new_callable=StringIO) as stdout_mock:
        Alma.help()
    assert 'Position' in stdout_mock.getvalue()
    assert 'Energy' in stdout_mock.getvalue()
    assert 'Frequency', 'frequency' in stdout_mock.getvalue()


def test_gen_pos_sql():
    # test circle
    # radius defaults to 1.0arcmin
    common_select = 'select * from ivoa.obscore WHERE '
    assert _gen_sql({'ra_dec': '1 2'}) == common_select + "(INTERSECTS(" \
        "CIRCLE('ICRS',1.0,2.0,0.16666666666666666), s_region) = 1)"
    assert _gen_sql({'ra_dec': '1 2, 3'}) == common_select + \
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,3.0), s_region) = 1)"
    assert _gen_sql({'ra_dec': '12:13:14.0 -00:01:02.1, 3'}) == \
        common_select + \
        "(INTERSECTS(CIRCLE('ICRS',12.220555555555556,-0.01725,3.0), " \
        "s_region) = 1)"
    # multiple circles
    assert _gen_sql({'ra_dec': '1 20|40, 3'}) == common_select + \
        "((INTERSECTS(CIRCLE('ICRS',1.0,20.0,3.0), s_region) = 1) OR " \
        "(INTERSECTS(CIRCLE('ICRS',1.0,40.0,3.0), s_region) = 1))"
    assert _gen_sql({'ra_dec': '1|10 20|40, 1'}) == common_select + \
        "((INTERSECTS(CIRCLE('ICRS',1.0,20.0,1.0), s_region) = 1) OR " \
        "(INTERSECTS(CIRCLE('ICRS',1.0,40.0,1.0), s_region) = 1) OR " \
        "(INTERSECTS(CIRCLE('ICRS',10.0,20.0,1.0), s_region) = 1) OR " \
        "(INTERSECTS(CIRCLE('ICRS',10.0,40.0,1.0), s_region) = 1))"

    # test range
    assert _gen_sql({'ra_dec': '0.0..20.0 >20'}) == common_select + \
        "(INTERSECTS(RANGE_S2D(0.0,20.0,20.0,90.0), s_region) = 1)"
    assert _gen_sql({'ra_dec': '12:13:14..12:13:20 <4:20:20'}) == \
        common_select +\
        "(INTERSECTS(RANGE_S2D(12.220555555555556,12.222222222222223," \
        "-90.0,4.338888888888889), s_region) = 1)"
    assert _gen_sql({'ra_dec': '!(10..20) >60'}) == common_select + \
        "((INTERSECTS(RANGE_S2D(0.0,10.0,60.0,90.0), s_region) = 1) OR " \
        "(INTERSECTS(RANGE_S2D(20.0,0.0,60.0,90.0), s_region) = 1))"
    assert _gen_sql({'ra_dec': '0..20|40..60 <-50|>50'}) == common_select + \
        "((INTERSECTS(RANGE_S2D(0.0,20.0,-90.0,-50.0), s_region) = 1) OR " \
        "(INTERSECTS(RANGE_S2D(0.0,20.0,50.0,90.0), s_region) = 1) OR " \
        "(INTERSECTS(RANGE_S2D(40.0,60.0,-90.0,-50.0), s_region) = 1) OR " \
        "(INTERSECTS(RANGE_S2D(40.0,60.0,50.0,90.0), s_region) = 1))"

    # galactic frame
    center = coord.SkyCoord(1, 2, unit=u.deg, frame='galactic')
    assert _gen_sql({'galactic': '1 2, 3'}) == common_select + "(INTERSECTS(" \
        "CIRCLE('ICRS',{},{},3.0), s_region) = 1)".format(
        center.icrs.ra.to(u.deg).value, center.icrs.dec.to(u.deg).value)
    min_point = coord.SkyCoord('12:13:14.0', '-00:01:02.1', unit=u.deg,
                               frame='galactic')
    max_point = coord.SkyCoord('12:14:14.0', '-00:00:02.1', unit=(u.deg, u.deg),
                               frame='galactic')
    assert _gen_sql(
        {'galactic': '12:13:14.0..12:14:14.0 -00:01:02.1..-00:00:02.1'}) == \
        common_select +\
        "(INTERSECTS(RANGE_S2D({},{},{},{}), s_region) = 1)".format(
            min_point.icrs.ra.to(u.deg).value,
            max_point.icrs.ra.to(u.deg).value,
            min_point.icrs.dec.to(u.deg).value,
            max_point.icrs.dec.to(u.deg).value)

    # combination of frames
    center = coord.SkyCoord(1, 2, unit=u.deg, frame='galactic')
    assert _gen_sql({'ra_dec': '1 2, 3', 'galactic': '1 2, 3'}) == \
        "select * from ivoa.obscore WHERE " \
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,3.0), s_region) = 1) AND " \
        "(INTERSECTS(CIRCLE('ICRS',{},{},3.0), s_region) = 1)".format(
        center.icrs.ra.to(u.deg).value, center.icrs.dec.to(u.deg).value)


def test_gen_numeric_sql():
    common_select = 'select * from ivoa.obscore WHERE '
    assert _gen_sql({'bandwidth': '23'}) == common_select + 'bandwidth=23.0'
    assert _gen_sql({'bandwidth': '22 .. 23'}) == common_select +\
        '(22.0<=bandwidth AND bandwidth<=23.0)'
    assert _gen_sql(
        {'bandwidth': '<100'}) == common_select + 'bandwidth<=100.0'
    assert _gen_sql(
        {'bandwidth': '>100'}) == common_select + 'bandwidth>=100.0'
    assert _gen_sql({'bandwidth': '!(20 .. 30)'}) == common_select + \
        '(bandwidth<=20.0 OR bandwidth>=30.0)'
    assert _gen_sql({'bandwidth': '<10 | >20'}) == common_select + \
        '(bandwidth<=10.0 OR bandwidth>=20.0)'
    assert _gen_sql({'bandwidth': 100, 'frequency': '>3'}) == common_select +\
        "bandwidth=100 AND frequency>=3.0"


def test_gen_str_sql():
    common_select = 'select * from ivoa.obscore WHERE '
    assert _gen_sql({'pub_title': '*Cosmic*'}) == common_select + \
        "pub_title LIKE '%Cosmic%'"
    assert _gen_sql({'pub_title': 'Galaxy'}) == common_select + \
        "pub_title='Galaxy'"
    assert _gen_sql({'pub_abstract': '*50% of the mass*'}) == common_select + \
        r"pub_abstract LIKE '%50\% of the mass%'"
    assert _gen_sql({'project_code': '2012.* | 2013.?3*'}) == common_select + \
        "(proposal_id LIKE '2012.%' OR proposal_id LIKE '2013._3%')"
    # test with brackets like the form example
    assert _gen_sql({'project_code': '(2012.* | 2013.?3*)'}) == common_select + \
        "(proposal_id LIKE '2012.%' OR proposal_id LIKE '2013._3%')"


def test_gen_array_sql():
    # test string array input (regression in #2094)
    # string arrays should be OR'd together
    common_select = "select * from ivoa.obscore WHERE "
    test_keywords = ["High-mass star formation", "Disks around high-mass stars"]
    assert _gen_sql({"spatial_resolution": "<0.1",
        "science_keyword": test_keywords}) == common_select + \
            "spatial_resolution<=0.1 AND (science_keyword='High-mass star formation' OR science_keyword='Disks around high-mass stars')"


def test_gen_datetime_sql():
    common_select = 'select * from ivoa.obscore WHERE '
    assert _gen_sql({'start_date': '01-01-2020'}) == common_select + \
        "t_min=58849.0"
    assert _gen_sql({'start_date': '>01-01-2020'}) == common_select + \
        "t_min>=58849.0"
    assert _gen_sql({'start_date': '<01-01-2020'}) == common_select + \
        "t_min<=58849.0"
    assert _gen_sql({'start_date': '(01-01-2020 .. 01-02-2020)'}) == \
        common_select + "(58849.0<=t_min AND t_min<=58880.0)"


def test_gen_spec_res_sql():
    common_select = 'select * from ivoa.obscore WHERE '
    assert _gen_sql({'spectral_resolution': 70}) == common_select + \
        "em_resolution=20985472.06"
    assert _gen_sql({'spectral_resolution': '<70'}) == common_select + \
        "em_resolution>=20985472.06"
    assert _gen_sql({'spectral_resolution': '>70'}) == common_select + \
        "em_resolution<=20985472.06"
    assert _gen_sql({'spectral_resolution': '(70 .. 80)'}) == common_select + \
        "(23983396.64<=em_resolution AND em_resolution<=20985472.06)"
    assert _gen_sql({'spectral_resolution': '(70|80)'}) == common_select + \
        "(em_resolution=20985472.06 OR em_resolution=23983396.64)"


def test_gen_public_sql():
    common_select = 'select * from ivoa.obscore'
    assert _gen_sql({'public_data': None}) == common_select
    assert _gen_sql({'public_data': True}) == common_select +\
        " WHERE data_rights='Public'"
    assert _gen_sql({'public_data': False}) == common_select + \
        " WHERE data_rights='Proprietary'"


def test_gen_science_sql():
    common_select = 'select * from ivoa.obscore'
    assert _gen_sql({'science_observation': None}) == common_select
    assert _gen_sql({'science_observation': True}) == common_select +\
        " WHERE science_observation='T'"
    assert _gen_sql({'science_observation': False}) == common_select +\
        " WHERE science_observation='F'"


def test_pol_sql():
    common_select = 'select * from ivoa.obscore'
    assert _gen_sql({'polarisation_type': 'Stokes I'}) == common_select +\
        " WHERE pol_states LIKE '%I%'"
    assert _gen_sql({'polarisation_type': 'Single'}) == common_select + \
        " WHERE pol_states='/XX/'"
    assert _gen_sql({'polarisation_type': 'Dual'}) == common_select + \
        " WHERE pol_states='/XX/YY/'"
    assert _gen_sql({'polarisation_type': 'Full'}) == common_select + \
        " WHERE pol_states='/XX/XY/YX/YY/'"
    assert _gen_sql({'polarisation_type': ['Single', 'Dual']}) == \
        common_select + " WHERE (pol_states='/XX/' OR pol_states='/XX/YY/')"
    assert _gen_sql({'polarisation_type': 'Single, Dual'}) == \
        common_select + " WHERE (pol_states='/XX/' OR pol_states='/XX/YY/')"


def test_unused_args():
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    # with patch('astroquery.alma.tapsql.coord.SkyCoord.from_name') as name_mock, pytest.raises(TypeError) as typeError:
    with patch('astroquery.alma.tapsql.coord.SkyCoord.from_name') as name_mock:
        with pytest.raises(TypeError) as typeError:
            name_mock.return_value = SkyCoord(1, 2, unit='deg')
            alma.query_object('M13', public=False, bogus=True, nope=False, band_list=[3])

        assert "['bogus -> True', 'nope -> False']" in str(typeError.value)


def test_query():
    # Tests the query and return values
    tap_mock = Mock()
    empty_result = Table.read(os.path.join(DATA_DIR, 'alma-empty.txt'),
                              format='ascii')
    mock_result = Mock()
    mock_result.to_table.return_value = empty_result
    tap_mock.search.return_value = mock_result
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._tap = tap_mock
    result = alma.query_region(SkyCoord(1*u.deg, 2*u.deg, frame='icrs'),
                               radius=1*u.deg)
    assert len(result) == 0
    assert 'proposal_id' in result.columns
    tap_mock.search.assert_called_once_with(
        "select * from ivoa.obscore WHERE "
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,1.0), s_region) = 1) "
        "AND science_observation='T' AND data_rights='Public'",
        language='ADQL', maxrec=None)

    # one row result
    tap_mock = Mock()
    onerow_result = Table.read(os.path.join(DATA_DIR, 'alma-onerow.txt'),
                               format='ascii')
    mock_result = Mock()
    mock_result.to_table.return_value = onerow_result
    tap_mock.search.return_value = mock_result
    alma = Alma()
    alma._tap = tap_mock
    with patch('astroquery.alma.tapsql.coord.SkyCoord.from_name') as name_mock:
        name_mock.return_value = SkyCoord(1, 2, unit='deg')
        result = alma.query_object('M83', public=False,
                                   band_list=[3])
    assert len(result) == 1

    tap_mock.search.assert_called_once_with(
        "select * from ivoa.obscore WHERE "
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,0.16666666666666666), s_region) = 1) "
        "AND band_list LIKE '%3%' AND science_observation='T' AND "
        "data_rights='Proprietary'",
        language='ADQL', maxrec=None)

    # repeat for legacy columns
    mock_result = Mock()
    tap_mock = Mock()
    mock_result.to_table.return_value = onerow_result
    tap_mock.search.return_value = mock_result
    alma = Alma()
    alma._tap = tap_mock
    with patch('astroquery.alma.tapsql.coord.SkyCoord.from_name') as name_mock:
        name_mock.return_value = SkyCoord(1, 2, unit='deg')
        result_legacy = alma.query_object('M83', public=False,
                                          legacy_columns=True,
                                          band_list=[3])
    assert len(result) == 1

    assert 'Project code' in result_legacy.columns
    tap_mock.search.assert_called_once_with(
        "select * from ivoa.obscore WHERE "
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,0.16666666666666666), s_region) = 1) "
        "AND band_list LIKE '%3%' AND science_observation='T' AND "
        "data_rights='Proprietary'",
        language='ADQL', maxrec=None)
    row_legacy = result_legacy[0]
    row = result[0]
    for item in _OBSCORE_TO_ALMARESULT.items():
        if item[0] == 't_min':
            assert Time(row[item[0]], format='mjd').strftime('%d-%m-%Y') ==\
                row_legacy[item[1]]
        else:
            assert row[item[0]] == row_legacy[item[1]]

    # query with different arguments
    tap_mock = Mock()
    empty_result = Table.read(os.path.join(DATA_DIR, 'alma-empty.txt'),
                              format='ascii')
    mock_result = Mock()
    mock_result.to_table.return_value = empty_result
    tap_mock.search.return_value = mock_result
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._tap = tap_mock
    result = alma.query_region('1 2', radius=1*u.deg,
                               payload={'frequency': '22'}, public=None,
                               band_list='1 3', science=False,
                               start_date='01-01-2010',
                               polarisation_type='Dual',
                               fov=0.0123130,
                               integration_time=25)
    assert len(result) == 0
    tap_mock.search.assert_called_with(
        "select * from ivoa.obscore WHERE frequency=22.0 AND "
        "(INTERSECTS(CIRCLE('ICRS',1.0,2.0,1.0), s_region) = 1) AND "
        "(band_list LIKE '%1%' OR band_list LIKE '%3%') AND "
        "t_min=55197.0 AND pol_states='/XX/YY/' AND s_fov=0.012313 AND "
        "t_exptime=25 AND science_observation='F'",
        language='ADQL', maxrec=None
    )


def test_sia():
    sia_mock = Mock()
    empty_result = Table.read(os.path.join(DATA_DIR, 'alma-empty.txt'),
                              format='ascii')
    sia_mock.search.return_value = Mock(table=empty_result)
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._sia = sia_mock
    result = alma.query_sia(pos='CIRCLE 1 2 1', calib_level=[0, 1],
                            data_rights='Public',
                            band=(300, 400),
                            time=545454, maxrec=10, pol=['XX', 'YY'],
                            instrument='JAO', collection='ALMA',
                            field_of_view=0.0123130, data_type='cube',
                            target_name='J0423-013',
                            publisher_did='ADS/JAO.ALMA#2013.1.00546.S',
                            exptime=25)
    assert len(result.table) == 0
    assert_called_with(sia_mock.search, calib_level=[0, 1],
                       band=(300, 400), data_type='cube',
                       pos='CIRCLE 1 2 1',
                       time=545454, maxrec=10, pol=['XX', 'YY'],
                       instrument='JAO', collection='ALMA',
                       data_rights='Public',
                       field_of_view=0.0123130,
                       target_name='J0423-013',
                       publisher_did='ADS/JAO.ALMA#2013.1.00546.S', exptime=25)


def test_tap():
    tap_mock = Mock()
    empty_result = Table.read(os.path.join(DATA_DIR, 'alma-empty.txt'),
                              format='ascii')
    tap_mock.search.return_value = Mock(table=empty_result)
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._tap = tap_mock
    result = alma.query_tap('select * from ivoa.ObsCore')
    assert len(result.table) == 0

    tap_mock.search.assert_called_once_with('select * from ivoa.ObsCore',
                                            language='ADQL', maxrec=None)


@pytest.mark.parametrize('data_archive_url',
                         [
                            ('https://almascience.nrao.edu'),
                            ('https://almascience.eso.org'),
                            ('https://almascience.nao.ac.jp')
                         ])
def test_tap_url(data_archive_url):
    _test_tap_url(data_archive_url)


def _test_tap_url(data_archive_url):
    alma = Alma()
    alma._get_dataarchive_url = Mock(return_value=data_archive_url)
    alma._get_dataarchive_url.reset_mock()
    assert alma.tap_url == f"{data_archive_url}/tap"


@pytest.mark.parametrize('data_archive_url',
                         [
                            ('https://almascience.nrao.edu'),
                            ('https://almascience.eso.org'),
                            ('https://almascience.nao.ac.jp')
                         ])
def test_sia_url(data_archive_url):
    _test_sia_url(data_archive_url)


def _test_sia_url(data_archive_url):
    alma = Alma()
    alma._get_dataarchive_url = Mock(return_value=data_archive_url)
    alma._get_dataarchive_url.reset_mock()
    assert alma.sia_url == f"{data_archive_url}/sia2"


@pytest.mark.parametrize('data_archive_url',
                         [
                            ('https://almascience.nrao.edu'),
                            ('https://almascience.eso.org'),
                            ('https://almascience.nao.ac.jp')
                         ])
def test_datalink_url(data_archive_url):
    _test_datalink_url(data_archive_url)


def _test_datalink_url(data_archive_url):
    alma = Alma()
    alma._get_dataarchive_url = Mock(return_value=data_archive_url)
    alma._get_dataarchive_url.reset_mock()
    assert alma.datalink_url == f"{data_archive_url}/datalink/sync"


def test_get_data_info():
    class MockDataLinkService:
        def run_sync(self, uid):
            return _mocked_datalink_sync(uid)

    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._datalink = MockDataLinkService()
    result = alma.get_data_info(uids='uid://A001/X12a3/Xe9')
    assert len(result) == 9


# This method will be used by the mock in test_get_data_info_expand_tarfiles to replace requests.get
def _mocked_datalink_sync(*args, **kwargs):
    class MockResponse:
        adhoc_service_1_param1 = type('', (object, ), {'ID': 'standardID', 'value': 'ivo://ivoa.net/std/DataLink#links-1.0'})()
        adhoc_service_1_param2 = type('', (object, ), {'ID': 'accessURL', 'value': 'https://almascience.org/datalink/sync?ID=2017.1.01185.S_uid___A001_X12a3_Xe9_001_of_001.tar'})()
        adhoc_service_1 = type('', (object, ), {'ID': 'DataLink.2017.1.01185.S_uid___A001_X12a3_Xe9_001_of_001.tar', 'params': [adhoc_service_1_param1, adhoc_service_1_param2]})()

        adhoc_service_2_param1 = type('', (object, ), {'ID': 'standardID', 'value': 'ivo://ivoa.net/std/DataLink#links-1.0'})()
        adhoc_service_2_param2 = type('', (object, ), {'ID': 'accessURL', 'value': 'https://almascience.org/datalink/sync?ID=2017.1.01185.S_uid___A001_X12a3_Xe9_auxiliary.tar'})()
        adhoc_service_2 = type('', (object, ), {'ID': 'DataLink.2017.1.01185.S_uid___A001_X12a3_Xe9_auxiliary.tar', 'params': [adhoc_service_1_param1, adhoc_service_1_param2]})()

        adhoc_services = {
            'DataLink.2017.1.01185.S_uid___A001_X12a3_Xe9_001_of_001.tar': adhoc_service_1,
            'DataLink.2017.1.01185.S_uid___A001_X12a3_Xe9_auxiliary.tar': adhoc_service_2
        }

        def __init__(self, table):
            self.table = table

        def to_table(self):
            return self.table

        @property
        def status(self):
            return ['OK']

        def iter_adhocservices(self):
            return [self.adhoc_service_1, self.adhoc_service_2]

        def get_adhocservice_by_id(self, adhoc_service_id):
            return self.adhoc_services[adhoc_service_id]

    print(f"\n\nFOUND ARGS {args}\n\n")

    if args[0] == 'uid://A001/X12a3/Xe9':
        return MockResponse(Table.read(data_path('alma-datalink.xml'), format='votable'))
    elif args[0] == '2017.1.01185.S_uid___A001_X12a3_Xe9_001_of_001.tar':
        return MockResponse(Table.read(data_path('alma-datalink-recurse-this.xml'), format='votable'))
    elif args[0] == '2017.1.01185.S_uid___A001_X12a3_Xe9_auxiliary.tar':
        return MockResponse(Table.read(data_path('alma-datalink-recurse-aux.xml'), format='votable'))

    pytest.fail('Should not get here.')


# @patch('pyvo.dal.adhoc.DatalinkService', side_effect=_mocked_datalink_sync)
def test_get_data_info_expand_tarfiles():
    class MockDataLinkService:
        def run_sync(self, uid):
            return _mocked_datalink_sync(uid)

    alma = Alma()
    alma._datalink = MockDataLinkService()
    result = alma.get_data_info(uids='uid://A001/X12a3/Xe9', expand_tarfiles=True)

    # Entire expanded structure is 19 links long.
    assert len(result) == 19


def test_galactic_query():
    """
    regression test for 1867
    """
    tap_mock = Mock()
    empty_result = Table.read(os.path.join(DATA_DIR, 'alma-empty.txt'),
                              format='ascii')
    mock_result = Mock()
    mock_result.to_table.return_value = empty_result
    tap_mock.search.return_value = mock_result
    alma = Alma()
    alma._get_dataarchive_url = Mock()
    alma._tap = tap_mock
    result = alma.query_region(SkyCoord(0*u.deg, 0*u.deg, frame='galactic'),
                               radius=1*u.deg, get_query_payload=True)

    assert "'ICRS',266.405,-28.9362,1.0" in result


def test_download_files():
    def _requests_mock(method, url, **kwargs):
        response = Mock()
        response.headers = {
            'Content-Disposition': 'attachment; '
                                   'filename={}'.format(url.split('/')[-1])}
        return response

    def _download_file_mock(url, file_name, **kwargs):
        return file_name
    alma = Alma()
    alma._request = Mock(side_effect=_requests_mock)
    alma._download_file = Mock(side_effect=_download_file_mock)
    downloaded_files = alma.download_files(['https://location/file1'])
    assert len(downloaded_files) == 1
    assert downloaded_files[0].endswith('file1')

    alma._request.reset_mock()
    alma._download_file.reset_mock()
    downloaded_files = alma.download_files(['https://location/file1',
                                            'https://location/file2'])
    assert len(downloaded_files) == 2

    # error cases
    alma._request = Mock()
    # no Content-Disposition results in no downloaded file
    alma._request.return_value = Mock(headers={})
    result = alma.download_files(['https://location/file1'])
    assert not result
