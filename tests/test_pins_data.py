from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


import re
import pytest
from mock import patch, MagicMock

import gpiozero.devices
import gpiozero.pins.data
import gpiozero.pins.native
from gpiozero.pins.data import pi_info, Style, HeaderInfo, PinInfo
from gpiozero import PinMultiplePins, PinNoPins, PinUnknownPi


def test_pi_revision():
    save_factory = gpiozero.devices.pin_factory
    try:
        # Can't use MockPin for this as we want something that'll actually try
        # and read /proc/cpuinfo (MockPin simply parrots the 2B's data);
        # NativePin is used as we're guaranteed to be able to import it
        gpiozero.devices.pin_factory = gpiozero.pins.native.NativePin
        with patch('io.open') as m:
            m.return_value.__enter__.return_value = ['lots of irrelevant', 'lines', 'followed by', 'Revision: 0002', 'Serial:  xxxxxxxxxxx']
            assert pi_info().revision == '0002'
            # LocalPin caches the revision (because realistically it isn't going to
            # change at runtime); we need to wipe it here though
            gpiozero.pins.native.NativePin._PI_REVISION = None
            m.return_value.__enter__.return_value = ['Revision: a21042']
            assert pi_info().revision == 'a21042'
            # Check over-volting result (some argument over whether this is 7 or
            # 8 character result; make sure both work)
            gpiozero.pins.native.NativePin._PI_REVISION = None
            m.return_value.__enter__.return_value = ['Revision: 1000003']
            assert pi_info().revision == '0003'
            gpiozero.pins.native.NativePin._PI_REVISION = None
            m.return_value.__enter__.return_value = ['Revision: 100003']
            assert pi_info().revision == '0003'
            with pytest.raises(PinUnknownPi):
                m.return_value.__enter__.return_value = ['nothing', 'relevant', 'at all']
                gpiozero.pins.native.NativePin._PI_REVISION = None
                pi_info()
            with pytest.raises(PinUnknownPi):
                pi_info('0fff')
    finally:
        gpiozero.devices.pin_factory = save_factory

def test_pi_info():
    r = pi_info('900011')
    assert r.model == 'B'
    assert r.pcb_revision == '1.0'
    assert r.memory == 512
    assert r.manufacturer == 'Sony'
    assert r.storage == 'SD'
    assert r.usb == 2
    assert not r.wifi
    assert not r.bluetooth
    assert r.csi == 1
    assert r.dsi == 1
    with pytest.raises(PinUnknownPi):
        pi_info('9000f1')

def test_pi_info_other_types():
    with pytest.raises(PinUnknownPi):
        pi_info(b'9000f1')
    with pytest.raises(PinUnknownPi):
        pi_info(0x9000f1)

def test_physical_pins():
    # Assert physical pins for some well-known Pi's; a21041 is a Pi2B
    assert pi_info('a21041').physical_pins('3V3') == {('P1', 1), ('P1', 17)}
    assert pi_info('a21041').physical_pins('GPIO2') == {('P1', 3)}
    assert pi_info('a21041').physical_pins('GPIO47') == set()

def test_physical_pin():
    with pytest.raises(PinMultiplePins):
        assert pi_info('a21041').physical_pin('GND')
    assert pi_info('a21041').physical_pin('GPIO3') == ('P1', 5)
    with pytest.raises(PinNoPins):
        assert pi_info('a21041').physical_pin('GPIO47')

def test_pulled_up():
    assert pi_info('a21041').pulled_up('GPIO2')
    assert not pi_info('a21041').pulled_up('GPIO4')
    assert not pi_info('a21041').pulled_up('GPIO47')

def test_pprint_content():
    with patch('sys.stdout') as stdout:
        stdout.output = []
        stdout.write = lambda buf: stdout.output.append(buf)
        pi_info('900092').pprint(color=False)
        s = ''.join(stdout.output)
        assert ('o' * 20 + ' ') in s # first header row
        assert ('1' + 'o' * 19 + ' ') in s # second header row
        assert 'PiZero' in s
        assert 'V1.2' in s # PCB revision
        assert '900092' in s # Pi revision
        assert 'BCM2835' in s # SOC name
        stdout.output = []
        pi_info('0002').pprint(color=False)
        s = ''.join(stdout.output)
        assert ('o' * 13 + ' ') in s # first header row
        assert ('1' + 'o' * 12 + ' ') in s # second header row
        assert 'Pi Model' in s
        assert 'B  V1.0' in s # PCB revision
        assert '0002' in s # Pi revision
        assert 'BCM2835' in s # SOC name
        stdout.output = []
        pi_info('0014').headers['SODIMM'].pprint(color=False)
        assert len(''.join(stdout.output).splitlines()) == 100

def test_pprint_headers():
    assert len(pi_info('0002').headers) == 1
    assert len(pi_info('000e').headers) == 2
    assert len(pi_info('900092').headers) == 1
    with patch('sys.stdout') as stdout:
        stdout.output = []
        stdout.write = lambda buf: stdout.output.append(buf)
        pi_info('0002').pprint()
        s = ''.join(stdout.output)
        assert 'P1:\n' in s
        assert 'P5:\n' not in s
        stdout.output = []
        pi_info('000e').pprint()
        s = ''.join(stdout.output)
        assert 'P1:\n' in s
        assert 'P5:\n' in s
        stdout.output = []
        pi_info('900092').pprint()
        s = ''.join(stdout.output)
        assert 'P1:\n' in s
        assert 'P5:\n' not in s

def test_pprint_color():
    with patch('sys.stdout') as stdout:
        stdout.output = []
        stdout.write = lambda buf: stdout.output.append(buf)
        pi_info('900092').pprint(color=False)
        s = ''.join(stdout.output)
        assert '\x1b[0m' not in s # make sure ANSI reset code isn't in there
        stdout.output = []
        pi_info('900092').pprint(color=True)
        s = ''.join(stdout.output)
        assert '\x1b[0m' in s # check the ANSI reset code *is* in there (can't guarantee much else!)
        stdout.output = []
        stdout.fileno.side_effect = IOError('not a real file')
        pi_info('900092').pprint()
        s = ''.join(stdout.output)
        assert '\x1b[0m' not in s # default should output mono
        with patch('os.isatty') as isatty:
            isatty.return_value = True
            stdout.fileno.side_effect = None
            stdout.output = []
            pi_info('900092').pprint()
            s = ''.join(stdout.output)
            assert '\x1b[0m' in s # default should now output color

def test_pprint_styles():
    with pytest.raises(ValueError):
        Style.from_style_content('mono color full')
    with pytest.raises(ValueError):
        Style.from_style_content('full specs')
    with patch('sys.stdout') as stdout:
        s = '{0:full}'.format(pi_info('900092'))
        assert '\x1b[0m' not in s # ensure default is mono when stdout is not a tty
    with pytest.raises(ValueError):
        '{0:foo on bar}'.format(Style())

def test_pprint_missing_pin():
    header = HeaderInfo('FOO', 4, 2, {
        1: PinInfo(1, '5V',    False, 1, 1),
        2: PinInfo(2, 'GND',   False, 1, 2),
        # Pin 3 is deliberately missing
        4: PinInfo(4, 'GPIO1', False, 2, 2),
        5: PinInfo(5, 'GPIO2', False, 3, 1),
        6: PinInfo(6, 'GPIO3', False, 3, 2),
        7: PinInfo(7, '3V3',   False, 4, 1),
        8: PinInfo(8, 'GND',   False, 4, 2),
        })
    with patch('sys.stdout') as stdout:
        stdout.output = []
        stdout.write = lambda buf: stdout.output.append(buf)
        s = ''.join(stdout.output)
        header.pprint()
        for i in range(1, 9):
            if i == 3:
                assert '(3)' not in s
            else:
                assert ('(%d)' % i)

def test_pprint_rows_cols():
    assert '{0:row1}'.format(pi_info('900092').headers['P1']) == '1o'
    assert '{0:row2}'.format(pi_info('900092').headers['P1']) == 'oo'
    assert '{0:col1}'.format(pi_info('0002').headers['P1']) == '1oooooooooooo'
    assert '{0:col2}'.format(pi_info('0002').headers['P1']) == 'ooooooooooooo'
    with pytest.raises(ValueError):
        '{0:row16}'.format(pi_info('0002').headers['P1'])
    with pytest.raises(ValueError):
        '{0:col3}'.format(pi_info('0002').headers['P1'])
