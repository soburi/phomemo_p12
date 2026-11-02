#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-

import argparse
import sys
import io
import binascii

import serial
import PIL.Image
import PIL.ImageOps

class DummySerial:
    def __init__(self, w):
        self.width = int(w/8)

    def write(self, x):
        with io.BytesIO(x) as bstrm:
            while bstrm.readable():
                data = bytearray(self.width)
                blen = bstrm.readinto(data)
                if blen == 0:
                    break
                print(binascii.hexlify(data[0:blen]), file=sys.stderr)
        return 0

    def flush(self):
        return 0

    def read(self):
        return bytearray(0)

def header(port):
    # printer initialization sniffed from Android app "Print Master"
    packets = [
        '1f1138',
        '1f11111f11121f11091f1113',
        '1f1109',
        '1f11191f1111',
        '1f1119',
        '1f1107'
    ]

    for packet in packets:
        port.write(bytes.fromhex(packet))
        port.flush()
        resp = port.read()
        #print(binascii.hexlify(resp), file=sys.stderr)

def set_density(port, level):
    # print density 1 (light) .. 4 (very dark), sniffed from "Print Master".
    # Without it the printer uses a faint default after power-on;
    # the setting persists until the printer is switched off.
    # The printer sends no reply, so don't wait for one here.
    port.write(bytes([0x1f, 0x11, 0x02, level]))
    port.flush()

def preprocess_image(data, width):
    with PIL.Image.open(io.BytesIO(data)) as src:
        src_w, src_h = src.size
        if src_w > width:
            resized = src.crop(0, 0, width, src_h)
        elif src_w < width:
            resized = PIL.Image.new('1', (width, src_h), 1)
            resized.paste(src, (width-src_w, 0))
        else:
            resized = src

        return PIL.ImageOps.invert(resized.convert("RGB")).convert("1")

def image_to_bytes(image):
    width, height = image.size

    output = bytearray(0)

    for y in range(height):
        byte = 0
        for x in range(width):
            pixel = 1 if image.getpixel((x, y)) != 0 else 0
            byte |= (pixel & 0x1) << (7 - (x % 8))

            if (x % 8) == 7:
                output.append(byte)
                byte = 0

    return output

def print_image(port, image):
    width, height = image.size

    output = bytearray.fromhex('1b401d763000')
    output.extend( int(width/8).to_bytes(2, byteorder="little") )
    output.extend( height.to_bytes(2, byteorder="little") )

    port.write(output)
    port.flush()
    resp = port.read()
    #print(binascii.hexlify(resp), file=sys.stderr)

    output = image_to_bytes(image)

    port.write(output)
    port.flush()
    resp = port.read()
    #print(binascii.hexlify(resp), file=sys.stderr)


def tape_feed(port):
    output = bytearray.fromhex('1b640d1b640d')

    port.write(output)
    port.flush()
    resp = port.read()
    #print(binascii.hexlify(resp), file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description='Phomemo P12 printing command')
    parser.add_argument('--port', dest='port', required=True, help='Serial Port')
    parser.add_argument('--dots', dest='dots', default=96, type=int, help='Number of dots in tape width')
    parser.add_argument('--density', dest='density', type=int, choices=range(1, 5), default=None,
                        help='Print density 1 (light) to 4 (very dark). Printer default if not given.')
    parser.add_argument('filename', nargs='?', help='Filename of image to print. Using stdin if not given.')

    args = parser.parse_args()

    if args.filename:
        imagedata = open(args.filename, 'rb').read()
    else:
        imagedata = sys.stdin.buffer.read()

    image = preprocess_image(imagedata, args.dots)

    if args.port == "dummy":
        port = DummySerial(args.dots)
    else:
        port = serial.Serial(args.port, timeout=10)

    header(port)
    if args.density is not None:
        set_density(port, args.density)
    print_image(port, image)
    tape_feed(port)


if __name__ == '__main__':
    main()
