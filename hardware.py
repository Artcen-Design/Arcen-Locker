"""Serial protocol helpers for the Chinese locker control board.

Binary framing confirmed working against the real board — kept as-is, just
moved out of server.py so the Flask routes stay focused on HTTP concerns.
"""
import functools
import time

import serial

import config

HEADER = b'\x57\x4B\x4C\x59'  # "WKLY"
BOARD_ADDR = b'\x01'
CMD_BYTE_OPEN = b'\x82'
CMD_BYTE_CHECK = b'\x83'
RESPONSE_LENGTH = 11


def _calculate_checksum(payload):
    checksum = functools.reduce(lambda a, b: a ^ b, payload)
    return bytes([checksum])


def _build_command(cmd_byte, channel, data_bytes=b''):
    channel_byte = bytes([channel])
    payload = BOARD_ADDR + cmd_byte + channel_byte + data_bytes
    length = 4 + 1 + len(payload) + 1
    length_byte = bytes([length])
    checksum = _calculate_checksum(payload)
    return HEADER + length_byte + payload + checksum


def _send_serial_command(command):
    try:
        with serial.Serial(config.SERIAL_PORT, config.BAUD_RATE, timeout=1.0) as ser:
            ser.flushInput()
            ser.flushOutput()
            ser.write(command)
            time.sleep(0.1)
            return ser.read(RESPONSE_LENGTH)
    except serial.SerialException as e:
        print(f"SERIAL ERROR: {e}")
        return None
    except Exception as e:
        print(f"GENERAL ERROR: {e}")
        return None


def open_locker(channel):
    """Sends the open command. Returns True if the board acknowledged (or
    sent no reply, which is normal for 'open'), False on a comms failure."""
    command = _build_command(CMD_BYTE_OPEN, channel)
    response = _send_serial_command(command)
    return response is not None


def get_lock_status(channel):
    command = _build_command(CMD_BYTE_CHECK, channel)
    response = _send_serial_command(command)
    status = {"channel": channel, "status": "UNKNOWN"}
    if response:
        try:
            if (response[0:4] == HEADER and
                    response[6] == CMD_BYTE_CHECK[0] and
                    response[8] == channel):
                state_byte = response[9]
                if state_byte == 0x01:
                    status["status"] = "LOCKED"
                elif state_byte == 0x00:
                    status["status"] = "UNLOCKED"
        except IndexError:
            pass
    return status


def get_all_statuses(channels):
    return [get_lock_status(channel) for channel in channels]
