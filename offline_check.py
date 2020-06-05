#!/usr/bin/env python
'''
Check a set of terrain files for corruption
'''
import os
#from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
import argparse
import time
import gzip
import shutil
import struct
import crc16

from terrain_gen import TERRAIN_GRID_BLOCK_SIZE_Y, east_blocks, IO_BLOCK_SIZE, TERRAIN_GRID_FORMAT_VERSION, GridBlock

# IO block size is 2048
# Actual size is 1821 bytes
# Last 227 bytes is filling
def check_filled(block, lat_int, lon_int, grid_spacing):
    '''check a block for validity'''
    if len(block) != IO_BLOCK_SIZE - 227:
        print("Bad size {0} of {1}".format(len(block), IO_BLOCK_SIZE))
        return False
    (bitmap, lat, lon, crc, version, spacing) = struct.unpack("<QiiHHH", block[:22])
    if (version != TERRAIN_GRID_FORMAT_VERSION):
        print("Bad version: " + str(version))
        return False
    if abs(lat_int - (lat/1E7)) > 2 or abs(lon_int - (lon/1E7)) > 2:
        print("Bad lat/lon: {0}, {1}".format((lat/1E7), (lon/1E7)))
        return False
    if spacing != 100:
        print("Bad spacing: " + str(spacing))
        return False
    if bitmap != (1<<56)-1:
        print("Bad bitmap")
        return False

    block = block[:16] + struct.pack("<H", 0) + block[18:]
    crc2 = crc16.crc16xmodem(block[:1821])
    if crc2 != crc:
        print("Bad CRC")
        return False
    return True

if __name__ == '__main__':
    # Create the parser
    parser = argparse.ArgumentParser(description='ArduPilot Terrain DAT file generator')

    # Add the arguments
    # Folder to store processed DAT files
    parser.add_argument('-folder', action="store", dest="folder", default="processedTerrain")
    
    args = parser.parse_args()

    targetFolder = os.path.join(os.getcwd(), args.folder)

    grid_spacing = 100
    

    #for each file in folder
    for file in os.listdir(targetFolder):
        if file.endswith("DAT.gz") or file.endswith("DAT"):
            # It's a compressed tile
            # 1. Check it's a valid gzip
            tile = None
            try:
                lat_int = int(os.path.basename(file)[1:3])
                if os.path.basename(file)[0:1] == "S":
                    lat_int = -lat_int
                lon_int = int(os.path.basename(file)[4:7])
                if os.path.basename(file)[3:4] == "W":
                    lon_int = -lon_int
                if file.endswith("DAT.gz"):
                    with gzip.open(os.path.join(targetFolder, file), 'rb') as f:
                        tile = f.read()
                else:
                    with open(os.path.join(targetFolder, file), 'rb') as f:
                        tile = f.read()
            except Exception as e:
                print("Bad file: " + file)
                print(e)
            # 2. Is it a valid dat file?
            if (tile):
                total_blocks = east_blocks(lat_int*1e7, lon_int*1e7, grid_spacing) * TERRAIN_GRID_BLOCK_SIZE_Y
                # 2a. Are the correct number of blocks present?
                # There is an extra 1821 bytes at the end on the file (2048-1821 = 227), as the 
                # terrain blocks only take up 1821 bytes.
                if (len(tile)+227) != (total_blocks * IO_BLOCK_SIZE):
                    print("Bad number of blocks: {0}, {1} vs {2}".format(file, len(tile), total_blocks * IO_BLOCK_SIZE))
                # 2b. Does each block have the correct CRC and fields?
                for blocknum in range(total_blocks):
                    block = tile[(blocknum * IO_BLOCK_SIZE):((blocknum + 1)* IO_BLOCK_SIZE)-227]
                    if not check_filled(block, lat_int, lon_int, 100):
                        print("Bad data in block {0} of {1}".format(blocknum, total_blocks))
            else:
                print("Bad tile: " + file)
    print("Done!")
